"""Tune on validation, refit, evaluate once on test, and persist model records."""

import hashlib
import itertools
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import psycopg
from psycopg.types.json import Jsonb
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ossustain_pipeline.modeling.config import ModelingConfig
from ossustain_pipeline.modeling.core import (
    activity_decline_scores,
    calibration_bins,
    classification_metrics,
    paired_repository_cluster_bootstrap,
    repository_cluster_bootstrap,
    robustness_metrics,
    select_f1_threshold,
)
from ossustain_pipeline.modeling.data import (
    ACTIVITY_FEATURES,
    ModelDataset,
    ModelRow,
    load_model_dataset,
    load_test_robustness_outcomes,
)
from ossustain_pipeline.snapshots.core import is_decline

FEATURE_FAMILIES = {
    "activity_only": ACTIVITY_FEATURES,
    "extended": None,
}
ALGORITHMS = (
    "threshold_baseline",
    "logistic_regression",
    "random_forest",
    "gradient_boosting",
)
SCORED_METRICS = ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _identity() -> str:
    root = Path(__file__).resolve().parents[4]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "pipeline/src/ossustain_pipeline/modeling"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return revision + ("+dirty" if dirty else "")


def _root() -> Path:
    return Path(__file__).resolve().parents[4]


def _matrix(rows: list[ModelRow], feature_names: tuple[str, ...]) -> list[list[float]]:
    return [[row.features[name] for name in feature_names] for row in rows]


def _labels(rows: list[ModelRow]) -> list[int]:
    return [row.label for row in rows]


def _grid(config: ModelingConfig, algorithm: str) -> list[dict[str, Any]]:
    model_grid = getattr(config.models, algorithm)
    fields = model_grid.model_dump()
    keys = tuple(fields)
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*fields.values())]


def _estimator(algorithm: str, params: dict[str, Any], seed: int) -> Pipeline:
    steps: list[tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True))
    ]
    if algorithm == "logistic_regression":
        steps.extend(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=params["c"],
                        class_weight=params["class_weight"],
                        max_iter=2000,
                        random_state=seed,
                        solver="lbfgs",
                    ),
                ),
            ]
        )
    elif algorithm == "random_forest":
        steps.append(
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=params["n_estimators"],
                    max_depth=params["max_depth"],
                    min_samples_leaf=params["min_samples_leaf"],
                    class_weight=params["class_weight"],
                    random_state=seed,
                    n_jobs=1,
                ),
            )
        )
    elif algorithm == "gradient_boosting":
        steps.append(
            (
                "classifier",
                GradientBoostingClassifier(
                    n_estimators=params["n_estimators"],
                    learning_rate=params["learning_rate"],
                    max_depth=params["max_depth"],
                    random_state=seed,
                ),
            )
        )
    else:
        raise ValueError(f"Unsupported estimator: {algorithm}")
    return Pipeline(steps)


def _probabilities(model: Pipeline, rows: list[ModelRow], names: tuple[str, ...]) -> list[float]:
    matrix = _matrix(rows, names)
    positive_index = list(model.classes_).index(1)
    return [float(value) for value in model.predict_proba(matrix)[:, positive_index]]


def _model_report(
    rows: list[ModelRow], scores: list[float], threshold: float, config: ModelingConfig
) -> list[dict[str, Any]]:
    if len(rows) != len(scores):
        raise ValueError("Prediction count differs from modeling row count")
    strata = [("overall", rows, scores)]
    for size in ("small", "medium", "large"):
        pairs = [
            (row, score) for row, score in zip(rows, scores, strict=True) if row.size_group == size
        ]
        if pairs:
            strata.append((size, [row for row, _ in pairs], [score for _, score in pairs]))

    output = []
    for stratum, subset, subset_scores in strata:
        labels = _labels(subset)
        metrics = classification_metrics(labels, subset_scores, threshold)
        details: dict[str, Any] = {
            "n_snapshots": len(subset),
            "n_repositories": len({row.repo_id for row in subset}),
            "positive_labels": sum(labels),
            "negative_labels": len(labels) - sum(labels),
            "decision_threshold": threshold,
        }
        bootstrap_rows = [
            {"repo_id": row.repo_id, "label": row.label, "score": score}
            for row, score in zip(subset, subset_scores, strict=True)
        ]
        intervals = repository_cluster_bootstrap(
            bootstrap_rows,
            threshold=threshold,
            seed=config.random_seed,
            resamples=config.bootstrap_resamples,
            confidence_level=config.confidence_level,
        )
        for metric_name in SCORED_METRICS:
            interval = intervals.get(metric_name)
            output.append(
                {
                    "split": "",
                    "stratum": stratum,
                    "metric": metric_name,
                    "value": metrics[metric_name],
                    "ci_low": interval[0] if interval else None,
                    "ci_high": interval[1] if interval else None,
                    "details": details,
                }
            )
        details["calibration_bins"] = calibration_bins(
            labels, subset_scores, config.calibration_bins
        )
        output.append(
            {
                "split": "",
                "stratum": stratum,
                "metric": "calibration_curve",
                "value": None,
                "ci_low": None,
                "ci_high": None,
                "details": details,
            }
        )
    return output


def _validation_selection_score(rows: list[ModelRow], scores: list[float]) -> dict[str, Any]:
    metrics = classification_metrics(_labels(rows), scores, 0.5)
    return metrics


def _fit_candidates(
    algorithm: str,
    train_rows: list[ModelRow],
    validation_rows: list[ModelRow],
    feature_names: tuple[str, ...],
    config: ModelingConfig,
) -> tuple[dict[str, Any], Pipeline, list[float], dict[str, Any]]:
    candidates = []
    for params in _grid(config, algorithm):
        model = _estimator(algorithm, params, config.random_seed)
        model.fit(_matrix(train_rows, feature_names), _labels(train_rows))
        scores = _probabilities(model, validation_rows, feature_names)
        metrics = _validation_selection_score(validation_rows, scores)
        pr_auc = metrics["pr_auc"]
        if pr_auc is None:
            raise ValueError("Validation PR-AUC is undefined; both classes are required")
        candidates.append(
            (float(pr_auc), float(metrics["brier_score"]), params, model, scores, metrics)
        )
    if not candidates:
        raise ValueError(f"Model grid for {algorithm} has no candidates")
    # PR-AUC is the frozen primary selection criterion; lower Brier and smaller
    # parameter encodings break ties without consulting the test set.
    candidates.sort(key=lambda item: (-item[0], item[1], json.dumps(item[2], sort_keys=True)))
    best = candidates[0]
    return best[2], best[3], best[4], best[5]


def _importance_rows(
    algorithm: str,
    model: Pipeline | None,
    rows: list[ModelRow],
    feature_names: tuple[str, ...],
    config: ModelingConfig,
) -> list[dict[str, Any]]:
    if model is None:
        return []
    if algorithm == "logistic_regression":
        coefficients = model.named_steps["classifier"].coef_[0]
        values = [float(value) for value in coefficients]
        method = "standardized_coefficient"
    elif algorithm in {"random_forest", "gradient_boosting"}:
        result = permutation_importance(
            model,
            _matrix(rows, feature_names),
            _labels(rows),
            scoring="average_precision",
            n_repeats=config.permutation_repeats,
            random_state=config.random_seed,
            n_jobs=1,
        )
        values = [float(value) for value in result.importances_mean]
        method = "validation_permutation"
    else:
        return []
    ranked = sorted(
        range(len(values)), key=lambda index: (-abs(values[index]), feature_names[index])
    )
    rank_by_index = {index: rank + 1 for rank, index in enumerate(ranked)}
    return [
        {"method": method, "feature_name": name, "value": value, "rank": rank_by_index[index]}
        for index, (name, value) in enumerate(zip(feature_names, values, strict=True))
    ]


def _version_row(
    connection: psycopg.Connection[Any],
    dataset: ModelDataset,
    family: str,
    algorithm: str,
    params: dict[str, Any],
    threshold: float,
    config: ModelingConfig,
    training_config: dict[str, Any],
    code_revision: str,
    artifact_path: str | None,
) -> int:
    params_hash = _digest(
        {
            "algorithm": algorithm,
            "params": params,
            "threshold": threshold,
            "random_seed": config.random_seed,
            "training_protocol": training_config,
            "code_revision": code_revision,
        }
    )
    row = connection.execute(
        """INSERT INTO model_versions (
                 dataset_version_id, feature_set_id, feature_set_name, algorithm,
                 params, params_hash, seed, label_config, training_config,
                 code_revision, artifact_path, validation_threshold, is_selected
             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
             ON CONFLICT (dataset_version_id, feature_set_id, feature_set_name,
                          algorithm, params_hash)
             DO UPDATE SET params = EXCLUDED.params,
                           label_config = EXCLUDED.label_config,
                           training_config = EXCLUDED.training_config,
                           code_revision = EXCLUDED.code_revision,
                           artifact_path = EXCLUDED.artifact_path,
                           validation_threshold = EXCLUDED.validation_threshold
             RETURNING id""",
        (
            dataset.dataset_version_id,
            dataset.feature_set_id,
            family,
            algorithm,
            Jsonb(params),
            params_hash,
            config.random_seed,
            Jsonb(dataset.label_config),
            Jsonb(training_config),
            code_revision,
            artifact_path,
            threshold,
        ),
    ).fetchone()
    return int(row[0])


def _persist_evaluation(
    connection: psycopg.Connection[Any], model_version_id: int, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    with connection.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO evaluation_results (
                     model_version_id, split, stratum, metric, value, ci_low, ci_high, details
                 ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                 ON CONFLICT (model_version_id, split, stratum, metric)
                 DO UPDATE SET value = EXCLUDED.value,
                               ci_low = EXCLUDED.ci_low,
                               ci_high = EXCLUDED.ci_high,
                               details = EXCLUDED.details""",
            [
                (
                    model_version_id,
                    row["split"],
                    row["stratum"],
                    row["metric"],
                    row["value"],
                    row["ci_low"],
                    row["ci_high"],
                    Jsonb(row["details"]),
                )
                for row in rows
            ],
        )


def _persist_importances(
    connection: psycopg.Connection[Any], model_version_id: int, rows: list[dict[str, Any]]
) -> None:
    connection.execute(
        "DELETE FROM feature_importances WHERE model_version_id = %s", (model_version_id,)
    )
    if not rows:
        return
    with connection.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO feature_importances
                   (model_version_id, method, feature_name, value, rank)
               VALUES (%s, %s, %s, %s, %s)""",
            [
                (model_version_id, row["method"], row["feature_name"], row["value"], row["rank"])
                for row in rows
            ],
        )


def train_and_evaluate(
    connection: psycopg.Connection[Any],
    config: ModelingConfig,
    *,
    dataset_version_id: int | None,
    feature_set_id: int | None,
    report_path: Path,
) -> dict[str, Any]:
    """Fit both feature families, select by validation, and report one test pass."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = load_model_dataset(
        connection,
        dataset_version_id=dataset_version_id,
        feature_set_id=feature_set_id,
    )
    code_revision = _identity()
    config_dump = config.model_dump(mode="json")
    training_config = {
        **config_dump,
        "primary_selection": (
            "highest validation PR-AUC; ties use lower validation Brier, then lexical params"
        ),
        "threshold_selection": "maximize validation F1; tied thresholds prefer the higher cutoff",
        "imputation": (
            "median fitted on train during tuning; refit on train plus validation "
            "for final evaluation"
        ),
        "activity_features": list(ACTIVITY_FEATURES),
        "extended_features": list(dataset.feature_names),
        "test_access": "one evaluation per final algorithm and feature family after selection",
    }
    split_rows = {
        split: [row for row in dataset.rows if row.split == split]
        for split in ("train", "validation", "test")
    }
    outcome_counts = {
        split: dict(Counter(row.label for row in rows)) for split, rows in split_rows.items()
    }
    for split, counts in outcome_counts.items():
        if set(counts) != {0, 1}:
            raise ValueError(f"Both outcome classes are required in the {split} split")

    family_runs: list[dict[str, Any]] = []
    for family, configured_names in FEATURE_FAMILIES.items():
        names = tuple(configured_names or dataset.feature_names)
        family_results = []
        for algorithm in ALGORITHMS:
            if algorithm == "threshold_baseline":
                params = {
                    "recent_window_days": 30,
                    "reference_window_days": 90,
                    "decline_cutoff": 0.5,
                }
                validation_scores = activity_decline_scores(
                    [row.features for row in split_rows["validation"]]
                )
                best_model = None
                validation_metrics = _validation_selection_score(
                    split_rows["validation"], validation_scores
                )
                threshold = 0.5
            else:
                params, best_model, validation_scores, validation_metrics = _fit_candidates(
                    algorithm,
                    split_rows["train"],
                    split_rows["validation"],
                    names,
                    config,
                )
                threshold = select_f1_threshold(
                    _labels(split_rows["validation"]), validation_scores
                )

            validation_rows = _model_report(
                split_rows["validation"], validation_scores, threshold, config
            )
            for row in validation_rows:
                row["split"] = "validation"

            importance_rows = _importance_rows(
                algorithm, best_model, split_rows["validation"], names, config
            )
            final_model = best_model
            if best_model is not None:
                training_rows = split_rows["train"] + split_rows["validation"]
                final_model = _estimator(algorithm, params, config.random_seed)
                final_model.fit(_matrix(training_rows, names), _labels(training_rows))
            test_scores = (
                activity_decline_scores([row.features for row in split_rows["test"]])
                if algorithm == "threshold_baseline"
                else _probabilities(final_model, split_rows["test"], names)
            )
            test_rows = _model_report(split_rows["test"], test_scores, threshold, config)
            for row in test_rows:
                row["split"] = "test"

            result = {
                "family": family,
                "algorithm": algorithm,
                "params": params,
                "threshold": threshold,
                "validation_pr_auc": validation_metrics["pr_auc"],
                "validation_brier_score": validation_metrics["brier_score"],
                "evaluation_rows": validation_rows + test_rows,
                "importance_rows": importance_rows,
                "final_model": final_model,
                "validation_scores": validation_scores,
                "test_scores": test_scores,
            }
            family_results.append(result)
        selected = max(
            family_results,
            key=lambda item: (
                item["validation_pr_auc"],
                -item["validation_brier_score"],
                -ALGORITHMS.index(item["algorithm"]),
            ),
        )
        family_runs.extend(family_results)
        selected["selected"] = True

    selected_activity = next(
        item for item in family_runs if item["family"] == "activity_only" and item.get("selected")
    )
    selected_extended = next(
        item for item in family_runs if item["family"] == "extended" and item.get("selected")
    )

    # Sensitivity targets reuse each validation-selected model's fixed test scores.
    # They do not refit, retune, or select models using test outcomes.
    test_outcomes = load_test_robustness_outcomes(connection, dataset.dataset_version_id)
    test_row_by_id = {row.snapshot_id: row for row in split_rows["test"]}
    if {outcome.snapshot_id for outcome in test_outcomes} != set(test_row_by_id):
        raise ValueError("Robustness outcomes do not match the labeled held-out test snapshots")
    thresholds = [float(value) for value in dataset.label_config["sensitivity_theta"]]
    minimum_reference = int(dataset.label_config["min_reference_commits"])
    robustness_report: dict[str, Any] = {}
    for item in (selected_activity, selected_extended):
        score_by_id = {
            row.snapshot_id: score
            for row, score in zip(split_rows["test"], item["test_scores"], strict=True)
        }
        variants = [
            (
                f"robustness_theta_{theta:g}",
                f"theta={theta:g}; non-bot default-branch commits",
                [
                    int(is_decline(outcome.reference_activity, outcome.future_activity, theta))
                    for outcome in test_outcomes
                ],
                [True] * len(test_outcomes),
            )
            for theta in thresholds
        ]
        variants.append(
            (
                "robustness_commits_plus_merged_prs",
                "theta=primary; non-bot default-branch commits plus merged pull requests",
                [
                    int(is_decline(
                        outcome.combined_reference_activity,
                        outcome.combined_future_activity,
                        float(dataset.label_config["theta"]),
                    ))
                    for outcome in test_outcomes
                ],
                [
                    outcome.combined_reference_activity >= minimum_reference
                    for outcome in test_outcomes
                ],
            )
        )
        for metric_prefix, definition, all_labels, eligible in variants:
            subset = [
                outcome
                for outcome, keep in zip(test_outcomes, eligible, strict=True)
                if keep
            ]
            labels = [label for label, keep in zip(all_labels, eligible, strict=True) if keep]
            scores = [score_by_id[outcome.snapshot_id] for outcome in subset]
            repository_ids = [outcome.repo_id for outcome in subset]
            if not labels:
                raise ValueError(
                    f"No eligible test outcomes for robustness variant {metric_prefix}"
                )
            metrics, intervals = robustness_metrics(
                labels,
                scores,
                repository_ids,
                decision_threshold=item["threshold"],
                seed=config.random_seed,
                resamples=config.bootstrap_resamples,
                confidence_level=config.confidence_level,
            )
            details = {
                "analysis": "fixed validation-selected model scores; target-label sensitivity only",
                "target_definition": definition,
                "n_snapshots": len(subset),
                "n_excluded_low_reference_activity": len(test_outcomes) - len(subset),
                "n_repositories": len(set(repository_ids)),
                "positive_labels": sum(labels),
                "negative_labels": len(labels) - sum(labels),
                "decision_threshold_from_validation": item["threshold"],
                "confidence_level": config.confidence_level,
                "bootstrap_resamples": config.bootstrap_resamples,
            }
            for metric_name in SCORED_METRICS:
                interval = intervals.get(metric_name)
                item["evaluation_rows"].append(
                    {
                        "split": "test",
                        "stratum": "overall",
                        "metric": f"{metric_prefix}_{metric_name}",
                        "value": metrics[metric_name],
                        "ci_low": interval[0] if interval else None,
                        "ci_high": interval[1] if interval else None,
                        "details": details,
                    }
                )
            robustness_report.setdefault(item["family"], {})[metric_prefix] = {
                **{metric: metrics[metric] for metric in SCORED_METRICS},
                "n_snapshots": len(subset),
                "n_repositories": len(set(repository_ids)),
            }

    paired_comparison = paired_repository_cluster_bootstrap(
        [
            {
                "snapshot_id": row.snapshot_id,
                "repo_id": row.repo_id,
                "label": row.label,
                "score": score,
            }
            for row, score in zip(split_rows["test"], selected_activity["test_scores"], strict=True)
        ],
        [
            {
                "snapshot_id": row.snapshot_id,
                "repo_id": row.repo_id,
                "label": row.label,
                "score": score,
            }
            for row, score in zip(split_rows["test"], selected_extended["test_scores"], strict=True)
        ],
        baseline_threshold=selected_activity["threshold"],
        extended_threshold=selected_extended["threshold"],
        seed=config.random_seed,
        resamples=config.bootstrap_resamples,
        confidence_level=config.confidence_level,
    )
    comparison_details = {
        "comparison": "extended minus activity_only",
        "activity_only_algorithm": selected_activity["algorithm"],
        "extended_algorithm": selected_extended["algorithm"],
        "n_snapshots": len(split_rows["test"]),
        "n_repositories": len({row.repo_id for row in split_rows["test"]}),
        "confidence_level": config.confidence_level,
        "bootstrap_resamples": config.bootstrap_resamples,
    }
    for metric_name, values in paired_comparison.items():
        selected_extended["evaluation_rows"].append(
            {
                "split": "test",
                "stratum": "overall",
                "metric": f"paired_delta_{metric_name}_vs_activity_only",
                "value": values["difference"],
                "ci_low": values["ci_low"],
                "ci_high": values["ci_high"],
                "details": comparison_details,
            }
        )

    report_models = []
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        for family in FEATURE_FAMILIES:
            connection.execute(
                "UPDATE model_versions SET is_selected = FALSE "
                "WHERE dataset_version_id = %s AND feature_set_id = %s AND feature_set_name = %s",
                (dataset.dataset_version_id, dataset.feature_set_id, family),
            )

        for item in family_runs:
            params_hash = _digest(
                {
                    "algorithm": item["algorithm"],
                    "params": item["params"],
                    "threshold": item["threshold"],
                    "random_seed": config.random_seed,
                    "training_protocol": training_config,
                    "code_revision": code_revision,
                }
            )
            artifact_path = None
            model = item["final_model"]
            if model is not None:
                relative = (
                    Path("pipeline/artifacts")
                    / str(dataset.dataset_version_id)
                    / item["family"]
                    / f"{item['algorithm']}-{params_hash}.joblib"
                )
                absolute = _root() / relative
                absolute.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(model, absolute)
                artifact_path = relative.as_posix()
            version_id = _version_row(
                connection,
                dataset,
                item["family"],
                item["algorithm"],
                item["params"],
                item["threshold"],
                config,
                training_config,
                code_revision,
                artifact_path,
            )
            if item.get("selected"):
                connection.execute(
                    "UPDATE model_versions SET is_selected = TRUE WHERE id = %s",
                    (version_id,),
                )
            _persist_evaluation(connection, version_id, item["evaluation_rows"])
            _persist_importances(connection, version_id, item["importance_rows"])
            report_models.append(
                {
                    "model_version_id": version_id,
                    "family": item["family"],
                    "algorithm": item["algorithm"],
                    "params": item["params"],
                    "validation_threshold": item["threshold"],
                    "validation_pr_auc": item["validation_pr_auc"],
                    "validation_brier_score": item["validation_brier_score"],
                    "test_metrics": {
                        row["metric"]: row["value"]
                        for row in item["evaluation_rows"]
                        if row["split"] == "test" and row["stratum"] == "overall"
                    },
                    "selected": bool(item.get("selected")),
                    "artifact_path": artifact_path,
                }
            )

    report = {
        "dataset_version_id": dataset.dataset_version_id,
        "dataset_version_hash": dataset.dataset_hash,
        "feature_set_id": dataset.feature_set_id,
        "feature_set_hash": dataset.feature_set_hash,
        "label_config": dataset.label_config,
        "training_config": training_config,
        "eligible_rows_by_split": {
            split: {
                "snapshots": len(rows),
                "repositories": len({row.repo_id for row in rows}),
                "positive": sum(row.label for row in rows),
                "negative": len(rows) - sum(row.label for row in rows),
            }
            for split, rows in split_rows.items()
        },
        "models": report_models,
        "paired_test_comparison_extended_minus_activity_only": paired_comparison,
        "test_target_robustness": robustness_report,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

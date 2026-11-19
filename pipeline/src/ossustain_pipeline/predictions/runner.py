"""Generate and explain predictions for the latest usable cohort snapshots."""

import json
from math import isfinite, nan
from pathlib import Path
from statistics import median
from typing import Any

import joblib
import psycopg
from psycopg.types.json import Jsonb

from ossustain_pipeline.modeling.core import activity_decline_scores
from ossustain_pipeline.modeling.data import ACTIVITY_FEATURES, ModelRow
from ossustain_pipeline.modeling.runner import _estimator
from ossustain_pipeline.predictions.core import (
    activity_baseline_score,
    local_feature_deltas,
    risk_category,
    validation_risk_cutoffs,
)

TOP_INDICATORS = 5


def _root() -> Path:
    return Path(__file__).resolve().parents[4]


def _feature_names(
    connection: psycopg.Connection[Any], feature_set_id: int, family: str
) -> tuple[str, ...]:
    if family == "activity_only":
        return ACTIVITY_FEATURES
    rows = connection.execute(
        """SELECT feature_name FROM feature_definitions
           WHERE feature_set_id = %s ORDER BY feature_name""",
        (feature_set_id,),
    ).fetchall()
    return tuple(row[0] for row in rows)


def _choose_model(
    connection: psycopg.Connection[Any], dataset_version_id: int | None
) -> tuple[Any, ...]:
    row = connection.execute(
        """SELECT version.id, version.dataset_version_id, version.feature_set_id,
                  version.feature_set_name, version.algorithm, version.artifact_path,
                  dataset.version_hash, dataset.cohort_name, version.validation_threshold,
                  result.value AS validation_pr_auc, version.params, version.seed
           FROM model_versions version
           JOIN dataset_versions dataset ON dataset.id = version.dataset_version_id
           JOIN evaluation_results result
             ON result.model_version_id = version.id
            AND result.split = 'validation' AND result.stratum = 'overall'
            AND result.metric = 'pr_auc'
           WHERE version.is_selected
             AND (%s IS NULL OR version.dataset_version_id = %s)
           ORDER BY version.dataset_version_id DESC, result.value DESC, version.id ASC
           LIMIT 1""",
        (dataset_version_id, dataset_version_id),
    ).fetchone()
    if row is None:
        raise ValueError("No validation-selected model is available for prediction")
    return row


def _load_artifact(path: str) -> Any:
    root = _root().resolve()
    artifact = (root / path).resolve()
    try:
        artifact.relative_to((root / "pipeline" / "artifacts").resolve())
    except ValueError as error:
        raise ValueError("Model artifact path is outside pipeline/artifacts") from error
    if not artifact.is_file():
        raise ValueError(f"Model artifact is missing: {path}; rerun train for this model version")
    return joblib.load(artifact)


def _as_features(raw: Any, names: tuple[str, ...]) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError("Snapshot feature payload is not an object")
    values: dict[str, float] = {}
    for name in names:
        value = raw.get(name)
        if value is None:
            values[name] = nan
        else:
            values[name] = float(value)
            if not isfinite(values[name]):
                raise ValueError(f"Feature {name} is not finite")
    return values


def _load_training_rows(
    connection: psycopg.Connection[Any],
    *,
    dataset_version_id: int,
    feature_set_id: int,
    names: tuple[str, ...],
) -> tuple[dict[str, Any], list[ModelRow]]:
    """Load only training and validation labels; the test split is never queried."""
    dataset_config = connection.execute(
        "SELECT config FROM dataset_versions WHERE id = %s", (dataset_version_id,)
    ).fetchone()
    if dataset_config is None:
        raise ValueError(f"Dataset version {dataset_version_id} does not exist")
    config = dataset_config[0]
    definitions = {
        row[0]
        for row in connection.execute(
            "SELECT feature_name FROM feature_definitions WHERE feature_set_id = %s",
            (feature_set_id,),
        ).fetchall()
    }
    if not set(names).issubset(definitions):
        raise ValueError("Selected model inputs are missing from the registered feature dictionary")
    stored_rows = connection.execute(
        """SELECT snapshot.id, snapshot.repo_id, snapshot.prediction_date, snapshot.split,
                  repository.size_group, snapshot.label, snapshot_features.features
           FROM snapshots snapshot
           JOIN repositories repository ON repository.id = snapshot.repo_id
           JOIN snapshot_features
             ON snapshot_features.snapshot_id = snapshot.id
            AND snapshot_features.dataset_version_id = snapshot.dataset_version_id
            AND snapshot_features.feature_set_id = %s
           WHERE snapshot.dataset_version_id = %s
             AND snapshot.label_status = 'labeled'
             AND snapshot.split IN ('train', 'validation')
           ORDER BY snapshot.prediction_date, snapshot.repo_id, snapshot.id""",
        (feature_set_id, dataset_version_id),
    ).fetchall()
    rows = [
        ModelRow(
            int(snapshot_id),
            int(repo_id),
            prediction_date,
            split,
            size_group,
            int(label),
            _as_features(features, names),
        )
        for snapshot_id, repo_id, prediction_date, split, size_group, label, features in stored_rows
    ]
    if not any(row.split == "train" for row in rows) or not any(
        row.split == "validation" for row in rows
    ):
        raise ValueError("Predictions require both train and validation snapshot rows")
    return config["experiment"]["label"], rows


def _scores(model: Any, rows: list[ModelRow], names: tuple[str, ...]) -> list[float]:
    matrix = [[row.features[name] for name in names] for row in rows]
    positive_index = list(model.classes_).index(1)
    return [float(value) for value in model.predict_proba(matrix)[:, positive_index]]


def _inference_repositories(
    connection: psycopg.Connection[Any],
    *,
    dataset_version_id: int,
    cohort_name: str,
    feature_set_id: int,
    names: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT repository.id, repository.full_name, latest.snapshot_id,
                  latest.prediction_date, latest.reference_activity,
                  latest.label_status, latest.features, latest.missing_flags
           FROM cohorts cohort
           JOIN cohort_memberships membership ON membership.cohort_id = cohort.id
           JOIN repositories repository ON repository.id = membership.repository_id
           LEFT JOIN LATERAL (
               SELECT snapshot.id AS snapshot_id, snapshot.prediction_date,
                      snapshot.reference_activity, snapshot.label_status,
                      snapshot_features.features, snapshot_features.missing_flags
               FROM snapshots snapshot
               LEFT JOIN snapshot_features
                 ON snapshot_features.snapshot_id = snapshot.id
                AND snapshot_features.dataset_version_id = snapshot.dataset_version_id
                AND snapshot_features.feature_set_id = %s
               WHERE snapshot.dataset_version_id = %s
                 AND snapshot.repo_id = repository.id
               ORDER BY snapshot.prediction_date DESC, snapshot.id DESC
               LIMIT 1
           ) latest ON TRUE
           WHERE cohort.name = %s
           ORDER BY repository.id""",
        (feature_set_id, dataset_version_id, cohort_name),
    ).fetchall()
    output = []
    for repo_id, full_name, snapshot_id, date, activity, label_status, raw, missing in rows:
        item: dict[str, Any] = {
            "repo_id": int(repo_id),
            "full_name": full_name,
            "snapshot_id": int(snapshot_id) if snapshot_id is not None else None,
            "prediction_date": date,
            "reference_activity": activity,
            "label_status": label_status,
            "raw_features": raw,
            "missing_flags": missing or {},
        }
        if snapshot_id is None:
            item["skip_reason"] = "no_snapshot_in_dataset"
        elif raw is None:
            item["skip_reason"] = "latest_snapshot_has_no_feature_record"
        else:
            try:
                item["features"] = _as_features(raw, names)
            except (TypeError, ValueError) as error:
                item["skip_reason"] = f"invalid_feature_record: {error}"
        output.append(item)
    return output


def _write_outcome(
    connection: psycopg.Connection[Any],
    *,
    model_version_id: int,
    dataset_version_id: int,
    item: dict[str, Any],
    prediction_id: int | None = None,
) -> None:
    status = "predicted" if prediction_id is not None else "skipped"
    connection.execute(
        """INSERT INTO prediction_outcomes (
                   model_version_id, dataset_version_id, repo_id, snapshot_id,
                   prediction_id, status, reason
               ) VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (model_version_id, repo_id) DO UPDATE SET
                   dataset_version_id = EXCLUDED.dataset_version_id,
                   snapshot_id = EXCLUDED.snapshot_id,
                   prediction_id = EXCLUDED.prediction_id,
                   status = EXCLUDED.status,
                   reason = EXCLUDED.reason,
                   created_at = now()""",
        (
            model_version_id,
            dataset_version_id,
            item["repo_id"],
            item["snapshot_id"],
            prediction_id,
            status,
            item.get("skip_reason"),
        ),
    )


def generate_predictions(
    connection: psycopg.Connection[Any],
    *,
    dataset_version_id: int | None,
    report_path: Path,
) -> dict[str, Any]:
    """Select using validation PR-AUC only and score each cohort's latest snapshot."""
    selected = _choose_model(connection, dataset_version_id)
    (
        model_version_id,
        version_id,
        feature_set_id,
        family,
        algorithm,
        artifact_path,
        dataset_hash,
        cohort_name,
        validation_threshold,
        validation_pr_auc,
        model_params,
        random_seed,
    ) = selected
    version_id = int(version_id)
    feature_set_id = int(feature_set_id)
    model_version_id = int(model_version_id)
    names = _feature_names(connection, feature_set_id, family)
    if not names:
        raise ValueError("The selected feature set has no registered model inputs")
    model = _load_artifact(artifact_path) if artifact_path else None

    label_config, modeling_rows = _load_training_rows(
        connection,
        dataset_version_id=version_id,
        feature_set_id=feature_set_id,
        names=names,
    )
    train_rows = [row for row in modeling_rows if row.split == "train"]
    validation_rows = [row for row in modeling_rows if row.split == "validation"]
    validation_model = None
    if algorithm != "threshold_baseline":
        validation_model = _estimator(algorithm, model_params, int(random_seed))
        validation_matrix = [[row.features[name] for name in names] for row in train_rows]
        validation_model.fit(validation_matrix, [row.label for row in train_rows])
    validation_scores = (
        activity_decline_scores([row.features for row in validation_rows])
        if validation_model is None
        else _scores(validation_model, validation_rows, names)
    )
    cutoffs = validation_risk_cutoffs(validation_scores)
    cohort_rows = _inference_repositories(
        connection,
        dataset_version_id=version_id,
        cohort_name=cohort_name,
        feature_set_id=feature_set_id,
        names=names,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_rows: list[dict[str, Any]] = []
    with connection.transaction():
        connection.execute(
            """UPDATE model_versions SET risk_low_cutoff = %s, risk_high_cutoff = %s
               WHERE id = %s""",
            (cutoffs.low, cutoffs.high, model_version_id),
        )
        for item in cohort_rows:
            if item.get("skip_reason"):
                _write_outcome(
                    connection,
                    model_version_id=model_version_id,
                    dataset_version_id=version_id,
                    item=item,
                )
                output_rows.append(
                    {
                        "repository": item["full_name"],
                        "status": "skipped",
                        "reason": item["skip_reason"],
                    }
                )
                continue
            values = item["features"]
            score = (
                activity_baseline_score(values)
                if model is None
                else _scores(
                    model,
                    [
                        ModelRow(
                            0, item["repo_id"], item["prediction_date"], "inference", "", 0, values
                        )
                    ],
                    names,
                )[0]
            )
            flags = []
            min_activity = int(label_config.get("min_reference_commits", 20))
            if item["reference_activity"] < min_activity:
                flags.append("low_activity")
            missing_flags = item["missing_flags"]
            if any(
                values[name] != values[name] or bool(missing_flags.get(name, False))
                for name in names
            ):
                flags.append("missing_data")
            category = risk_category(score, cutoffs)
            with connection.transaction():
                row = connection.execute(
                    """INSERT INTO predictions (
                               model_version_id, snapshot_id, dataset_version_id,
                               risk_score, risk_level, prediction_date, limitation_flags
                           ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (model_version_id, snapshot_id)
                           WHERE model_version_id IS NOT NULL
                           DO UPDATE SET risk_score = EXCLUDED.risk_score,
                                         risk_level = EXCLUDED.risk_level,
                                         prediction_date = EXCLUDED.prediction_date,
                                         limitation_flags = EXCLUDED.limitation_flags
                           RETURNING id""",
                    (
                        model_version_id,
                        item["snapshot_id"],
                        version_id,
                        score,
                        category,
                        item["prediction_date"],
                        Jsonb(flags),
                    ),
                ).fetchone()
                prediction_id = int(row[0])
                item["skip_reason"] = None
                _write_outcome(
                    connection,
                    model_version_id=model_version_id,
                    dataset_version_id=version_id,
                    item=item,
                    prediction_id=prediction_id,
                )
            output_rows.append(
                {
                    "repository": item["full_name"],
                    "status": "predicted",
                    "prediction_id": prediction_id,
                    "snapshot_id": item["snapshot_id"],
                    "prediction_date": item["prediction_date"].isoformat(),
                    "probability": score,
                    "risk_category": category,
                    "limitation_flags": flags,
                }
            )
    report = {
        "dataset_version_id": version_id,
        "dataset_version_hash": dataset_hash,
        "model_version_id": model_version_id,
        "algorithm": algorithm,
        "feature_set": family,
        "selection": (
            "highest validation PR-AUC among family-selected models; test is not consulted"
        ),
        "validation_pr_auc": validation_pr_auc,
        "validation_decision_threshold": validation_threshold,
        "risk_category_method": "validation probability tertiles; persisted on the model version",
        "risk_low_cutoff": cutoffs.low,
        "risk_high_cutoff": cutoffs.high,
        "repositories": output_rows,
        "predicted_count": sum(row["status"] == "predicted" for row in output_rows),
        "skipped_count": sum(row["status"] == "skipped" for row in output_rows),
    }
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def generate_explanations(
    connection: psycopg.Connection[Any],
    *,
    dataset_version_id: int | None,
    report_path: Path,
) -> dict[str, Any]:
    """Persist top one-feature validation-median substitutions for stored predictions."""
    selected = _choose_model(connection, dataset_version_id)
    model_version_id, version_id, feature_set_id, family, algorithm, artifact_path = selected[:6]
    model_version_id = int(model_version_id)
    version_id = int(version_id)
    feature_set_id = int(feature_set_id)
    names = _feature_names(connection, feature_set_id, family)
    model = _load_artifact(artifact_path) if artifact_path else None
    _, modeling_rows = _load_training_rows(
        connection,
        dataset_version_id=version_id,
        feature_set_id=feature_set_id,
        names=names,
    )
    validation_rows = [row for row in modeling_rows if row.split == "validation"]
    reference_values = {
        name: median(values)
        for name in names
        if (
            values := [
                row.features[name] for row in validation_rows if isfinite(row.features[name])
            ]
        )
    }
    rows = connection.execute(
        """SELECT prediction.id, snapshot.repo_id, snapshot.id,
                  snapshot_features.features
           FROM prediction_outcomes outcome
           JOIN predictions prediction ON prediction.id = outcome.prediction_id
           JOIN snapshots snapshot ON snapshot.id = outcome.snapshot_id
           JOIN snapshot_features
             ON snapshot_features.snapshot_id = snapshot.id
            AND snapshot_features.feature_set_id = %s
           WHERE outcome.model_version_id = %s AND outcome.status = 'predicted'
           ORDER BY snapshot.repo_id, snapshot.prediction_date""",
        (feature_set_id, model_version_id),
    ).fetchall()
    explained = 0
    report_items = []
    with connection.transaction():
        for prediction_id, repo_id, snapshot_id, raw in rows:
            values = _as_features(raw, names)
            indicators = local_feature_deltas(model, names, values, reference_values)[
                :TOP_INDICATORS
            ]
            connection.execute(
                "DELETE FROM prediction_explanations WHERE prediction_id = %s", (prediction_id,)
            )
            for rank, indicator in enumerate(indicators, start=1):
                indicator["rank"] = rank
                direction_text = {
                    "increases_risk": "is associated with a higher model risk score",
                    "decreases_risk": "is associated with a lower model risk score",
                    "neutral": "does not change the model risk score in this comparison",
                }[indicator["direction"]]
                indicator["description"] = (
                    f"The observed value {direction_text} than substituting the validation median. "
                    "This is a model association, not a causal effect."
                )
                connection.execute(
                    """INSERT INTO prediction_explanations (
                               prediction_id, feature_name, feature_value, reference_value,
                               probability_delta, direction, rank, description
                           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        prediction_id,
                        indicator["feature_name"],
                        indicator["feature_value"],
                        indicator["reference_value"],
                        indicator["probability_delta"],
                        indicator["direction"],
                        rank,
                        indicator["description"],
                    ),
                )
            explained += 1
            report_items.append(
                {"repo_id": int(repo_id), "snapshot_id": int(snapshot_id), "indicators": indicators}
            )
    report = {
        "dataset_version_id": version_id,
        "model_version_id": model_version_id,
        "algorithm": algorithm,
        "feature_set": family,
        "method": (
            "one-feature-at-a-time substitution with validation medians; associational, not causal"
        ),
        "predictions_explained": explained,
        "top_indicators_per_prediction": TOP_INDICATORS,
        "results": report_items,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report

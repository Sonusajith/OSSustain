from datetime import date
from pathlib import Path

import pytest

from ossustain_pipeline.modeling.config import load_modeling_config
from ossustain_pipeline.modeling.core import (
    activity_decline_scores,
    calibration_bins,
    classification_metrics,
    paired_repository_cluster_bootstrap,
    repository_cluster_bootstrap,
    robustness_metrics,
    select_f1_threshold,
)
from ossustain_pipeline.modeling.data import ModelRow, validate_split_chronology
from ossustain_pipeline.modeling.runner import _estimator
from ossustain_pipeline.predictions.runner import _shap_values


def test_hand_checked_binary_classification_metrics():
    metrics = classification_metrics([0, 1, 0, 1], [0.1, 0.8, 0.4, 0.6], 0.5)
    assert metrics["pr_auc"] == 1
    assert metrics["roc_auc"] == 1
    assert metrics["precision"] == 1
    assert metrics["recall"] == 1
    assert metrics["f1"] == 1
    assert metrics["brier_score"] == pytest.approx(0.0925)
    assert metrics["true_positives"] == 2
    assert metrics["true_negatives"] == 2


def test_auc_handles_ties_and_missing_positive_class():
    tied = classification_metrics([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5], 0.5)
    assert tied["pr_auc"] == 0.5
    assert tied["roc_auc"] == 0.5

    no_positives = classification_metrics([0, 0], [0.1, 0.9], 0.5)
    assert no_positives["pr_auc"] is None
    assert no_positives["roc_auc"] is None
    assert no_positives["recall"] is None
    assert no_positives["f1"] is None


def test_validation_cutoff_selects_maximum_f1_with_deterministic_tie_break():
    assert select_f1_threshold([0, 1, 0, 1], [0.2, 0.7, 0.4, 0.6]) == 0.6


def test_calibration_bins_keep_counts_and_probability_one_in_last_bin():
    rows = calibration_bins([0, 1, 1], [0.0, 0.5, 1.0], bin_count=2)
    assert rows == [
        {"bin": 0, "count": 1, "mean_probability": 0.0, "observed_rate": 0.0},
        {"bin": 1, "count": 2, "mean_probability": 0.75, "observed_rate": 1.0},
    ]


def test_repository_cluster_bootstrap_is_reproducible_and_clustered():
    rows = [
        {"repo_id": 1, "label": 0, "score": 0.1},
        {"repo_id": 1, "label": 1, "score": 0.9},
        {"repo_id": 2, "label": 0, "score": 0.2},
        {"repo_id": 2, "label": 1, "score": 0.8},
        {"repo_id": 3, "label": 0, "score": 0.3},
        {"repo_id": 3, "label": 1, "score": 0.7},
    ]
    first = repository_cluster_bootstrap(rows, threshold=0.5, seed=42, resamples=100)
    second = repository_cluster_bootstrap(rows, threshold=0.5, seed=42, resamples=100)
    assert first == second
    assert first["pr_auc"] == (1.0, 1.0)


def test_robustness_metrics_use_fixed_scores_and_repository_clusters():
    metrics, intervals = robustness_metrics(
        [0, 1, 0, 1],
        [0.2, 0.8, 0.3, 0.7],
        [11, 11, 22, 22],
        decision_threshold=0.5,
        seed=42,
        resamples=100,
        confidence_level=0.95,
    )
    assert metrics["pr_auc"] == 1
    assert metrics["f1"] == 1
    assert intervals["pr_auc"] == (1.0, 1.0)


def test_shap_attributions_reconcile_to_probability_with_validation_background():
    names = ("activity", "collaboration")
    model = _estimator(
        "logistic_regression", {"c": 1.0, "class_weight": "balanced"}, seed=42
    )
    train_matrix = [[0.0, 0.0], [1.0, 0.2], [2.0, 0.5], [3.0, 1.0]]
    model.fit(train_matrix, [0, 0, 1, 1])
    validation_rows = [
        ModelRow(index, index, date(2024, 1, index), "validation", "small", index % 2,
                 dict(zip(names, values, strict=True)))
        for index, values in enumerate(train_matrix, start=1)
    ]
    predicted = {"activity": 1.5, "collaboration": 0.4}
    bases, attributions = _shap_values(model, names, validation_rows, [predicted])
    probability = model.predict_proba([[predicted[name] for name in names]])[0][1]
    assert len(attributions) == 1
    assert len(attributions[0]) == len(names)
    assert bases[0] + sum(attributions[0]) == pytest.approx(probability, abs=1e-5)


def test_paired_cluster_bootstrap_compares_the_same_snapshot_rows():
    rows = [
        {"snapshot_id": 1, "repo_id": 11, "label": 0, "score": 0.1},
        {"snapshot_id": 2, "repo_id": 11, "label": 1, "score": 0.9},
        {"snapshot_id": 3, "repo_id": 22, "label": 0, "score": 0.2},
        {"snapshot_id": 4, "repo_id": 22, "label": 1, "score": 0.8},
    ]
    result = paired_repository_cluster_bootstrap(
        rows,
        rows,
        baseline_threshold=0.5,
        extended_threshold=0.5,
        seed=9,
        resamples=100,
    )
    assert result["pr_auc"] == {"difference": 0.0, "ci_low": 0.0, "ci_high": 0.0}


def test_recent_activity_baseline_uses_only_historical_counts():
    scores = activity_decline_scores(
        [
            {"commits_30d": 5, "commits_90d": 30},
            {"commits_30d": 10, "commits_90d": 30},
            {"commits_30d": 15, "commits_90d": 30},
        ]
    )
    assert scores == [0.5, 0.0, 0.0]


def test_model_grid_configuration_is_frozen_and_loads():
    config = load_modeling_config(Path("config/modeling.yaml"))
    assert config.random_seed == 42
    assert config.selection_metric == "pr_auc"
    assert config.bootstrap_resamples == 2000
    assert config.models.random_forest.n_estimators == [200]


def test_estimators_are_reproducible_and_imputer_fits_on_training_rows():
    train = [[0.0], [1.0], [2.0], [None], [5.0], [6.0]]
    labels = [0, 0, 0, 1, 1, 1]
    params = {
        "logistic_regression": {"c": 1.0, "class_weight": "balanced"},
        "random_forest": {
            "n_estimators": 20,
            "max_depth": 2,
            "min_samples_leaf": 1,
            "class_weight": "balanced",
        },
        "gradient_boosting": {
            "n_estimators": 20,
            "learning_rate": 0.05,
            "max_depth": 1,
        },
    }
    for algorithm, candidate in params.items():
        first = _estimator(algorithm, candidate, seed=42).fit(train, labels)
        second = _estimator(algorithm, candidate, seed=42).fit(train, labels)
        assert first.named_steps["imputer"].statistics_[0] == 2
        assert first.predict_proba([[100.0]]) == pytest.approx(second.predict_proba([[100.0]]))


def test_split_order_must_be_strict_and_chronological():
    def row(day: str, split: str) -> ModelRow:
        return ModelRow(1, 1, date.fromisoformat(day), split, "small", 0, {})

    valid = [
        row("2023-06-30", "train"),
        row("2023-10-23", "validation"),
        row("2024-10-17", "test"),
    ]
    validate_split_chronology(valid)
    with pytest.raises(ValueError, match="chronological"):
        validate_split_chronology([valid[0], row("2023-05-30", "validation"), valid[2]])

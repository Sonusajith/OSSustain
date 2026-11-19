from math import isclose

import pytest

from ossustain_pipeline.predictions.core import (
    local_feature_deltas,
    risk_category,
    validation_risk_cutoffs,
)


class LinearProbabilityModel:
    classes_ = [0, 1]

    def predict_proba(self, rows):
        return [
            [1 - min(1, max(0, 0.2 + 0.1 * rows[0][0])), min(1, max(0, 0.2 + 0.1 * rows[0][0]))]
        ]


def test_risk_cutoffs_are_derived_from_validation_scores_and_ordered():
    cutoffs = validation_risk_cutoffs([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])

    assert isclose(cutoffs.low, 0.2666666667)
    assert isclose(cutoffs.high, 0.4333333333)
    assert risk_category(cutoffs.low, cutoffs) == "low"
    assert risk_category((cutoffs.low + cutoffs.high) / 2, cutoffs) == "medium"
    assert risk_category(0.9, cutoffs) == "high"


@pytest.mark.parametrize("scores", [[], [0.1, 0.2], [float("nan"), 0.5, 0.8]])
def test_risk_cutoffs_require_three_finite_probabilities(scores):
    with pytest.raises(ValueError):
        validation_risk_cutoffs(scores)


def test_local_indicator_uses_validation_reference_and_associational_direction():
    rows = local_feature_deltas(
        LinearProbabilityModel(),
        ("feature",),
        {"feature": 2.0},
        {"feature": 1.0},
    )

    assert rows[0]["direction"] == "increases_risk"
    assert rows[0]["feature_value"] == 2.0
    assert rows[0]["reference_value"] == 1.0
    assert isclose(rows[0]["probability_delta"], 0.1)


def test_fixed_activity_baseline_handles_zero_recent_activity():
    rows = local_feature_deltas(
        None,
        ("commits_30d", "commits_90d"),
        {"commits_30d": 0.0, "commits_90d": 0.0},
        {"commits_30d": 1.0, "commits_90d": 10.0},
    )

    assert rows
    assert all(row["direction"] in {"increases_risk", "decreases_risk", "neutral"} for row in rows)

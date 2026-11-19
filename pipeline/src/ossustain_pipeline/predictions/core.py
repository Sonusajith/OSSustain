"""Pure helpers for validation-derived risk categories and local indicators."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import quantiles
from typing import Any


@dataclass(frozen=True)
class RiskCutoffs:
    low: float
    high: float


def validation_risk_cutoffs(scores: list[float]) -> RiskCutoffs:
    """Use validation-score tertiles as the persisted low/medium/high boundaries."""
    if not scores or any(not isfinite(score) or not 0 <= score <= 1 for score in scores):
        raise ValueError("Validation scores must be finite probabilities")
    if len(scores) < 3:
        raise ValueError("At least three validation scores are required for risk categories")
    lower, upper = quantiles(scores, n=3, method="inclusive")
    return RiskCutoffs(float(lower), float(upper))


def risk_category(score: float, cutoffs: RiskCutoffs) -> str:
    if not isfinite(score) or not 0 <= score <= 1:
        raise ValueError("Prediction score must be a finite probability")
    if score <= cutoffs.low:
        return "low"
    if score <= cutoffs.high:
        return "medium"
    return "high"


def local_feature_deltas(
    model: Any | None,
    feature_names: tuple[str, ...],
    values: dict[str, float],
    reference_values: dict[str, float],
) -> list[dict[str, Any]]:
    """Measure one-feature substitutions around validation medians, not causal effects."""
    if model is None:
        actual_score = activity_baseline_score(values)
    else:
        actual_score = float(model.predict_proba([[values[name] for name in feature_names]])[0][1])

    rows: list[dict[str, Any]] = []
    for name in feature_names:
        current = values[name]
        reference = reference_values.get(name)
        if reference is None or not isfinite(reference):
            continue
        if model is None:
            counterfactual = dict(values)
            counterfactual[name] = reference
            reference_score = activity_baseline_score(counterfactual)
        else:
            counterfactual_values = [values[feature] for feature in feature_names]
            counterfactual_values[feature_names.index(name)] = reference
            reference_score = float(model.predict_proba([counterfactual_values])[0][1])
        delta = actual_score - reference_score
        rows.append(
            {
                "feature_name": name,
                "feature_value": current if isfinite(current) else None,
                "reference_value": reference,
                "probability_delta": delta,
                "direction": (
                    "increases_risk"
                    if delta > 1e-12
                    else "decreases_risk"
                    if delta < -1e-12
                    else "neutral"
                ),
            }
        )
    rows.sort(key=lambda row: (-abs(row["probability_delta"]), row["feature_name"]))
    return rows


def activity_baseline_score(values: dict[str, float]) -> float:
    """Fixed activity rule; zero recent reference activity maps to maximum risk."""
    recent = values["commits_30d"]
    reference = values["commits_90d"]
    if not isfinite(recent) or not isfinite(reference):
        raise ValueError("Activity baseline requires non-missing 30-day and 90-day commit counts")
    if reference <= 0:
        return 1.0
    return min(1.0, max(0.0, 1.0 - 3.0 * recent / reference))

"""Dependency-free metric, threshold, and repository-cluster bootstrap helpers."""

from collections import defaultdict
from math import isfinite
from random import Random
from typing import Any


def _validate_binary_inputs(
    labels: list[int], scores: list[float]
) -> tuple[list[int], list[float]]:
    if len(labels) != len(scores) or not labels:
        raise ValueError("labels and scores must have equal, non-zero length")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must contain only 0 and 1")
    if any(not isfinite(score) or score < 0 or score > 1 for score in scores):
        raise ValueError("scores must be finite probabilities in [0, 1]")
    return labels, scores


def classification_metrics(
    labels: list[int], scores: list[float], threshold: float
) -> dict[str, float | int | None]:
    """Calculate average precision, ROC AUC, threshold metrics, and Brier score."""
    labels, scores = _validate_binary_inputs(labels, scores)
    if not isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and in [0, 1]")

    positives = sum(labels)
    negatives = len(labels) - positives
    ranked = sorted(zip(scores, labels, strict=True), reverse=True)
    tp = fp = 0
    previous_recall = 0.0
    average_precision = 0.0
    index = 0
    while index < len(ranked):
        end = index
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        group_pos = sum(label for _, label in ranked[index:end])
        group_neg = end - index - group_pos
        tp += group_pos
        fp += group_neg
        if positives:
            recall = tp / positives
            average_precision += (recall - previous_recall) * tp / (tp + fp)
            previous_recall = recall
        index = end

    pair_wins = 0.0
    lower_scored_negatives = 0
    ascending = sorted(ranked)
    index = 0
    while index < len(ascending):
        end = index
        while end < len(ascending) and ascending[end][0] == ascending[index][0]:
            end += 1
        group_pos = sum(label for _, label in ascending[index:end])
        group_neg = end - index - group_pos
        pair_wins += group_pos * (lower_scored_negatives + group_neg / 2)
        lower_scored_negatives += group_neg
        index = end

    predicted = [int(score >= threshold) for score in scores]
    true_positive = sum(label and guess for label, guess in zip(labels, predicted, strict=True))
    false_positive = sum(
        not label and guess for label, guess in zip(labels, predicted, strict=True)
    )
    false_negative = positives - true_positive
    precision = (
        true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    )
    recall = true_positive / positives if positives else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if recall is not None and precision + recall
        else (0.0 if positives else None)
    )
    return {
        "pr_auc": average_precision if positives else None,
        "roc_auc": pair_wins / (positives * negatives) if positives and negatives else None,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "brier_score": sum(
            (score - label) ** 2 for label, score in zip(labels, scores, strict=True)
        )
        / len(labels),
        "true_positives": true_positive,
        "false_positives": false_positive,
        "false_negatives": false_negative,
        "true_negatives": negatives - false_positive,
    }


def select_f1_threshold(labels: list[int], scores: list[float]) -> float:
    """Choose an F1-maximizing probability cutoff, preferring the higher tied cutoff."""
    labels, scores = _validate_binary_inputs(labels, scores)
    candidates = sorted({0.0, 1.0, *scores})
    return max(
        candidates,
        key=lambda candidate: (
            classification_metrics(labels, scores, candidate)["f1"] or 0.0,
            candidate,
        ),
    )


def calibration_bins(
    labels: list[int], scores: list[float], bin_count: int = 10
) -> list[dict[str, float | int]]:
    """Return equal-width probability bins, omitting empty bins."""
    labels, scores = _validate_binary_inputs(labels, scores)
    if bin_count < 1:
        raise ValueError("bin_count must be positive")
    bins: list[list[tuple[int, float]]] = [[] for _ in range(bin_count)]
    for label, score in zip(labels, scores, strict=True):
        index = min(int(score * bin_count), bin_count - 1)
        bins[index].append((label, score))
    return [
        {
            "bin": index,
            "count": len(values),
            "mean_probability": sum(score for _, score in values) / len(values),
            "observed_rate": sum(label for label, _ in values) / len(values),
        }
        for index, values in enumerate(bins)
        if values
    ]


def repository_cluster_bootstrap(
    rows: list[dict[str, Any]],
    *,
    threshold: float,
    seed: int,
    resamples: int = 2000,
    confidence_level: float = 0.95,
) -> dict[str, tuple[float, float] | None]:
    """Percentile CIs from repository-level bootstrap samples."""
    if not rows:
        return {}
    if resamples < 1:
        raise ValueError("resamples must be positive")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one")
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["repo_id"])].append(row)
    repositories = sorted(grouped)
    if len(repositories) < 2:
        return {
            name: None for name in ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score")
        }

    random = Random(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    for _ in range(resamples):
        chosen = [random.choice(repositories) for _ in repositories]
        sample = [row for repo_id in chosen for row in grouped[repo_id]]
        labels = [int(row["label"]) for row in sample]
        scores = [float(row["score"]) for row in sample]
        metrics = classification_metrics(labels, scores, threshold)
        for name in ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score"):
            value = metrics[name]
            if value is not None:
                samples[name].append(float(value))

    intervals: dict[str, tuple[float, float] | None] = {}
    for name in ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score"):
        values = sorted(samples[name])
        if not values:
            intervals[name] = None
            continue
        alpha = (1 - confidence_level) / 2
        intervals[name] = (
            _percentile(values, alpha),
            _percentile(values, 1 - alpha),
        )
    return intervals


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = probability * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def paired_repository_cluster_bootstrap(
    baseline_rows: list[dict[str, Any]],
    extended_rows: list[dict[str, Any]],
    *,
    baseline_threshold: float,
    extended_threshold: float,
    seed: int,
    resamples: int = 2000,
    confidence_level: float = 0.95,
) -> dict[str, dict[str, float | None]]:
    """Cluster-bootstrap paired metric differences for the same snapshots."""
    if not baseline_rows or len(baseline_rows) != len(extended_rows):
        raise ValueError("paired model rows must be non-empty and have matching size")
    if resamples < 1 or not 0 < confidence_level < 1:
        raise ValueError("invalid bootstrap configuration")
    baseline = {int(row["snapshot_id"]): row for row in baseline_rows}
    extended = {int(row["snapshot_id"]): row for row in extended_rows}
    if baseline.keys() != extended.keys():
        raise ValueError("paired models must score identical snapshot IDs")
    if any(
        baseline[snapshot_id]["repo_id"] != extended[snapshot_id]["repo_id"]
        or baseline[snapshot_id]["label"] != extended[snapshot_id]["label"]
        for snapshot_id in baseline
    ):
        raise ValueError("paired model rows must share repositories and labels")

    by_repository: dict[int, list[int]] = defaultdict(list)
    for snapshot_id, row in baseline.items():
        by_repository[int(row["repo_id"])].append(snapshot_id)
    repositories = sorted(by_repository)
    if len(repositories) < 2:
        return {
            name: {"difference": None, "ci_low": None, "ci_high": None}
            for name in ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score")
        }

    def difference(snapshot_ids: list[int]) -> dict[str, float | None]:
        labels = [int(baseline[sid]["label"]) for sid in snapshot_ids]
        base_scores = [float(baseline[sid]["score"]) for sid in snapshot_ids]
        extended_scores = [float(extended[sid]["score"]) for sid in snapshot_ids]
        base_metrics = classification_metrics(labels, base_scores, baseline_threshold)
        extended_metrics = classification_metrics(labels, extended_scores, extended_threshold)
        return {
            name: (
                float(extended_metrics[name]) - float(base_metrics[name])
                if extended_metrics[name] is not None and base_metrics[name] is not None
                else None
            )
            for name in ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score")
        }

    observed = difference(list(baseline))
    samples: dict[str, list[float]] = defaultdict(list)
    random = Random(seed)
    for _ in range(resamples):
        chosen = [random.choice(repositories) for _ in repositories]
        snapshot_ids = [sid for repo_id in chosen for sid in by_repository[repo_id]]
        for name, value in difference(snapshot_ids).items():
            if value is not None:
                samples[name].append(value)

    alpha = (1 - confidence_level) / 2
    return {
        name: {
            "difference": observed[name],
            "ci_low": _percentile(sorted(samples[name]), alpha) if samples[name] else None,
            "ci_high": _percentile(sorted(samples[name]), 1 - alpha) if samples[name] else None,
        }
        for name in ("pr_auc", "roc_auc", "precision", "recall", "f1", "brier_score")
    }


def activity_decline_scores(
    features: list[dict[str, Any]],
) -> list[float]:
    """Fixed recent-activity baseline: risk = 1 - 3*(recent/90-day commits)."""
    scores = []
    for row in features:
        count_90d = float(row["commits_90d"])
        count_30d = float(row["commits_30d"])
        if count_90d <= 0:
            raise ValueError("eligible snapshots require positive 90-day activity")
        scores.append(min(1.0, max(0.0, 1 - 3 * count_30d / count_90d)))
    return scores

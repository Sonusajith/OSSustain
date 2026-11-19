"""Pure UTC window, label, split, and prevalence calculations."""

from bisect import bisect_left
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from ossustain_pipeline.experiment import ExperimentConfig


def midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


@dataclass(frozen=True)
class Commit:
    sha: str
    timestamp: datetime
    is_bot: bool | None


@dataclass(frozen=True)
class Snapshot:
    prediction_date: date
    reference_start: date
    future_end: date
    observed_until: date  # Exclusive upper bound, midnight UTC.
    reference_activity: int
    future_activity: int | None
    label: bool | None
    label_status: str
    split: str


def split_for(prediction_date: date, config: ExperimentConfig) -> str:
    for name in ("train", "validation", "test"):
        window = config.splits[name]
        if window.start <= prediction_date <= window.end:
            return name
    for left, right in (("train", "validation"), ("validation", "test")):
        if config.splits[left].end < prediction_date < config.splits[right].start:
            return "purged"
    return "unassigned"


def is_decline(reference: int, future: int, theta: float) -> bool:
    # Decimal avoids a float rounding decision at the inclusive threshold boundary.
    return Decimal(future) <= Decimal(str(theta)) * reference


def build_repository_snapshots(
    commits: list[Commit],
    config: ExperimentConfig,
) -> list[Snapshot]:
    if any(c.timestamp.tzinfo is None for c in commits):
        raise ValueError("Commit timestamps must be timezone-aware")
    if len({c.sha for c in commits}) != len(commits):
        raise ValueError("Duplicate commit SHAs in snapshot input")
    # Unknown identities remain included in activity; only known bots are excluded.
    timestamps = sorted(c.timestamp.astimezone(UTC) for c in commits if c.is_bot is not True)
    policy = config.label
    observed_until = config.observation_end + timedelta(days=1)
    prediction_date = config.observation_start + timedelta(days=policy.reference_window_days)
    result = []
    while prediction_date <= config.observation_end:
        reference_start = prediction_date - timedelta(days=policy.reference_window_days)
        future_end = prediction_date + timedelta(days=policy.future_window_days)
        pivot = bisect_left(timestamps, midnight(prediction_date))
        reference = pivot - bisect_left(timestamps, midnight(reference_start))
        future = None
        label = None
        if future_end > observed_until:
            status = "incomplete_future"
        else:
            future = bisect_left(timestamps, midnight(future_end)) - pivot
            if reference < policy.min_reference_commits:
                status = "low_reference_activity"
            else:
                status = "labeled"
                label = is_decline(reference, future, policy.theta)
        result.append(
            Snapshot(
                prediction_date,
                reference_start,
                future_end,
                observed_until,
                reference,
                future,
                label,
                status,
                split_for(prediction_date, config),
            )
        )
        prediction_date += timedelta(days=config.snapshot_interval_days)
    return result


def prevalence(rows: list[Snapshot], thresholds: list[float]) -> dict[str, Any]:
    eligible = [row for row in rows if row.label_status == "labeled"]
    sensitivity = {}
    for theta in thresholds:
        positive = sum(
            is_decline(row.reference_activity, row.future_activity, theta) for row in eligible
        )
        sensitivity[str(theta)] = {
            "positive": positive,
            "labeled": len(eligible),
            "prevalence": positive / len(eligible) if eligible else None,
        }
    return {
        "snapshots": len(rows),
        "labeled": len(eligible),
        "statuses": dict(sorted(Counter(row.label_status for row in rows).items())),
        "thresholds": sensitivity,
    }


def summarize(
    repositories: list[tuple[str, list[Snapshot]]],
    config: ExperimentConfig,
) -> dict[str, Any]:
    thresholds = sorted([config.label.theta, *config.label.sensitivity_theta])
    rows = [row for _, snapshots in repositories for row in snapshots]
    groups = sorted({group for group, _ in repositories})
    periods = sorted({row.prediction_date for row in rows})
    return {
        "overall": prevalence(rows, thresholds),
        "by_split": {
            split: prevalence([r for r in rows if r.split == split], thresholds)
            for split in ("train", "validation", "test", "purged", "unassigned")
        },
        "by_size_group": {
            group: prevalence(
                [r for g, snapshots in repositories if g == group for r in snapshots], thresholds
            )
            for group in groups
        },
        "by_period": {
            str(period): prevalence([r for r in rows if r.prediction_date == period], thresholds)
            for period in periods
        },
        "by_split_and_size_group": {
            split: {
                group: prevalence(
                    [
                        r
                        for g, snapshots in repositories
                        if g == group
                        for r in snapshots
                        if r.split == split
                    ],
                    thresholds,
                )
                for group in groups
            }
            for split in ("train", "validation", "test", "purged", "unassigned")
        },
    }


def snapshot_values(snapshot: Snapshot) -> tuple[Any, ...]:
    return tuple(asdict(snapshot).values())

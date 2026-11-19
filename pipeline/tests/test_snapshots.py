from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from ossustain_pipeline.collect.models import load_cohort
from ossustain_pipeline.experiment import ExperimentConfig, load_experiment_config
from ossustain_pipeline.snapshots.core import (
    Commit,
    build_repository_snapshots,
    is_decline,
    midnight,
    prevalence,
    split_for,
    summarize,
)
from ossustain_pipeline.snapshots.runner import validate_inputs


@pytest.fixture
def protocol():
    return load_experiment_config(Path(__file__).parents[2] / "config/experiment.yaml")


def test_half_open_utc_windows_bot_and_unknown_author_policy(protocol):
    start = midnight(date(2022, 1, 1))
    t = midnight(date(2022, 4, 1))
    end = t + timedelta(days=90)
    commits = [Commit(str(i), t - timedelta(days=1), False) for i in range(19)]
    commits += [
        Commit("start", start, None),
        Commit("before", start - timedelta(microseconds=1), False),
        Commit("bot", t - timedelta(days=1), True),
        Commit("at-t", t, False),
        Commit("last-future", end - timedelta(microseconds=1), False),
        Commit("end", end, False),
    ]
    first = build_repository_snapshots(commits, protocol)[0]
    assert first.reference_activity == 20
    assert first.future_activity == 2
    assert first.label is True
    assert first.label_status == "labeled"
    assert first.split == "train"
    # Equivalent timestamps in another offset must count identically.
    commits[0] = replace(commits[0], timestamp=datetime.fromisoformat("2022-03-31T05:30:00+05:30"))
    assert build_repository_snapshots(commits, protocol)[0] == first


@pytest.mark.parametrize(
    "future,theta,expected",
    [
        (6, 0.3, True),
        (7, 0.3, False),
        (10, 0.5, True),
        (11, 0.5, False),
        (14, 0.7, True),
        (15, 0.7, False),
    ],
)
def test_inclusive_threshold(future, theta, expected):
    assert is_decline(20, future, theta) is expected


def test_low_activity_is_unlabeled_even_when_future_zero(protocol):
    snapshot = build_repository_snapshots([], protocol)[0]
    assert snapshot.reference_activity == 0
    assert snapshot.future_activity == 0
    assert snapshot.label is None
    assert snapshot.label_status == "low_reference_activity"
    commits = [Commit(str(i), midnight(date(2022, 3, 1)), False) for i in range(19)]
    assert build_repository_snapshots(commits, protocol)[0].label is None
    commits.append(Commit("20", midnight(date(2022, 3, 1)), False))
    assert build_repository_snapshots(commits, protocol)[0].label is True


def test_incomplete_future_never_uses_partial_counts(protocol):
    rows = build_repository_snapshots([], protocol)
    assert len(rows) == 46
    assert rows[0].prediction_date == date(2022, 4, 1)
    assert rows[-1].prediction_date == date(2025, 12, 11)
    for previous, current in zip(rows, rows[1:], strict=False):
        assert (current.prediction_date - previous.prediction_date).days == 30
    for row in rows:
        if row.future_end > date(2026, 1, 1):
            assert row.label_status == "incomplete_future"
            assert row.label is None and row.future_activity is None
    t = rows[-1].prediction_date
    commits = [Commit(str(i), midnight(t) - timedelta(days=1), False) for i in range(25)]
    commits.append(Commit("partial", midnight(t), False))
    last = build_repository_snapshots(commits, protocol)[-1]
    assert last.reference_activity == 25
    assert last.future_activity is None and last.label is None


def test_future_window_can_end_at_midnight_after_last_observed_day(protocol):
    values = protocol.model_dump(mode="json")
    values["splits"]["test"]["end"] = "2025-10-03"
    values["observation_end"] = "2026-01-01"
    config = ExperimentConfig.model_validate(values)
    # Pick an observation end that exactly closes a scheduled snapshot's future window.
    row = build_repository_snapshots([], config)[-4]
    values["observation_end"] = str(row.future_end - timedelta(days=1))
    values["splits"]["test"]["end"] = str(row.prediction_date)
    config = ExperimentConfig.model_validate(values)
    actual = next(
        s
        for s in build_repository_snapshots([], config)
        if s.prediction_date == row.prediction_date
    )
    assert actual.future_activity == 0
    assert actual.label_status == "low_reference_activity"


@pytest.mark.parametrize(
    "day,expected",
    [
        ("2023-06-30", "train"),
        ("2023-07-01", "purged"),
        ("2023-09-30", "purged"),
        ("2023-10-01", "validation"),
        ("2024-06-30", "validation"),
        ("2024-07-01", "purged"),
        ("2024-09-30", "purged"),
        ("2024-10-01", "test"),
        ("2025-09-30", "test"),
        ("2025-10-01", "unassigned"),
    ],
)
def test_inclusive_split_boundaries(protocol, day, expected):
    assert split_for(date.fromisoformat(day), protocol) == expected


def test_split_label_windows_do_not_overlap(protocol):
    rows = build_repository_snapshots([], protocol)
    for left, right in [("train", "validation"), ("validation", "test")]:
        assert max(r.future_end for r in rows if r.split == left) <= min(
            r.prediction_date for r in rows if r.split == right
        )
    values = protocol.model_dump(mode="json")
    values["label"]["future_window_days"] = 100
    values["splits"]["test"]["end"] = "2025-09-01"
    with pytest.raises(ValueError, match="split gap"):
        ExperimentConfig.model_validate(values)


def test_future_changes_cannot_change_reference_activity_or_split(protocol):
    commits = [Commit(str(i), midnight(date(2022, 3, 1)), False) for i in range(20)]
    original = build_repository_snapshots(commits, protocol)[0]
    commits += [Commit("future" + str(i), midnight(date(2022, 4, 1)), False) for i in range(30)]
    changed = build_repository_snapshots(commits, protocol)[0]
    assert original.reference_activity == changed.reference_activity == 20
    assert original.split == changed.split
    assert original.label is True and changed.label is False


def test_prevalence_denominator_excludes_unlabeled_and_reports_empty_strata(protocol):
    unlabeled = build_repository_snapshots([], protocol)[0]
    labeled = replace(
        unlabeled, reference_activity=20, future_activity=10, label_status="labeled", label=True
    )
    report = summarize([("small", [unlabeled, labeled]), ("large", [unlabeled])], protocol)
    assert report["overall"]["labeled"] == 1
    assert report["overall"]["thresholds"]["0.3"]["positive"] == 0
    assert report["overall"]["thresholds"]["0.5"]["prevalence"] == 1
    assert report["by_size_group"]["large"]["thresholds"]["0.5"]["prevalence"] is None
    assert report["by_period"]["2022-04-01"]["snapshots"] == 3
    assert prevalence([], [0.5])["thresholds"]["0.5"]["prevalence"] is None


def test_rejects_naive_times_and_duplicate_events(protocol):
    with pytest.raises(ValueError, match="timezone-aware"):
        build_repository_snapshots([Commit("a", datetime(2022, 1, 1), False)], protocol)
    commit = Commit("a", datetime(2022, 1, 1, tzinfo=UTC), False)
    with pytest.raises(ValueError, match="Duplicate"):
        build_repository_snapshots([commit, commit], protocol)


def test_preflight_retains_flags_but_rejects_incomplete_or_mismatched_cohort(protocol):
    cohort = load_cohort(Path(__file__).parents[2] / "config/cohort.yaml")
    report = {
        "cohort_config_hash": cohort.config_hash,
        "observation_start": "2022-01-01",
        "observation_end": "2025-12-31",
        "repositories": [
            {
                "github_id": r.github_id,
                "stages_complete": {"pull_requests": True, "reviews": True, "issues": True},
                "quality_flags": ["no_collaboration_events"],
            }
            for r in cohort.repositories
        ],
    }
    validate_inputs(cohort, protocol, report)
    report["repositories"][0]["stages_complete"]["issues"] = False
    with pytest.raises(ValueError, match="Complete Phase 4"):
        validate_inputs(cohort, protocol, report)
    report["repositories"].pop()
    with pytest.raises(ValueError, match="exactly the selected cohort"):
        validate_inputs(cohort, protocol, report)
    report["cohort_config_hash"] = "outdated"
    with pytest.raises(ValueError, match="current cohort"):
        validate_inputs(cohort, protocol, report)

from datetime import UTC, date, datetime, timedelta

import pytest

from ossustain_pipeline.features.core import (
    FEATURE_DEFINITIONS,
    CommitEvent,
    IssueEvent,
    PullRequestEvent,
    ReviewEvent,
    compute_features,
)


def at(day: date, offset: int, hour: int = 0) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(
        days=offset, hours=hour
    )


def test_all_feature_groups_use_trailing_half_open_windows_and_known_bots_are_excluded():
    t = date(2024, 1, 1)
    commits = [
        CommitEvent(at(t, -100), 1, False),
        CommitEvent(at(t, -1), 1, False),
        CommitEvent(at(t, -170), 2, False),
        CommitEvent(at(t, -90), 3, False),
        CommitEvent(at(t, -30), None, None),
        CommitEvent(at(t, -3), 4, True),
        CommitEvent(at(t, 0), 5, False),  # At t is outside every feature.
    ]
    prs = [
        PullRequestEvent(10, at(t, -30), at(t, -10), at(t, 1)),
        PullRequestEvent(11, at(t, 0), at(t, 0), at(t, 0)),
    ]
    issues = [
        IssueEvent(at(t, -5), at(t, -2)),
        IssueEvent(at(t, -4), at(t, 1)),
    ]
    reviews = [
        ReviewEvent(10, at(t, -30), at(t, -1)),
        ReviewEvent(10, at(t, -30), at(t, 0)),
        ReviewEvent(11, at(t, 0), at(t, 0)),
    ]

    result = compute_features(commits, prs, issues, reviews, t)
    f = result.features
    assert f["commits_30d"] == 2  # -30 and -1; unknown author remains in activity.
    assert f["commits_90d"] == 3
    assert f["active_contributors_90d"] == 2
    assert f["contributor_identity_coverage_90d"] == pytest.approx(2 / 3)
    assert f["top_1_contribution_share_90d"] == pytest.approx(0.5)
    assert f["top_5_contribution_share_90d"] == 1
    assert f["contributor_gini_90d"] == 0
    assert f["contributor_entropy_90d"] == pytest.approx(1)
    assert f["contributor_churn_90d"] == pytest.approx(0.5)
    assert f["new_contributors_90d"] == 1
    assert f["newcomer_retention_rate_90d"] == pytest.approx(0.5)
    assert f["pull_requests_opened_90d"] == 1
    assert f["pull_requests_merged_90d"] == 1
    assert f["pull_request_merge_rate_90d"] == 1
    assert f["median_pr_merge_hours_90d"] == 20 * 24
    assert f["pull_request_response_coverage_90d"] == 0
    assert f["median_pr_first_response_hours_90d"] is None
    assert f["issues_opened_90d"] == 2
    assert f["issue_response_coverage_90d"] == 0.5
    assert f["median_issue_first_response_hours_90d"] == 72
    assert f["reviews_submitted_90d"] == 1
    assert result.missing_flags["median_pr_first_response_hours_90d"] is True
    assert result.completeness["unknown_identity_commits_90d"] == 1


def test_post_prediction_events_cannot_change_any_feature():
    t = date(2024, 1, 1)
    before = [CommitEvent(at(t, -10), 5, False)]
    prs = [PullRequestEvent(1, at(t, -20), None, None)]
    issues = [IssueEvent(at(t, -20), None)]
    reviews = [ReviewEvent(1, at(t, -20), None)]
    baseline = compute_features(before, prs, issues, reviews, t)
    changed = compute_features(
        before + [CommitEvent(at(t, 1), 99, False)],
        prs + [PullRequestEvent(2, at(t, 1), at(t, 2), at(t, 2))],
        issues + [IssueEvent(at(t, 1), at(t, 2))],
        reviews + [ReviewEvent(2, at(t, 1), at(t, 2))],
        t,
    )
    assert changed == baseline


def test_windows_are_half_open_at_each_start_and_prediction_boundary():
    t = date(2024, 6, 30)
    commits = [
        CommitEvent(at(t, -90), 1, False),
        CommitEvent(at(t, -30), 2, False),
        CommitEvent(at(t, 0), 3, False),
    ]
    result = compute_features(commits, [], [], [], t)
    assert result.features["commits_30d"] == 1
    assert result.features["commits_90d"] == 2
    assert result.features["commits_180d"] == 2


def test_empty_cohort_uses_null_for_undefined_rates_without_zero_imputation():
    result = compute_features([], [], [], [], date(2024, 1, 1))
    assert result.features["commits_90d"] == 0
    assert result.features["active_contributors_90d"] == 0
    assert result.features["contributor_identity_coverage_90d"] is None
    assert result.features["contributor_churn_90d"] is None
    assert result.features["newcomer_retention_rate_90d"] is None
    assert result.features["pull_request_merge_rate_90d"] is None
    assert result.features["issue_response_coverage_90d"] is None
    assert result.missing_flags["commits_90d"] is False
    assert result.missing_flags["contributor_identity_coverage_90d"] is True
    assert result.missing_flags["pull_request_merge_rate_90d"] is True


def test_registered_dictionary_covers_exactly_the_computed_feature_names():
    names = [item["feature_name"] for item in FEATURE_DEFINITIONS]
    values = compute_features([], [], [], [], date(2024, 1, 1)).features
    assert len(names) == len(set(names))
    assert set(names) == set(values)
    assert {item["feature_group"] for item in FEATURE_DEFINITIONS} == {
        "activity",
        "contributor_diversity",
        "newcomer_retention",
        "responsiveness",
    }


@pytest.mark.parametrize(
    "events",
    [
        [CommitEvent(datetime(2024, 1, 1), 1, False)],
    ],
)
def test_naive_event_timestamps_are_rejected(events):
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_features(events, [], [], [], date(2024, 2, 1))

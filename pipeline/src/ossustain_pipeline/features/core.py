"""Pure feature calculations using only events strictly before prediction time."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import log
from statistics import median
from typing import Any

FeatureDefinition = dict[str, str]


def _definition(
    name: str, group: str, description: str, window: str, missing: str
) -> FeatureDefinition:
    return {
        "feature_name": name,
        "feature_group": group,
        "description": description,
        "time_window": window,
        "missing_policy": missing,
    }


FEATURE_DEFINITIONS = [
    _definition(
        "commits_30d",
        "activity",
        "Non-known-bot default-branch commits in the trailing 30 days.",
        "[t-30d, t)",
        "Zero when the complete commit collection has no events.",
    ),
    _definition(
        "commits_90d",
        "activity",
        "Non-known-bot default-branch commits in the trailing 90 days.",
        "[t-90d, t)",
        "Zero when the complete commit collection has no events.",
    ),
    _definition(
        "commits_180d",
        "activity",
        "Non-known-bot default-branch commits in the trailing 180 days.",
        "[t-180d, t)",
        "Zero when the complete commit collection has no events.",
    ),
    _definition(
        "active_contributors_90d",
        "contributor_diversity",
        "Distinct known, non-bot contributors with a commit in the trailing 90 days.",
        "[t-90d, t)",
        "Zero when there are no attributable commits.",
    ),
    _definition(
        "active_contributors_180d",
        "contributor_diversity",
        "Distinct known, non-bot contributors with a commit in the trailing 180 days.",
        "[t-180d, t)",
        "Zero when there are no attributable commits.",
    ),
    _definition(
        "contributor_identity_coverage_90d",
        "contributor_diversity",
        "Share of non-known-bot commits linked to a contributor in the trailing 90 days.",
        "[t-90d, t)",
        "Null when there are no commits in the window.",
    ),
    _definition(
        "top_1_contribution_share_90d",
        "contributor_diversity",
        "Largest known contributor share of attributable commits in the trailing 90 days.",
        "[t-90d, t)",
        "Null when there are no attributable commits.",
    ),
    _definition(
        "top_5_contribution_share_90d",
        "contributor_diversity",
        "Top five known contributor share of attributable commits in the trailing 90 days.",
        "[t-90d, t)",
        "Null when there are no attributable commits.",
    ),
    _definition(
        "contributor_gini_90d",
        "contributor_diversity",
        "Gini coefficient of known contributor commit counts in the trailing 90 days.",
        "[t-90d, t)",
        "Null when there are no attributable commits.",
    ),
    _definition(
        "contributor_entropy_90d",
        "contributor_diversity",
        "Normalized Shannon entropy of known contributor commit shares in the trailing 90 days.",
        "[t-90d, t)",
        "Null when there are no attributable commits; zero for one contributor.",
    ),
    _definition(
        "contributor_churn_90d",
        "contributor_diversity",
        "Share of prior-window contributors absent in the most recent 90 days.",
        "Prior [t-180d, t-90d); recent [t-90d, t)",
        "Null when the preceding cohort is empty.",
    ),
    _definition(
        "new_contributors_90d",
        "newcomer_retention",
        "Known contributors whose first observed repository commit is in the trailing 90 days.",
        "[t-90d, t)",
        "Zero when no contributors are new.",
    ),
    _definition(
        "newcomer_retention_rate_90d",
        "newcomer_retention",
        "Share of contributors first seen 90–180 days before t who returned in the recent window.",
        "First seen [t-180d, t-90); retained [t-90d, t)",
        "Null when the eligible newcomer cohort is empty.",
    ),
    _definition(
        "pull_requests_opened_90d",
        "responsiveness",
        "Pull requests created in the trailing 90 days.",
        "[t-90d, t)",
        "Zero when complete collection has no events.",
    ),
    _definition(
        "pull_requests_merged_90d",
        "responsiveness",
        "Pull requests both created and merged in the trailing 90 days, with merge before t.",
        "[t-90d, t)",
        "Zero when complete collection has no events.",
    ),
    _definition(
        "pull_request_merge_rate_90d",
        "responsiveness",
        "Share of pull requests created in the trailing 90 days and merged before t.",
        "Created [t-90d, t); merge < t",
        "Null when no pull requests were created in the window.",
    ),
    _definition(
        "median_pr_merge_hours_90d",
        "responsiveness",
        "Median hours from creation to merge for trailing-window pull requests merged before t.",
        "Created [t-90d, t); merge < t",
        "Null when no eligible pull request has merged.",
    ),
    _definition(
        "pull_request_response_coverage_90d",
        "responsiveness",
        "Share of trailing-window pull requests with a recorded first response before t.",
        "Created [t-90d, t); response < t",
        "Null when no pull requests were created in the window.",
    ),
    _definition(
        "median_pr_first_response_hours_90d",
        "responsiveness",
        "Median hours from pull request creation to first recorded response before t.",
        "Created [t-90d, t); response < t",
        "Null when no eligible response is recorded.",
    ),
    _definition(
        "issues_opened_90d",
        "responsiveness",
        "Non-pull-request issues created in the trailing 90 days.",
        "[t-90d, t)",
        "Zero when complete collection has no events.",
    ),
    _definition(
        "issue_response_coverage_90d",
        "responsiveness",
        "Share of trailing-window issues with a recorded first response before t.",
        "Created [t-90d, t); response < t",
        "Null when no issues were created in the window.",
    ),
    _definition(
        "median_issue_first_response_hours_90d",
        "responsiveness",
        "Median hours from issue creation to first recorded response before t.",
        "Created [t-90d, t); response < t",
        "Null when no eligible response is recorded.",
    ),
    _definition(
        "reviews_submitted_90d",
        "responsiveness",
        "Reviews submitted before t on pull requests created in the trailing 90 days.",
        "PR created [t-90d, t); review < t",
        "Zero when complete collection has no reviews.",
    ),
]


@dataclass(frozen=True)
class CommitEvent:
    timestamp: datetime
    contributor_id: int | None
    is_bot: bool | None


@dataclass(frozen=True)
class PullRequestEvent:
    pull_request_id: int
    created_at: datetime
    merged_at: datetime | None
    first_response_at: datetime | None


@dataclass(frozen=True)
class IssueEvent:
    created_at: datetime
    first_response_at: datetime | None


@dataclass(frozen=True)
class ReviewEvent:
    pull_request_id: int
    pull_request_created_at: datetime
    submitted_at: datetime | None


@dataclass(frozen=True)
class FeatureResult:
    features: dict[str, float | int | None]
    missing_flags: dict[str, bool]
    completeness: dict[str, float | int]


def _instant(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _validate_times(events: list[Any]) -> None:
    for event in events:
        for value in event.__dict__.values():
            if isinstance(value, datetime) and value.tzinfo is None:
                raise ValueError("Feature event timestamps must be timezone-aware")


def _in_window(value: datetime | None, start: datetime, end: datetime) -> bool:
    return value is not None and start <= value.astimezone(UTC) < end


def _gini(counts: list[int]) -> float | None:
    if not counts:
        return None
    ordered = sorted(counts)
    n = len(ordered)
    total = sum(ordered)
    return sum((2 * index - n - 1) * value for index, value in enumerate(ordered, 1)) / (n * total)


def compute_features(
    commits: list[CommitEvent],
    pull_requests: list[PullRequestEvent],
    issues: list[IssueEvent],
    reviews: list[ReviewEvent],
    prediction_date: date,
) -> FeatureResult:
    """Compute all fields from the strict historical prefix ending before t."""
    _validate_times(commits)
    _validate_times(pull_requests)
    _validate_times(issues)
    _validate_times(reviews)
    end = _instant(prediction_date)
    historical_commits = [
        row for row in commits if row.timestamp.astimezone(UTC) < end and row.is_bot is not True
    ]
    historical_prs = [row for row in pull_requests if row.created_at.astimezone(UTC) < end]
    historical_issues = [row for row in issues if row.created_at.astimezone(UTC) < end]
    historical_reviews = [
        row
        for row in reviews
        if row.submitted_at is not None
        and row.submitted_at.astimezone(UTC) < end
        and row.pull_request_created_at.astimezone(UTC) < end
    ]

    def range_events(rows: list[Any], field: str, days: int) -> list[Any]:
        start = end - timedelta(days=days)
        return [row for row in rows if _in_window(getattr(row, field), start, end)]

    commit_30 = range_events(historical_commits, "timestamp", 30)
    commit_90 = range_events(historical_commits, "timestamp", 90)
    commit_180 = range_events(historical_commits, "timestamp", 180)
    attributed_90 = Counter(
        row.contributor_id for row in commit_90 if row.contributor_id is not None
    )
    attributed_180 = {row.contributor_id for row in commit_180 if row.contributor_id is not None}
    previous_90 = {
        row.contributor_id
        for row in historical_commits
        if row.contributor_id is not None
        and _in_window(row.timestamp, end - timedelta(days=180), end - timedelta(days=90))
    }
    recent_90 = {row.contributor_id for row in commit_90 if row.contributor_id is not None}
    identities_first_seen: dict[int, datetime] = {}
    for row in historical_commits:
        if row.contributor_id is None:
            continue
        current = row.timestamp.astimezone(UTC)
        identities_first_seen[row.contributor_id] = min(
            current, identities_first_seen.get(row.contributor_id, current)
        )
    new_90 = {
        contributor
        for contributor, first_seen in identities_first_seen.items()
        if _in_window(first_seen, end - timedelta(days=90), end)
    }
    newcomer_cohort = {
        contributor
        for contributor, first_seen in identities_first_seen.items()
        if _in_window(first_seen, end - timedelta(days=180), end - timedelta(days=90))
    }
    pr_90 = range_events(historical_prs, "created_at", 90)
    issue_90 = range_events(historical_issues, "created_at", 90)
    merged_prs = [
        row
        for row in pr_90
        if row.merged_at is not None and _in_window(row.merged_at, end - timedelta(days=90), end)
    ]
    pr_responses = [
        row
        for row in pr_90
        if row.first_response_at is not None and row.first_response_at.astimezone(UTC) < end
    ]
    issue_responses = [
        row
        for row in issue_90
        if row.first_response_at is not None and row.first_response_at.astimezone(UTC) < end
    ]
    trailing_pr_ids = {row.pull_request_id for row in pr_90}
    response_reviews = [row for row in historical_reviews if row.pull_request_id in trailing_pr_ids]

    known_commit_count = sum(attributed_90.values())
    total_commit_count = len(commit_90)
    contributor_counts = list(attributed_90.values())
    normalized_entropy = None
    if contributor_counts:
        entropy = -sum(
            (count / known_commit_count) * log(count / known_commit_count)
            for count in contributor_counts
        )
        normalized_entropy = (
            entropy / log(len(contributor_counts)) if len(contributor_counts) > 1 else 0.0
        )
    pr_response_hours = [
        (row.first_response_at.astimezone(UTC) - row.created_at.astimezone(UTC)).total_seconds()
        / 3600
        for row in pr_responses
    ]
    issue_response_hours = [
        (row.first_response_at.astimezone(UTC) - row.created_at.astimezone(UTC)).total_seconds()
        / 3600
        for row in issue_responses
    ]
    merge_hours = [
        (row.merged_at.astimezone(UTC) - row.created_at.astimezone(UTC)).total_seconds() / 3600
        for row in merged_prs
    ]
    features: dict[str, float | int | None] = {
        "commits_30d": len(commit_30),
        "commits_90d": total_commit_count,
        "commits_180d": len(commit_180),
        "active_contributors_90d": len(attributed_90),
        "active_contributors_180d": len(attributed_180),
        "contributor_identity_coverage_90d": (
            known_commit_count / total_commit_count if total_commit_count else None
        ),
        "top_1_contribution_share_90d": (
            max(contributor_counts) / known_commit_count if known_commit_count else None
        ),
        "top_5_contribution_share_90d": (
            sum(sorted(contributor_counts, reverse=True)[:5]) / known_commit_count
            if known_commit_count
            else None
        ),
        "contributor_gini_90d": _gini(contributor_counts),
        "contributor_entropy_90d": normalized_entropy,
        "contributor_churn_90d": (
            len(previous_90 - recent_90) / len(previous_90) if previous_90 else None
        ),
        "new_contributors_90d": len(new_90),
        "newcomer_retention_rate_90d": (
            len(newcomer_cohort & recent_90) / len(newcomer_cohort) if newcomer_cohort else None
        ),
        "pull_requests_opened_90d": len(pr_90),
        "pull_requests_merged_90d": len(merged_prs),
        "pull_request_merge_rate_90d": len(merged_prs) / len(pr_90) if pr_90 else None,
        "median_pr_merge_hours_90d": median(merge_hours) if merge_hours else None,
        "pull_request_response_coverage_90d": len(pr_responses) / len(pr_90) if pr_90 else None,
        "median_pr_first_response_hours_90d": median(pr_response_hours)
        if pr_response_hours
        else None,
        "issues_opened_90d": len(issue_90),
        "issue_response_coverage_90d": len(issue_responses) / len(issue_90) if issue_90 else None,
        "median_issue_first_response_hours_90d": median(issue_response_hours)
        if issue_response_hours
        else None,
        "reviews_submitted_90d": len(response_reviews),
    }
    if set(features) != {row["feature_name"] for row in FEATURE_DEFINITIONS}:
        raise RuntimeError("Feature values and registered dictionary are out of sync")
    missing = {name: value is None for name, value in features.items()}
    completeness = {
        "commits_observed_90d": total_commit_count,
        "commits_with_known_identity_90d": known_commit_count,
        "unknown_identity_commits_90d": total_commit_count - known_commit_count,
        "pull_requests_observed_90d": len(pr_90),
        "pull_requests_with_response_90d": len(pr_responses),
        "issues_observed_90d": len(issue_90),
        "issues_with_response_90d": len(issue_responses),
    }
    return FeatureResult(features, missing, completeness)

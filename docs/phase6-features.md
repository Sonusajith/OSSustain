# Phase 6 feature engineering

`build-features` derives a reproducible feature set from one Phase 5 dataset
version. The event calculations are pure functions in
`pipeline/src/ossustain_pipeline/features/core.py`; the database runner reads
only source events and snapshot dates, then stores results in V7 tables.

## Time and identity rules

For a snapshot at date *t*, *t* means 00:00 UTC. Every input event timestamp is
filtered to be strictly earlier than that instant. Trailing windows are
half-open: `[t − N days, t)`. Response and merge timestamps after *t* are
ignored even when the issue or pull request was created earlier. Each snapshot
is computed separately, so a later repository event cannot alter an earlier
snapshot's features.

Known bots are excluded from commit and contributor counts. Commits with an
unknown bot classification remain in activity counts; commits with no linked
contributor also remain in activity counts but cannot contribute to identity
distribution features. Identity coverage is reported to make that distinction
visible. Newcomer first-seen dates are recomputed from the repository's commit
history strictly before *t*; the globally stored contributor first-seen date is
not used because it can include later activity. Bot classification reflects
the collected account metadata and may not capture all automated accounts.

## Registered feature groups

All feature names and per-feature missing-value rules are registered in
`feature_definitions` for each feature set. The implementation currently
registers 23 values:

- **Activity:** `commits_30d`, `commits_90d`, `commits_180d`.
- **Contributor diversity:** `active_contributors_90d`,
  `active_contributors_180d`, `contributor_identity_coverage_90d`,
  `top_1_contribution_share_90d`, `top_5_contribution_share_90d`,
  `contributor_gini_90d`, `contributor_entropy_90d`, `contributor_churn_90d`.
- **Newcomer retention:** `new_contributors_90d`,
  `newcomer_retention_rate_90d`.
- **Responsiveness:** `pull_requests_opened_90d`, `pull_requests_merged_90d`,
  `pull_request_merge_rate_90d`, `median_pr_merge_hours_90d`,
  `pull_request_response_coverage_90d`,
  `median_pr_first_response_hours_90d`, `issues_opened_90d`,
  `issue_response_coverage_90d`, `median_issue_first_response_hours_90d`,
  `reviews_submitted_90d`.

The complete descriptions, windows, and missing policies are available in the
feature run's JSON report and in `feature_definitions`. Undefined ratios or
medians are stored as JSON null and have a corresponding `true` entry in
`missing_flags`; counts use zero when the event collection is complete. No
imputation is performed. `repository_metrics_monthly` contains the selected
human-readable trend metrics and completeness counters for dashboard use.

## Reproducibility and completeness

The feature-set hash incorporates the source dataset hash, registered
definitions, window and attribution rules, and a hash of the feature module
source. A rerun of the same feature set is idempotent and verifies that stored
feature values and display metrics match the recomputation. Different dataset
versions can each register the same implementation independently.

The runner refuses to proceed unless commits, pull requests, reviews, and issues
are marked complete for every repository represented in the dataset. Its report
includes per-feature missingness across all snapshots, grouped by repository
size and eligible labeled split, along with counts of all snapshots and labeled
train/validation/test snapshots. Unlabeled and purged snapshots also receive
features for research completeness, but downstream modeling must use only
labeled rows assigned to train, validation, or test.

Features are predictors or descriptive measurements, not causal explanations.
Responsiveness measures are also limited by public event availability and the
collector's first-response definition. Phase 6 does not train or select a model.

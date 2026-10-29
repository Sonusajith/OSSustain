# Research protocol v1.0.0

This Phase 2 protocol fixes the retrospective study definitions before collection. It does not collect GitHub data or assert any model result. Dates and eligibility are to be revalidated before Phase 3 collection begins.

## Outcome and prediction schedule

The primary activity measure is the number of non-bot commits to a repository's default branch. For a prediction date *t*, reference activity is counted in `[t−90 days, t)` and future activity in `[t, t+90 days)`. A label is available only when the full future window is observed and reference activity is at least 20 commits. The primary decline label is positive when future activity is at most 0.5 times reference activity. Sensitivity thresholds are 0.3 and 0.7. Snapshots are scheduled every 30 days. Unlinked commit authors remain null; identity uses GitHub user ID. Accounts typed as Bot and logins ending in `[bot]` are excluded from contributor activity.

The planned observation period is 2022-01-01 through 2025-12-31. Prediction windows are train 2022-04-01–2023-06-30, validation 2023-10-01–2024-06-30, and test 2024-10-01–2025-09-30. Each adjacent split has at least 90 days between its last and next first prediction dates. The latest test future window completes by 2025-12-29. This is a chronological retrospective design; no random split is permitted. Recheck these dates against data availability before collection.

## Cohort and screening

The frozen candidate screen is `github-rest-search-2026-10-29-v1` in `config/cohort-candidates.yaml`; `config/cohort.yaml` is its deterministic, seeded selection. Screening used GitHub REST search on 2026-10-29. Candidate repositories must be public search results, non-forks, non-archived, created before 2022-01-01, pushed within the preceding 365 days, and have no more than 250 PRs created during 2022–2025. The age cutoff ensures at least four years of repository existence at the start of observation; the recency cutoff excludes inactive repositories; the PR cap bounds expensive collaboration-data collection. These are screening criteria, not model features.

Strata use stars observed during screening as a coarse size proxy: small 100–999, medium 1,000–4,999, large 5,000–9,999. Seed 42 deterministically selects 17, 17, and 16 repositories respectively, for 50 total. The screened candidate file contains 17, 21, and 22 eligible records in those strata; candidates are ordered by a SHA-256 key derived from the seed and case-insensitive repository name. The screen is not claimed to be representative of all GitHub repositories. Search-result and PR-count screening was rate limited for some candidates; unverified candidates were conservatively excluded. Re-run screening before collection and record any changes rather than silently replacing entries.

## API approach and budget estimate

Phase 2 selects REST-only collection; no GraphQL fallback is planned. REST authentication is expected to use the documented 5,000-request/hour authenticated quota. The selected cohort has 2,660 screened PRs total (492 small, 1,576 medium, 592 large). A conservative baseline assumes up to three calls per PR (detail, reviews, and response comments), 27 PR-list pages at 100 records per page, and one metadata request per repository: 8,057 requests. A 25% allowance for pagination, retries, and request overhead gives 10,072; rounded planning estimate: **10,100 requests**. The proposed stop cap is **12,500 requests** for PR/review/response collection only (about 2.5 quota-hours at 5,000 requests/hour). This excludes commit history and non-PR issue collection, which the PR screen does not bound.

This is a planning estimate, not a guaranteed upper bound: review/comment pagination and retries can increase the count. The project owner approved the 12,500-request stop cap for PR/review/response collection. Phase 4 must refine this estimate from actual endpoint pagination and issue counts before collection. Collectors must stop and report before exceeding the approved cap; do not switch to GraphQL without approval.

## Reproducibility and limits

Protocol values are in `config/experiment.yaml`; inclusion, screening, and final membership are in the two cohort YAML files. The selection command is deterministic for an unchanged input and seed. Star count is a screening-time proxy and can change; the frozen values are retained for reproducibility. Screening counts are based on public GitHub REST search and are not activity data. Phase 2 contains no collection, training, or prediction results.

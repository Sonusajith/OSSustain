# OSSustain: Product Requirements Document

**Status:** Planning. Development has not started.
**Scope note:** Visual design is produced separately in Google Stitch. This document defines product behavior and functional UX requirements only.

## 1. Project Overview

OSSustain is a research-oriented web application that analyzes historical data from public GitHub repositories and estimates the risk that a repository's contribution activity will decline significantly over the next 90 days. It has two parts:

1. **An offline research pipeline** (Python) that collects GitHub data, builds time-stamped snapshots, engineers features, trains and evaluates models, and stores the results.
2. **A read-only web dashboard** (React + Spring Boot) that presents repository analytics, risk estimates, indicators, and the research evidence.

## 2. Problem Statement

Repository statistics describe past activity but do not say whether a significant drop in contributions is likely soon. Contributor diversity, newcomer retention, and review responsiveness may carry predictive signal, but that must be tested, not assumed. OSSustain tests it with leakage-safe temporal evaluation and presents the results honestly, including null results.

## 3. Product Vision

A transparent, reproducible early-warning dashboard for contribution-activity decline, backed by an empirical study of which signals actually help.

## 4. Product Goals

1. Build a documented, reproducible dataset of historical activity for 50–100 public repositories.
2. Define a measurable outcome, "significant contribution-activity decline over 90 days", and justify its parameters.
3. Compare activity-only models against models with contributor, newcomer-retention, and responsiveness features, using chronological validation.
4. Show per-repository analytics, a risk estimate, and associated indicators with explicit limitations.
5. Report actual results, including when extra features do not help.
6. Deliver a working end-to-end MVP and an empirical basis for a B.Tech report and a possible paper.

## 5. Non-Goals

- Predicting abandonment, project failure, software quality, or security vulnerabilities.
- Claiming causation. Explanations describe predictive association only.
- Real-time monitoring, alerts, or notifications.
- User accounts, authentication, or personalization (MVP).
- Analyzing arbitrary user-submitted repositories on demand (MVP).
- Private repositories.
- Natural-language or LLM features.
- Multi-service or microservice architecture.

## 6. Target Users

| User | Description | Primary need |
|---|---|---|
| **Researcher / Student (primary)** | The project author, supervisors, examiners, and other researchers | Inspect methodology, dataset, model comparisons, and limitations; reproduce results |
| **OSS observer (secondary)** | Maintainers, foundation staff, or contributors curious about a specific repository | See a repository's activity trend, risk estimate, and what drives it |
| **Developer-operator** | The project author running the pipeline | Run the pipeline end to end, rerun with new parameters, and version results |

## 7. Core Use Cases

- **UC1:** Browse the study cohort and see each repository's latest risk category.
- **UC2:** Open a repository and view activity trends, contributor trends, newcomer retention, and responsiveness history.
- **UC3:** See a repository's risk estimate (probability and category), the prediction date, the model version, and the main associated indicators.
- **UC4:** Review model comparison results (baseline vs. models; activity-only vs. extended features).
- **UC5:** Review feature importance, performance by repository size group, and calibration.
- **UC6:** Read the definitions, label threshold, data limitations, and methodology.
- **UC7 (operator):** Run collection, feature building, training, and evaluation from the command line, and reproduce a result from a recorded dataset and model version.

## 8. Main User Journey

1. The user opens the dashboard and sees the cohort overview with a summary and the repository list (filterable by risk category and size group).
2. They select a repository and open its detail page.
3. They review trends, then the current risk estimate, indicators, and limitations.
4. They navigate to Research Results to see whether extended features improved prediction.
5. They open Methodology to understand definitions and caveats.

## 9. User Stories

- As a researcher, I want to see PR-AUC for each model on the test period so I can judge whether extended features help.
- As a researcher, I want results broken down by repository size group so I can answer RQ4.
- As a researcher, I want the label definition and threshold displayed so I can assess validity.
- As an OSS observer, I want to filter repositories by risk category so I can find at-risk projects.
- As an OSS observer, I want to see why a repository is flagged, shown as associations, not causes.
- As an OSS observer, I want to know when a prediction is unreliable (low activity, missing data).
- As the operator, I want each model and prediction tied to a dataset version and configuration so results are reproducible.

## 10. MVP Scope

The MVP is a complete vertical slice: a documented cohort → collected data → snapshots and labels → features → trained and evaluated models → stored predictions and explanations → read-only dashboard with four screens.

### Core Features (MVP)

| ID | Feature |
|---|---|
| F1 | Config-driven cohort selection with documented inclusion criteria and size/activity stratification |
| F2 | GitHub historical data collection (repo metadata, commits, contributors derived from commits, PRs, reviews, issues, first responses), resumable and rate-limit aware |
| F3 | Data validation and quality report (missingness, completeness per repository and per feature) |
| F4 | Snapshot and label construction (monthly prediction dates, reference/future windows, label-completeness status) |
| F5 | Feature engineering in four groups: activity, contributor diversity, newcomer retention, collaboration responsiveness, with leakage guards |
| F6 | Model training and temporal evaluation: threshold baseline, Logistic Regression, Random Forest, Gradient Boosting; activity-only vs. extended feature sets |
| F7 | Prediction storage with probability, risk category, prediction date, model version |
| F8 | Explanations: global (LR coefficients, permutation importance) and per-repository indicators, with explicit "association, not causation" wording |
| F9 | Dashboard screens: Cohort Overview, Repository Detail, Research Results, Methodology & Limitations |
| F10 | Dataset, model, and evaluation versioning records |
| F11 | Setup and reproducibility documentation |

### Secondary Features (post-MVP, near term)
- Repository Comparison (side-by-side metrics).
- SHAP explanations and per-prediction SHAP views.
- Robustness and sensitivity analyses (alternative thresholds, alternative activity definitions) surfaced in the dashboard.

### Future Ideas (not planned)
- On-demand analysis of user-submitted repositories (requires job queue, rate-limit management, and a live-prediction path).
- Authentication and an admin UI.
- Scheduled data refresh and drift monitoring.
- Features borrowed from related proposals (ReviewPulse, FirstCommit). These are separate research ideas and are **not** part of OSSustain unless explicitly adopted.

## 11. Functional Requirements

**Data and research pipeline**
- FR1: The pipeline shall build a cohort from a versioned configuration file containing inclusion criteria and the final repository list.
- FR2: The pipeline shall collect data through the GitHub REST API with authentication, pagination, conditional requests (ETags) where useful, retry with backoff, and rate-limit handling, and shall resume after interruption without duplicating records.
- FR3: The pipeline shall persist raw API responses locally (for reproducibility) and normalized records in PostgreSQL.
- FR4: The pipeline shall exclude bot accounts from contributor-based metrics using a documented, configurable rule.
- FR5: The pipeline shall generate prediction snapshots at fixed intervals (default: every 30 days) per repository.
- FR6: For each snapshot at date *t*, the label shall be computed from the reference window [t−90d, t) and the future window [t, t+90d). A snapshot is *labeled* only if the full future window lies within the collected data period; otherwise it is *unlabeled* (usable for inference, never for training or evaluation).
- FR7: All features for a snapshot shall use only data with timestamps strictly before *t*. Automated tests shall enforce this.
- FR8: Chronological train/validation/test splits shall be defined by configurable cut dates, with a purge gap of at least 90 days between adjacent splits so label windows do not overlap.
- FR9: The pipeline shall train all candidate models for both feature sets (activity-only; activity + extended), and shall evaluate PR-AUC, precision, recall, F1, ROC-AUC, and calibration (Brier score, calibration curve), overall and by repository size group.
- FR10: Every trained model shall be recorded with algorithm, hyperparameters, feature set, dataset version, label configuration, code revision, random seed, and artifact path.
- FR11: The pipeline shall write predictions for each repository's most recent snapshot(s) with probability and risk category, plus the explanation data.

**Backend API**
- FR12: The backend shall expose read-only REST endpoints for repositories, metric time series, predictions, explanations, model evaluations, and metadata (see Architecture.md).
- FR13: The backend shall validate all query parameters and return consistent error responses.

**Dashboard**
- FR14: Cohort Overview: list repositories with name, size group, latest risk category and probability, prediction date, and data-quality flag. Support filter and sort, and pagination if the cohort exceeds one page.
- FR15: Repository Detail: show metadata, time-series charts (commits, merged PRs, issues, active contributors, contribution concentration, newcomer counts and retention, review and response times), the current prediction, associated indicators, a prediction history, and limitation notices.
- FR16: Research Results: show model comparison tables and charts, the activity-only vs. extended comparison, feature importance, size-group breakdown, calibration, and the dataset summary.
- FR17: Methodology & Limitations: show the label definition and parameters, feature dictionary, split design, and known limitations, loaded from backend data where possible so they cannot drift from the real configuration.
- FR18: Every prediction display shall show the prediction date, model version, and a statement that the prediction concerns contribution-activity decline only.

## 12. Non-Functional Requirements

- **Reproducibility:** Fixed random seeds, recorded versions, pinned dependencies, and a documented end-to-end run order.
- **Correctness over breadth:** Leakage prevention has priority over model sophistication.
- **Performance:** Dashboard API responses under ~500 ms for typical queries on the local dataset; heavy computation is offline.
- **Accessibility:** WCAG 2.1 AA targets. Keyboard navigation, sufficient contrast, semantic structure, and a text or table alternative for every chart. Risk category is never conveyed by color alone.
- **Responsiveness:** Desktop-first; all screens usable from 360 px width (charts may scroll or reflow).
- **Reliability:** Pipeline stages are idempotent and resumable.
- **Security:** No secrets in the repository; GitHub token only in pipeline environment; the public API is read-only.
- **Maintainability:** Strict typing, tests for pipeline correctness, and clear module boundaries.
- **Portability:** Runs locally via documented setup (Docker Compose for PostgreSQL).

## 13. Important Edge Cases

- Repositories with fewer than the minimum reference-window activity are excluded from labeling (documented threshold).
- Repository renamed, transferred, archived, deleted, or made private mid-collection.
- Commits whose author has no linked GitHub account (null login); handled with a documented identity policy.
- Bot-authored commits, PRs, and comments.
- Squash or rebase merges changing commit attribution; force-pushed history.
- Contributors/statistics endpoints returning HTTP 202 or capped data. The pipeline derives contributor data from the commit list instead.
- Missing or sparse review and response data → features are `null` with an indicator, never silently zero-filled.
- Newcomers in the final months have an incomplete retention observation window → excluded from retention calculation, not treated as non-retained.
- Rate-limit exhaustion mid-run; secondary rate limits.
- Repositories with extreme size (very many PRs) making collection infeasible → handled by a documented cap or exclusion criterion.
- Snapshots with an incomplete future window → unlabeled.
- Class imbalance, or very few positive labels in some size strata → report counts and avoid overinterpreting.
- Dashboard: repository with no prediction, empty series, or API failure → explicit empty and error states.

## 14. Product Constraints

- About one month of development; one primary developer.
- GitHub API rate limits (authenticated REST: 5,000 requests/hour).
- Local-first development; no mandatory paid infrastructure.
- Stack fixed to React/TypeScript, Java/Spring Boot, PostgreSQL, Python/scikit-learn.

## 15. Assumptions

See "Planning Notes and Assumptions" (delivered alongside these documents). Key: PostgreSQL; no auth in MVP; precomputed predictions; Stitch designs for the four MVP screens will be supplied.

## 16. Required Screens (product-level)

| Screen | Purpose | Phase integrated |
|---|---|---|
| Cohort Overview | Browse and filter repositories and risk | Phase 10 |
| Repository Detail | Analytics, prediction, indicators, limitations | Phase 11 |
| Research Results | Model and feature-group comparison | Phase 12 |
| Methodology & Limitations | Definitions, splits, caveats | Phase 12 |
| Repository Comparison *(post-MVP)* | Side-by-side metrics | Phase 14 |

**Navigation:** a persistent top-level navigation with Cohort, Research, and Methodology; Repository Detail reached from the cohort list and via URL (`/repositories/:id`).
**Required states on every data-driven screen:** loading, empty, error (with retry), and success.

## 17. Success Criteria

- **Dataset:** ≥ 50 repositories collected with a published quality report.
- **Pipeline:** the full pipeline reproduces results from a clean database using documented commands.
- **Evaluation:** all models evaluated on a chronologically later test period with no detected leakage; the activity-only vs. extended comparison is reported with uncertainty (e.g., cluster bootstrap by repository).
- **Application:** all four MVP screens work against real stored data.
- **Honesty:** results and limitations are shown even if extended features show no improvement.

## 18. Feature Acceptance Criteria

| Feature | Acceptance criteria |
|---|---|
| F1 | Cohort config lists every repo with its stratum; inclusion criteria documented; re-running selection with the same config yields the same list |
| F2 | Interrupted run resumes without duplicates; raw responses cached; collection report lists per-repo completeness |
| F3 | Quality report shows missingness per repo and per feature; flagged repos are identifiable in the DB |
| F4 | Snapshots exist at monthly dates; labeled/unlabeled status correct; unit tests cover window boundaries |
| F5 | Each feature has a dictionary entry; a leakage test proves that altering post-*t* data does not change features |
| F6 | Baseline and three ML models trained for both feature sets; metrics stored per split and per size group |
| F7 | Each repo has a latest prediction with probability, category, date, model version |
| F8 | Global importance stored; each prediction has top indicators with direction and value; the UI wording avoids causal claims |
| F9 | Four screens load real data; loading, empty, and error states implemented; accessibility checks pass |
| F10 | Any displayed result can be traced to a model version and dataset version |
| F11 | A new developer can set up and run the pipeline and app by following the README |

# OSSustain: Development Phases

**Current Phase:** Phase 1: Foundation
**Current Status:** In progress / Local database and backend runtime verification pending

No phase is completed. Work proceeds in order; do not start a phase before its dependencies are done. Indicative effort assumes about one month total; the research phases (2–8) are the critical path.

**Classification:** Foundation: Phase 1. MVP: Phases 2–12. **MVP completion milestone:** end of Phase 12. Production readiness: Phase 13. Post-MVP: Phases 14–17.

---

## Phase 1: Foundation *(Foundation phase)*
- **Goal:** A runnable empty skeleton of all three components with the database and schema baseline.
- **Scope / features included:** monorepo layout; Docker Compose PostgreSQL; Spring Boot skeleton with Flyway baseline migration and a health endpoint; Python package skeleton with config loading and DB connection; Vite React TS skeleton; `.env.example`; lint/test tooling; initial README.
- **Excluded:** any data collection, models, real screens, auth.
- **Dependencies:** none.
- **Tasks:** create structure per `Architecture.md`; Flyway migrations for core tables (can be added incrementally in later phases); pipeline CLI scaffold; frontend routing shell without Stitch screens.
- **Testing:** each component builds and runs its empty test suite; backend health test with Testcontainers.
- **Acceptance criteria:** `docker compose up` starts PostgreSQL; backend starts and migrates; pipeline CLI `--help` runs; frontend starts.
- **Definition of done:** all three components run locally from documented commands; `Memory.md` updated.

## Phase 2: Research Protocol and Cohort Selection
- **Goal:** Fix the research definitions and produce a documented cohort.
- **Features included:** F1; `config/experiment.yaml` (label θ, min-activity, windows, snapshot interval, split dates, seeds); bot-handling and identity rules; cohort inclusion criteria (activity level, age, PR-volume cap, stratification by size group); API-budget estimate.
- **Excluded:** collecting full history; modeling.
- **Dependencies:** Phase 1.
- **Tasks:** `select-cohort` command; cohort config with stratum per repo; write `docs/methodology.md` with definitions and justification; schema for `repositories`, `cohorts`, `cohort_memberships`.
- **Testing:** deterministic selection test; config validation tests.
- **Acceptance criteria:** cohort of 50–100 repositories listed with strata; definitions documented; API-call budget estimated and approved (decision on GraphQL fallback made).
- **Definition of done:** config and docs committed; `Memory.md` updated.

## Phase 3: Data Collection I (Repository metadata and commits)
- **Goal:** Reliable, resumable collection of metadata and full commit history.
- **Features included:** GitHub client (auth, pagination, ETags, backoff, rate-limit handling), raw JSON cache; repos, contributors, commits tables; collection run logging.
- **Excluded:** PRs, reviews, issues.
- **Dependencies:** Phase 2.
- **Tasks:** collectors; identity policy (null authors, bots); migrations; resume logic.
- **Testing:** recorded-fixture tests; idempotency and resume tests; rate-limit simulation.
- **Acceptance criteria:** commits for the entire cohort stored; reruns create no duplicates; per-repo completeness reported.
- **Definition of done:** collection report generated; `Memory.md` updated.

## Phase 4: Data Collection II (PRs, reviews, issues) and Validation
- **Goal:** Collect collaboration data and assess its quality.
- **Features included:** F2 remainder, F3; PRs, reviews, issues, first-response timestamps; quality report; flags for repositories with insufficient collaboration data.
- **Excluded:** feature computation.
- **Dependencies:** Phase 3.
- **Tasks:** collectors within the approved API budget (REST, or a bounded GraphQL fallback if approved); `validate` command; missingness summary.
- **Testing:** fixtures for PR/review/issue edge cases; idempotency.
- **Acceptance criteria:** quality report shows completeness per repo and per data type; unusable repos flagged, not silently dropped.
- **Definition of done:** dataset version recorded; `Memory.md` updated.

## Phase 5: Snapshots and Labels
- **Goal:** Correct, leakage-safe snapshots and outcome labels.
- **Features included:** F4; monthly snapshots; reference/future activity; labels; labeled/unlabeled status; split assignment with purge gaps; label prevalence summary.
- **Excluded:** features, modeling.
- **Dependencies:** Phase 4 (commits suffice technically; run after validation).
- **Tasks:** `build-snapshots`; threshold sensitivity summary (prevalence under 0.3/0.5/0.7).
- **Testing:** window-boundary tests; unlabeled-window tests; split purge-gap tests.
- **Acceptance criteria:** prevalence per period and per size group reported; no labeled snapshot has an incomplete future window.
- **Definition of done:** `Memory.md` updated; chosen label parameters recorded.

## Phase 6: Feature Engineering
- **Goal:** Four feature groups with leakage guarantees.
- **Features included:** F5; activity, contributor diversity (active contributors, top-k concentration, Gini/entropy, contributor churn), newcomer retention, responsiveness; monthly display metrics; feature dictionary.
- **Excluded:** training.
- **Dependencies:** Phase 5.
- **Tasks:** feature modules per group; `build-features`; `feature_definitions`; `repository_metrics_monthly`.
- **Testing:** leakage test for every feature group; missing-data handling tests; hand-checked small fixtures.
- **Acceptance criteria:** features exist for all labeled snapshots; missingness reported per feature; dictionary complete.
- **Definition of done:** `Memory.md` updated.

## Phase 7: Modeling and Temporal Evaluation
- **Goal:** Answer the research questions with valid experiments.
- **Features included:** F6; threshold baseline; LR, RF, GB; activity-only vs. extended; metrics (PR-AUC, precision, recall, F1, ROC-AUC, Brier/calibration); results by size group; repository-clustered bootstrap CIs; permutation importance; model version records.
- **Excluded:** SHAP, per-prediction explanations, dashboard.
- **Dependencies:** Phase 6.
- **Tasks:** split logic; training on train, tuning on validation, one final test evaluation; store `model_versions`, `evaluation_results`, `feature_importances`; select the final model by validation criteria only.
- **Testing:** split-ordering tests; metric-computation tests on toy data; reproducibility test (same seed → same result).
- **Acceptance criteria:** all models evaluated for both feature sets; results stored; a plain-language summary of what the data show, including null results.
- **Definition of done:** `Memory.md` updated; experiment config frozen and versioned.

## Phase 8: Predictions, Explanations, and Model Versioning
- **Goal:** Stored predictions with indicators ready for the app.
- **Features included:** F7, F8, F10; risk-category cutoffs from validation; per-repository latest predictions; per-prediction indicators; limitation flags (low activity, missing data).
- **Excluded:** SHAP; on-demand prediction.
- **Dependencies:** Phase 7.
- **Tasks:** `predict` and `explain` commands; the `predictions` and `prediction_explanations` tables.
- **Testing:** every cohort repo has a prediction or a recorded reason for none; explanation wording checks.
- **Acceptance criteria:** predictions traceable to model and dataset versions; calibration check documented.
- **Definition of done:** `Memory.md` updated.

## Phase 9: Backend Read API
- **Goal:** Stable, documented REST API over the stored results.
- **Features included:** FR12–FR13; all endpoints listed in `Architecture.md`; OpenAPI document; error handling; CORS config.
- **Excluded:** write endpoints, auth.
- **Dependencies:** Phase 8.
- **Tasks:** entities/projections, services, controllers, DTOs, global exception handler, pagination and filters.
- **Testing:** Testcontainers integration tests per endpoint, including empty and invalid-parameter cases.
- **Acceptance criteria:** all endpoints return real data; OpenAPI is generated; frontend types can be generated from it.
- **Definition of done:** `Memory.md` updated (API Changes section).

## Phase 10: Frontend Foundation and Cohort Overview
- **Goal:** Typed frontend foundation plus the first real screen.
- **Features included:** API client and generated types; routing and navigation; shared loading/empty/error components; **Stitch screen: Cohort Overview** integrated (list, filters, sorting, pagination); dataset summary on the screen.
- **Excluded:** Repository Detail, Research, Methodology screens.
- **Dependencies:** Phase 9; Stitch designs for this screen available (if not, build a functional unstyled version and mark the screen pending in `Memory.md`).
- **Tasks:** review and componentize Stitch output; connect to `GET /repositories`; accessibility and responsive pass.
- **Testing:** component tests (loading/error/empty/success); filter-in-URL tests.
- **Acceptance criteria:** the cohort list shows real data with working filters; keyboard navigable.
- **Definition of done:** `Memory.md` UI sections updated.

## Phase 11: Repository Detail Screen
- **Goal:** The core analytics-and-risk experience.
- **Features included:** **Stitch screen: Repository Detail**; time-series chart components with table fallbacks; prediction card (probability, category, date, model version); indicators with association wording; prediction history; limitation notices.
- **Excluded:** comparison, SHAP.
- **Dependencies:** Phase 10.
- **Tasks:** chart wrappers; hooks for metrics/predictions/explanations; handling of repos with no prediction or sparse data.
- **Testing:** component tests incl. missing-data and no-prediction states; chart table-fallback tests.
- **Acceptance criteria:** detail page shows real analytics and prediction for every cohort repo; limitations visible; accessible.
- **Definition of done:** `Memory.md` updated.

## Phase 12: Research Dashboard, Methodology, and Documentation *(MVP completion)*
- **Goal:** Present the experimental evidence and finish the MVP.
- **Features included:** **Stitch screens: Research Results and Methodology & Limitations**; model comparison, activity-only vs. extended, size-group results, calibration, feature importance, dataset summary; label definition and feature dictionary display; F11 (README, setup and run order, reproducibility notes).
- **Excluded:** hosting, comparison view, SHAP.
- **Dependencies:** Phases 7–11.
- **Tasks:** chart and table components with accessible alternatives; data-driven methodology content; end-to-end run on a clean database following the README.
- **Testing:** component tests; one end-to-end smoke test (optional Playwright); clean-setup walkthrough.
- **Acceptance criteria:** all PRD MVP features F1–F11 meet their acceptance criteria.
- **Definition of done / MVP completion milestone:** a new developer can reproduce the dataset-to-dashboard pipeline from the README; all four MVP screens work with real data; results and limitations are displayed honestly.

## Phase 13: Production Readiness *(Production readiness phase)*
- **Goal:** Make the MVP deployable and robust.
- **Features included:** containerize backend and frontend; production configuration and environment handling; database dump/restore; security review and dependency audit; accessibility audit; performance check; optional low-cost hosting; CI.
- **Excluded:** new product features.
- **Dependencies:** Phase 12.
- **Tasks:** Dockerfiles; production config; audits; CI pipeline; deployment docs.
- **Testing:** full test suite in CI; smoke test of the deployed build.
- **Acceptance criteria:** documented deployment from a clean machine; no high-severity dependency findings; accessibility audit issues triaged.
- **Definition of done:** `Memory.md` Deployment Status updated.

---

## Post-MVP Phases (optional; not part of the MVP)

### Phase 14: Repository Comparison
Side-by-side metrics for 2–4 repositories (new Stitch screen, API endpoint `GET /compare`). Depends on Phase 12. Excludes on-demand analysis.

### Phase 15: SHAP and Robustness Analyses
SHAP explanations (added dependency requires approval); alternative thresholds and activity definitions surfaced in the dashboard. Depends on Phase 12.

### Phase 16: On-Demand Repository Analysis
Collection and prediction for user-submitted repositories (requires an architecture revision: job handling, live-inference path, rate-limit strategy). Depends on Phase 13; requires an explicit approved architecture change first.

### Phase 17: Authentication and Admin (conditional)
Only if Phase 16 or admin features are adopted. Spring Security, roles, protected endpoints.

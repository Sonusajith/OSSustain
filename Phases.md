# OSSustain: Development Phases

**Current Phase:** Phase 17: Authentication and Admin
**Current Status:** Phase 16 merged to `main` in PR #16 (`be80014`, implementation `b0c87ee`). Phase 17 is approved to begin; authentication/session and admin scope is being proposed before implementation.

Phase 1 is complete. Work proceeds in order; do not start a phase before its dependencies are done. Indicative effort assumes about one month total; the research phases (2–8) are the critical path.

**Classification:** Foundation: Phase 1. MVP: Phases 2–12. **MVP completion milestone:** end of Phase 12. Production readiness: Phase 13. Post-MVP: Phases 14–17. All defined phases are complete; the next phase has not been scoped.

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
- **Goal:** Let users inspect stored data for 2–4 repositories side by side.
- **Features included:** comparison dashboard screen, cohort repository selection, latest risk estimates, and latest stored monthly metrics; read-only API endpoint `GET /api/v1/compare`.
- **Dependencies:** Phase 12 and the repository/detail API from Phase 9.
- **Tasks:** typed API contract and generated frontend types; validation for 2–4 distinct current-cohort repository IDs; responsive and accessible comparison table with loading, empty, error, and success states; navigation and documentation.
- **Design:** no Phase 14 Stitch comparison screen exists in `UIUX/`; implement a functional screen consistent with the current dashboard and mark design follow-up in `Memory.md`.
- **Testing:** backend integration coverage for selected ordering, invalid count, duplicates, and IDs outside the cohort; frontend MSW coverage for comparison success, error recovery, and empty cohort; full CI.
- **Definition of done:** comparison API and screen use live stored data, targeted tests pass, and `Memory.md` records implementation and verification. Excludes on-demand analysis.

### Phase 15: SHAP and Robustness Analyses
- **Goal:** Provide SHAP probability attributions for stored model predictions and quantify sensitivity to alternate decline thresholds and activity definitions.
- **Features included:** repository detail explanations identify SHAP versus the threshold-rule baseline substitution method; research results show held-out PR-AUC, F1, and Brier scores under θ 0.30, θ 0.70, and commits plus merged pull requests.
- **Analysis protocol:** robustness reuses fixed validation-selected model test probabilities. It does not refit or tune using test outcomes. Repository-cluster bootstrap intervals are reported; alternate activity outcomes apply the configured minimum reference activity.
- **SHAP protocol:** pinned SHAP with a validation-only background and probability-scale contributions. The threshold-rule baseline has no fitted estimator and keeps its explicitly identified substitution explanation.
- **Dependencies:** SHAP 0.54.1 was approved and pinned in `pipeline/pyproject.toml` and `pipeline/requirements.lock`.
- **Design:** no Phase 15 Stitch screen exists; additions extend the current Repository Detail and Research Results screens.
- **Testing:** pipeline, backend migration/API, and frontend suites; pipeline lint; frontend lint and production build; dependency audit.
- **Definition of done:** stored explanations and robustness metrics use the declared protocols, are served and displayed with clear method labels, targeted tests pass, and `Memory.md` records verification.

### Phase 16: On-Demand Repository Analysis
- **Goal:** Collect data and produce a prediction for a user-submitted public GitHub repository.
- **Architecture:** Approved database-backed queue and one Python worker; worker-only GitHub token; separate on-demand result storage; 180-day collection; read-only trained artifacts; limits of 300 requests/job, 1,000/hour overall, 20 waiting jobs, 3 submissions/IP/hour, one active job/repository, and a 24-hour result cache. Expire completed job/result rows after 30 days. Raw event responses are not persisted.
- **Dependencies:** Phase 13; API, collection pipeline, trained model artifacts, and prediction code from earlier phases.
- **Current status:** Complete and merged to `main` in PR #16 (`be80014`). A live GitHub analysis remains a pre-release smoke-test follow-up.
- **Definition of done:** public-only repository submission and status API; durable bounded jobs and results isolated from research data; a restart-safe Python worker collects within the approved budget and scores with an existing selected artifact; accessible UI with loading/empty/error/success states; setup and retention documented; backend, worker, and frontend verification passes; `Memory.md` records handoff.

### Phase 17: Authentication and Admin (conditional)
Phase 16 was adopted and Phase 17 is complete.
- **Goal:** Add account authentication and role-based access around on-demand analysis and administrative operations.
- **Scope:** Spring Security; researcher and administrator roles; protected analysis operations with ownership checks; an administrator interface for account and job oversight; no public self-registration.
- **Architecture decision:** approved by the project owner: invite-only accounts, environment-bootstrapped first administrator, PostgreSQL-backed sessions, public research reads, owned analysis access, and audited administrator account/job controls. See `docs/phase17-architecture-proposal.md`.
- **Dependencies:** Phase 16 and its analysis job/result schema.
- **Testing:** backend authorization and session integration tests; migration tests; frontend login/role/access-denied states; full CI.
- **Definition of done:** documented secure account provisioning; protected endpoints enforce roles and per-user analysis access; admin actions are audited and tested; no secrets are committed; `Memory.md` records verification and handoff.
- **Status:** merged in PR #17 (`815f1fd`, implementation commit `35cbae0`). Local PostgreSQL applied V12; first-admin sign-in, forced password rotation, logout, and sign-in with the rotated password were verified. Local credentials remain in ignored `.env`.

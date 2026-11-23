# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phases 1–12 are complete and merged to main. Phase 12 merged in PR #12 (`271b24b`). Phase 5 produced 2,300 versioned snapshots across all 50 repositories: 395 labeled, 1,755 below the reference-activity minimum, and 150 with incomplete futures. Excluding purge gaps leaves 342 labeled train/validation/test snapshots. Phase 6 stored 23 features for every snapshot. PostgreSQL contains metadata and full commit histories for the 50-repository cohort (55,206 unique commits; 2,638 anonymized contributors), plus Phase 4 collaboration data (2,659 pull requests, 2,285 reviews, 17,647 non-PR issues). Collection completed for all 50 repositories within the approved caps. The quality report records four flags: two one-record differences from frozen screening counts and two repositories with zero collaboration events.

## Current Phase
Phase 13: Production Readiness

## Current Task
Phase 12 merged in PR #12 (`271b24b`). Phase 13 production-readiness implementation is ready for review on `phase-13/production-readiness`.

## Last Completed Task
Phase 12 Research Results and Methodology merged in PR #12 (`271b24b`), including live research API data, accessible chart tables, responsive layouts, loading/empty/error states, reproduction run order, and the discoverable `/api/v1` index. The previous completed phase was Phase 11 Repository Detail, merged in PR #11 (`85f6e65`).

## Completed Phases
Phase 1: Foundation
Phase 2: Research Protocol and Cohort Selection
Phase 3: Data Collection I (Repository metadata and commits)
Phase 4: Data Collection II (PRs, reviews, issues) and Validation
Phase 5: Snapshots and Labels
Phase 6: Feature Engineering
Phase 7: Modeling and Temporal Evaluation — merged to main in PR #7 (`04cf1f7`)
Phase 8: Predictions, Explanations, and Model Versioning — merged to main in PR #8 (`ced3c39`)
Phase 9: Backend Read API — merged to main in PR #9 (`8e32a6b`)
Phase 10: Frontend Foundation and Cohort Overview — merged to main in PR #10 (`c281ca7`)
Phase 11: Repository Detail Screen — merged to main in PR #11 (`85f6e65`)
Phase 12: Research Dashboard, Methodology, and Documentation — merged to main in PR #12 (`271b24b`)

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.
- Phase 2: versioned label/split/identity protocol; deterministic stratified 50-repository cohort selected from a recorded GitHub REST candidate screen; repositories/cohorts/cohort_memberships Flyway schema; methodology and approved API budget.
- Phase 3: privacy-filtered GitHub REST cache and client; repository metadata and commit collection; HMAC contributor identities; idempotent page-level resume; collection run history; full-cohort report.
- Phase 4: privacy-filtered PR/review/issue collection; first-response timestamps; request caps with durable append-only local journal; resumable, idempotent stages; pagination fallback for single-day GitHub Search overflow; per-repository quality validation.

- Phase 5: versioned snapshot builder, UTC half-open windows, explicit unlabeled reasons, chronological split/purge assignment, input fingerprints, atomic reruns, and prevalence summaries.
- Phase 6: 23 leakage-safe registered features, per-feature missingness and completeness summaries, monthly display metrics, content-addressed/idempotent storage, and the `build-features` CLI. Inputs are versioned V6 snapshots and events strictly before each prediction date.
- Phase 7: frozen model grid, train-only preprocessing, validation-only hyperparameter/cutoff selection, held-out test evaluation, cluster-bootstrap intervals and paired feature-family comparison, validation importance, versioned model records, and local artifacts.

## Features In Progress
Phase 13: production deployment, operations, and security checks are implemented on `phase-13/production-readiness`; the GitHub CI run and merge remain pending review.

## Pending Tasks
- Review and merge the Phase 13 branch after its GitHub CI run passes.
- Retry a full backend container OS vulnerability scan: local Docker Scout could not fetch its Java vulnerability database (EOF), and OSV image extraction could not resolve the base-image chain. The backend now uses the updated Temurin Alpine runtime; source-manifest scans are clean.
- Before public hosting, perform a browser keyboard walkthrough and Lighthouse audit against the chosen deployed URL; no public host is configured.
- The Phase 12 full pipeline rebuild against a clean database was not repeated; documented pipeline steps and existing live dataset/API verification are available.
- Local detailed reports remain ignored in `pipeline/data/reports/`; aggregate results are committed in `docs/phase4-data-quality.md` and `docs/phase5-snapshots.md`.

## Known Bugs
The frozen screen and final collection differ by one issue for `protobuf-net/protobuf-net` and one pull request for `longitachi/ZLPhotoBrowser`. Two repositories (`kubernetes/client-go` and `hoochanlon/hamuleite`) have zero collaboration events, matching their frozen zero counts. These are recorded as quality flags; no stage is incomplete.

## Current Blockers
GitHub CLI is unavailable; use the Phase 13 branch comparison link to open its PR. A full backend container OS scan could not complete because local scanners failed while fetching their Java vulnerability database/base-image metadata; this is recorded in Pending Tasks. Port 8080 returned 403 in a previous workstation session, so the isolated production smoke deployment uses port 8088. The Stitch HTML contains unsupported sample claims and figures; it was used only as visual reference, and displayed results come from the real API records.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
- Approved frontend dependencies: TanStack Query 5.107.1, `openapi-typescript` 7.13.0, and MSW 3.0.5 for API request mocking in tests.
- Python direct and resolved pins are in `pipeline/pyproject.toml` and `pipeline/requirements.lock`; Phase 7 adds the approved scikit-learn 1.9.1 and joblib 1.6.0 modeling dependencies.
- Phase 7 selects hyperparameters by validation PR-AUC, chooses probability cutoffs by validation F1, then evaluates the refit configuration on held-out test. The highest validation PR-AUC selects one model per family; no test metric influences selection.
- Phase 2 introduced no dependencies; config validation and cohort selection use already pinned Pydantic and PyYAML.
- Approved Phase 2 collection decision: REST-only; 12,500 authenticated requests as the stop cap for PR/review/response collection (about 2.5 quota-hours), excluding commits and non-PR issues.
- Approved Phase 4 budgets: hard stop at 12,500 requests for PR/review/response collection and 25,000 requests for non-PR issue collection.
- Phase 4 request accounting uses the maximum of database run totals and the durable local ledger total to avoid double counting after completed runs. The ledger uses an append-only journal under `%LOCALAPPDATA%/ossustain/` to avoid synced-folder file replacement locks.
- GitHub Search's single-day 1,000-result overflow is collected through paginated repository issue listing, then filtered to the frozen observation window.
- Phase 3 collection uses the standard-library `urllib` client and existing pinned dependencies. JSON cache bodies are privacy-filtered before disk writes; contributor keys use HMAC-SHA256 with `OSSUSTAIN_HASH_SECRET`.
- The final collection totals are 50 repositories, 55,206 unique commits, 2,638 contributors, and 50 completed commit checkpoints. A rerun verified idempotence; `collection_runs` retains one historical transient failure followed by successful recovery.

## Architecture Changes
Approved by the project owner: upgraded the backend from Spring Boot 3.5.16 to Spring Boot 4.1.2. The Java target remains 21; Boot 4 starter modules are used.

## Database Changes
Added Flyway V1 foundation baseline, V2 cohort-selection tables, V3 core data tables, V4 `collection_runs`, and V5 Phase 4 run stages/review IDs.

Phase 5 adds V6 `dataset_versions` and `snapshots` for immutable research inputs, label completeness, and chronological splits. Existing V3 `repo_windows`/`labels` remain the development-seed/dashboard scaffold; Phase 6 consumes the versioned research snapshots. Phase 6 adds V7 `feature_sets`, `feature_definitions`, `snapshot_features`, and `repository_metrics_monthly`. Phase 7 adds V8 model/evaluation/importance records and versioned prediction references. Phase 8 adds V9 validation-derived risk cutoffs, prediction dates and limitation flags, per-repository prediction outcomes, and per-prediction explanations. The feature runner reads latest completed stages from `collection_runs`; resumable `collection_progress` covers commits only.

## API Changes
Spring Boot Actuator health remains available at `/actuator/health`. Phase 9 adds read-only endpoints for repository list/detail, monthly metrics, prediction history/latest indicators, models, evaluations, feature importance, dataset summary, and label/feature definitions. `GET /api/v1` now returns an API index so opening the base URL is informative; the dashboard runs separately at Vite's `http://localhost:5173`. Lists use bounded pagination and documented filters. Errors share `{timestamp,status,code,message,path}`. CORS defaults to `http://localhost:5173` and is configurable with `FRONTEND_ORIGIN`. OpenAPI 3.1 is served at `/openapi.yaml`.

## Important Files
- `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`, `config/experiment.yaml`, `config/modeling.yaml`, `config/cohort-candidates.yaml`, `config/cohort.yaml`, `docs/methodology.md`, `docs/phase4-data-quality.md`, `docs/phase7-modeling.md`, `docs/phase8-predictions.md`
- `backend/pom.xml`, `backend/src/main/`, `backend/src/test/`
- `pipeline/pyproject.toml`, `pipeline/requirements.lock`, `pipeline/src/`, `pipeline/tests/`
- `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/src/`

## Reusable Components
`MetricHistoryChart`, `RepositoryMetrics`, `PredictionCard`, and `PredictionHistory` were added for the Repository Detail screen.

## Dependencies Added
Phase 7 adds scikit-learn 1.9.1 and joblib 1.6.0 (approved by the project owner; versions verified from PyPI). Transitive versions are pinned in `pipeline/requirements.lock`. No additional services.

## Required Environment Variables
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `OSSUSTAIN_DATABASE_URL`, `SPRING_DATASOURCE_URL`, `VITE_API_BASE_URL`, `GITHUB_TOKEN`, and `OSSUSTAIN_HASH_SECRET` (documented in `.env.example`).

## UI Integration Status
Phase 10 Cohort Overview and Phase 11 Repository Detail are integrated. Phase 12 Research Results and Methodology & Limitations are integrated using `UIUX/ossustain_empirical_research_platform/code.html` and `UIUX/empirical_observational_research/DESIGN.md` as visual references; unsupported sample claims were replaced with live API values.

## Google Stitch Screens Integrated
`UIUX/cohort_overview` — Cohort Overview (Phase 10); `UIUX/repository_detail_facebook_react` — Repository Detail (Phase 11).

## Google Stitch Screens Pending
Research Results and Methodology & Limitations (Phase 12, in progress). Repository Comparison (Phase 14, post-MVP).

## Temporary Workarounds
Maven and Docker Desktop work locally. Use the quoted JVM timezone option for Windows backend tests. GitHub CLI is absent and the collection token cannot create PRs (HTTP 403); PR #5 was created through the signed-in browser without expanding token permissions.

## Testing Status
- Python: `pytest pipeline/tests -q` — 80 passed, 1 existing opt-in snapshot DB test skipped. Ruff checks and formatting check for changed files passed. `predict --help` and `explain --help` passed.
- Backend before Phase 9: 9 tests passed, including fresh V1–V9 migration coverage. Phase 9 final run: `mvn -B -ntp "-Duser.timezone=Asia/Kolkata" -f backend/pom.xml test` — 14 tests passed (5 API integration test groups plus 9 existing migration/health checks); Testcontainers used Docker Desktop.
- Phase 9 OpenAPI YAML parsed successfully with PyYAML: OpenAPI 3.1, 10 product paths, 17 schemas.
- Phase 10 frontend: frozen-lock install and OpenAPI type generation passed; `pnpm lint`, `pnpm test` (7 passed), and `pnpm build` passed after the table header fix. Live API check against local PostgreSQL returned all 50 cohort repositories and dataset summary #1.
- Phase 11 frontend: `pnpm lint`, `pnpm test` (11 passed), and `pnpm build` passed. Live API smoke checks returned repository metadata, 46 monthly metric points, the latest prediction with indicators, and prediction history for a real cohort repository.
- Phase 12 verification: frontend lint passed, 17 component tests passed, production build passed. Backend integration suite passed (14 tests). Live API smoke check returned API index at `/api/v1` plus 8 models, 454 evaluations, 23 selected-model importance rows, 23 feature definitions, 50 repositories, 2,300 snapshots, 395 labeled snapshots, 600 test snapshots (88 labeled), and four repository quality-flag records. The selected test PR-AUC difference (extended minus activity-only) is +0.188 (95% repository-cluster CI −0.059 to +0.391), which includes zero.
- Local PostgreSQL migrated to V9. Live Phase 8 rerun persisted 50 predictions/outcomes and 150 explanation indicators; all 50 repositories have a prediction and all were explained. Model version 3 has validation-derived risk cutoffs 0.4445/0.6041.
- Phase 7 run persisted 8 model versions (2 selected), 454 evaluation rows, and 78 feature-importance rows; six joblib artifacts are ignored under `pipeline/artifacts/`. The paired test PR-AUC difference was +0.188 (95% CI −0.059 to +0.391), inconclusive.
- Docker Desktop and local PostgreSQL remain running.
- Full cohort: 2,300 snapshots, 395 labeled (149 positive at theta 0.5), 1,755 low-reference, 150 incomplete-future. Of the labeled rows, 53 are purged and never eligible for modeling. Independent SQL recomputation: zero mismatches.
- Earlier frontend foundation checks passed (ESLint, 2 Vitest tests, TypeScript/build); frontend untouched in Phase 5.

## Deployment Status
Phase 13 local stack passed container smoke checks at `http://localhost:8088`; frontend/backend/PostgreSQL health checks are green. Backup creation and restore into a new database passed, including overwrite and path-traversal refusal checks. Frontend image high/critical scan found no vulnerable packages. Python `pip-audit`, frontend production `pnpm audit`, and the pinned source-manifest scan found no known vulnerabilities. Backend runtime uses Temurin 21 Alpine with OS packages upgraded at build; its container-level OS scan remains pending because local scanner database/registry access failed. No public hosting target was selected. GitHub CI will run after the branch is pushed for review. Browser-level keyboard and Lighthouse checks remain for the eventual public deployment.

## Important Context for the Next AI Session
- The owner confirmed Phase 5 on 2026-11-18. All four Phase 4 quality flags are retained; no repositories are silently excluded.
- The local `.env` is ignored by Git. Never print, paste, or commit its token or hash secret.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
Open the Phase 13 PR from the branch comparison link, confirm CI passes, and retry the backend image vulnerability scan. Before public hosting, select a target and run the documented keyboard and Lighthouse checks.

## Last Updated
2026-11-23, `phase-13/production-readiness` — production images, isolated deployment, safe backup/restore, local smoke checks, and available security scans completed; backend image scan needs a retry because scanner database/base-image access failed.

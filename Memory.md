# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phases 1–6 are complete and merged to main. Phase 5 produced 2,300 versioned snapshots across all 50 repositories: 395 labeled, 1,755 below the reference-activity minimum, and 150 with incomplete futures. Excluding purge gaps leaves 342 labeled train/validation/test snapshots. Phase 6 stored 23 features for every snapshot. PostgreSQL contains metadata and full commit histories for the 50-repository cohort (55,206 unique commits; 2,638 anonymized contributors), plus Phase 4 collaboration data (2,659 pull requests, 2,285 reviews, 17,647 non-PR issues). Collection completed for all 50 repositories within the approved caps. The quality report records four flags: two one-record differences from frozen screening counts and two repositories with zero collaboration events.

## Current Phase
Phase 7: Modeling and Temporal Evaluation — implementation complete; PR pending

## Current Task
Phase 6 PR #6 merged to main as `ba7dad5`. Phase 7 code and the frozen cohort evaluation are complete on `phase-7/modeling`; review/merge is pending.

## Last Completed Task
Phase 7 ran eight model configurations on dataset 1: threshold baseline, Logistic Regression, Random Forest, and Gradient Boosting for activity-only and extended features. Two models were selected using validation only. The paired test PR-AUC difference (extended minus activity-only) was +0.188 (95% repository-cluster bootstrap CI −0.059 to +0.391), which is inconclusive. Test data contain 88 labeled snapshots across 12 repositories (27.3% positive). Full results are in `docs/phase7-modeling.md`; the detailed local report is ignored at `pipeline/data/reports/phase7-models.json`. Phase 6 PR #6 merged at `ba7dad5` with 23 leakage-safe features for all snapshots. Phase 5 dataset 1 hash: `20186258c8680c150ec8834af87bff9b4e9c950efef22ee8f022c2f8b8dcccab`.

## Completed Phases
Phase 1: Foundation
Phase 2: Research Protocol and Cohort Selection
Phase 3: Data Collection I (Repository metadata and commits)
Phase 4: Data Collection II (PRs, reviews, issues) and Validation
Phase 5: Snapshots and Labels
Phase 6: Feature Engineering
Phase 7: Modeling and Temporal Evaluation — implementation complete; PR pending

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.
- Phase 2: versioned label/split/identity protocol; deterministic stratified 50-repository cohort selected from a recorded GitHub REST candidate screen; repositories/cohorts/cohort_memberships Flyway schema; methodology and approved API budget.
- Phase 3: privacy-filtered GitHub REST cache and client; repository metadata and commit collection; HMAC contributor identities; idempotent page-level resume; collection run history; full-cohort report.
- Phase 4: privacy-filtered PR/review/issue collection; first-response timestamps; request caps with durable append-only local journal; resumable, idempotent stages; pagination fallback for single-day GitHub Search overflow; per-repository quality validation.

- Phase 5: versioned snapshot builder, UTC half-open windows, explicit unlabeled reasons, chronological split/purge assignment, input fingerprints, atomic reruns, and prevalence summaries.
- Phase 6: 23 leakage-safe registered features, per-feature missingness and completeness summaries, monthly display metrics, content-addressed/idempotent storage, and the `build-features` CLI. Inputs are versioned V6 snapshots and events strictly before each prediction date.
- Phase 7: frozen model grid, train-only preprocessing, validation-only hyperparameter/cutoff selection, held-out test evaluation, cluster-bootstrap intervals and paired feature-family comparison, validation importance, versioned model records, and local artifacts.

## Features In Progress
Phase 7 implementation and evaluation are complete on `phase-7/modeling`; review/merge is pending.

## Pending Tasks
- Review and merge the Phase 7 pull request; do not begin Phase 8 until the owner confirms.
- Local detailed reports remain ignored in `pipeline/data/reports/`; aggregate results are committed in `docs/phase4-data-quality.md` and `docs/phase5-snapshots.md`.

## Known Bugs
The frozen screen and final collection differ by one issue for `protobuf-net/protobuf-net` and one pull request for `longitachi/ZLPhotoBrowser`. Two repositories (`kubernetes/client-go` and `hoochanlon/hamuleite`) have zero collaboration events, matching their frozen zero counts. These are recorded as quality flags; no stage is incomplete.

## Current Blockers
Most snapshots fall below the frozen minimum activity; only 342 labeled snapshots belong to train/validation/test (164/90/88). Test has 88 snapshots from 12 repositories; the paired PR-AUC CI includes zero. Treat this as a sample-size limitation, not a reason to retune using test results. Four Phase 4 quality flags remain retained.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
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

Phase 5 adds V6 `dataset_versions` and `snapshots` for immutable research inputs, label completeness, and chronological splits. Existing V3 `repo_windows`/`labels` remain the development-seed/dashboard scaffold; Phase 6 consumes the versioned research snapshots. Phase 6 adds V7 `feature_sets`, `feature_definitions`, `snapshot_features`, and `repository_metrics_monthly`, with dataset-consistent foreign keys and per-dataset content hashes. Phase 7 adds V8 `model_versions`, `evaluation_results`, and `feature_importances`, and extends `predictions` to reference either the legacy model/window pair or the versioned model/snapshot pair. The feature runner reads latest completed stages from `collection_runs`; resumable `collection_progress` covers commits only.

## API Changes
Enabled Spring Boot Actuator health at `/actuator/health`. No product API endpoints yet.

## Important Files
- `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`, `config/experiment.yaml`, `config/modeling.yaml`, `config/cohort-candidates.yaml`, `config/cohort.yaml`, `docs/methodology.md`, `docs/phase4-data-quality.md`, `docs/phase7-modeling.md`
- `backend/pom.xml`, `backend/src/main/`, `backend/src/test/`
- `pipeline/pyproject.toml`, `pipeline/requirements.lock`, `pipeline/src/`, `pipeline/tests/`
- `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/src/`

## Reusable Components
None yet.

## Dependencies Added
Phase 7 adds scikit-learn 1.9.1 and joblib 1.6.0 (approved by the project owner; versions verified from PyPI). Transitive versions are pinned in `pipeline/requirements.lock`. No additional services.

## Required Environment Variables
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `OSSUSTAIN_DATABASE_URL`, `SPRING_DATASOURCE_URL`, `VITE_API_BASE_URL`, `GITHUB_TOKEN`, and `OSSUSTAIN_HASH_SECRET` (documented in `.env.example`).

## UI Integration Status
Foundation routing shell only; no Stitch screen integrated.

## Google Stitch Screens Integrated
None.

## Google Stitch Screens Pending
Cohort Overview (Phase 10), Repository Detail (Phase 11), Research Results and Methodology & Limitations (Phase 12). Repository Comparison (Phase 14, post-MVP).

## Temporary Workarounds
Maven and Docker Desktop work locally. Use the quoted JVM timezone option for Windows backend tests. GitHub CLI is absent and the collection token cannot create PRs (HTTP 403); PR #5 was created through the signed-in browser without expanding token permissions.

## Testing Status
- Phase 7 Python: 74 tests passed, 1 existing opt-in local database test skipped; Ruff and CLI help passed. Unit checks cover hand-calculated metrics, tied ranks, cutoff choice, calibration bins, repository bootstrap, estimator repeatability, train-only imputation, and strict chronological split ordering.
- Backend: 9 tests passed with `mvn -B -ntp "-Duser.timezone=Asia/Kolkata" -f backend/pom.xml test`; includes V1–V8 migrations and versioned prediction constraints.
- Local PostgreSQL migrated to V8. The live Phase 7 run persisted 8 model versions (2 selected), 454 evaluation rows, and 78 feature-importance rows; six joblib artifacts are ignored under `pipeline/artifacts/`. The paired test PR-AUC difference was +0.188 (95% CI −0.059 to +0.391), inconclusive.
- Docker Desktop and local PostgreSQL remain running.
- Full cohort: 2,300 snapshots, 395 labeled (149 positive at theta 0.5), 1,755 low-reference, 150 incomplete-future. Of the labeled rows, 53 are purged and never eligible for modeling. Independent SQL recomputation: zero mismatches.
- Earlier frontend foundation checks passed (ESLint, 2 Vitest tests, TypeScript/build); frontend untouched in Phase 5.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- The owner confirmed Phase 5 on 2026-11-18. All four Phase 4 quality flags are retained; no repositories are silently excluded.
- The local `.env` is ignored by Git. Never print, paste, or commit its token or hash secret.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
Review and merge the Phase 7 branch/PR. After owner confirmation, begin Phase 8; do not tune against the completed test results.

## Last Updated
2026-11-19, `phase-7/modeling` — code/tests and held-out run complete; results documented; awaiting PR review/merge.

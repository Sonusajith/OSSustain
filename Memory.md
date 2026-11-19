# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phases 1–5 are complete. Phase 5 adds 2,300 versioned snapshots across all 50 repositories: 395 labeled, 1,755 below the reference-activity minimum, and 150 with incomplete futures. Excluding purge gaps leaves 342 labeled train/validation/test snapshots. PostgreSQL contains metadata and full commit histories for the 50-repository cohort (55,206 unique commits; 2,638 anonymized contributors), plus Phase 4 collaboration data (2,659 pull requests, 2,285 reviews, 17,647 non-PR issues). Collection completed for all 50 repositories within the approved caps. The quality report records four flags: two one-record differences from frozen screening counts and two repositories with zero collaboration events.

## Current Phase
Phase 5: Snapshots and Labels — complete; Phase 6 not started

## Current Task
Phase 5 acceptance is complete and [PR #5](https://github.com/Sonusajith/OSSustain/pull/5) is open into main. Phase 4 PR #4 remains a prerequisite; merge it first. This branch includes those commits and the measured results/handoff.

## Last Completed Task
Built 46 snapshots per repository for all 50 repositories using the frozen protocol (theta 0.5, 20 minimum reference commits, 90-day windows, 30-day interval). Dataset ID 1 / hash `20186258c8680c150ec8834af87bff9b4e9c950efef22ee8f022c2f8b8dcccab` was produced by committed revision `61ecefb`. Independent SQL found zero count/label mismatches. Reruns preserve version, snapshot IDs, and labels. See `docs/phase5-snapshots.md` for actual prevalence by date, split, size group, and thresholds 0.3/0.5/0.7.

## Completed Phases
Phase 1: Foundation
Phase 2: Research Protocol and Cohort Selection
Phase 3: Data Collection I (Repository metadata and commits)
Phase 4: Data Collection II (PRs, reviews, issues) and Validation
Phase 5: Snapshots and Labels

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.
- Phase 2: versioned label/split/identity protocol; deterministic stratified 50-repository cohort selected from a recorded GitHub REST candidate screen; repositories/cohorts/cohort_memberships Flyway schema; methodology and approved API budget.
- Phase 3: privacy-filtered GitHub REST cache and client; repository metadata and commit collection; HMAC contributor identities; idempotent page-level resume; collection run history; full-cohort report.
- Phase 4: privacy-filtered PR/review/issue collection; first-response timestamps; request caps with durable append-only local journal; resumable, idempotent stages; pagination fallback for single-day GitHub Search overflow; per-repository quality validation.

- Phase 5: versioned snapshot builder, UTC half-open windows, explicit unlabeled reasons, chronological split/purge assignment, input fingerprints, atomic reruns, and prevalence summaries.

## Features In Progress
None. Phase 5 meets its Definition of Done; Phase 6 awaits owner confirmation.

## Pending Tasks
- Review and merge Phase 4 PR #4 before the dependent Phase 5 PR.
- Phase 6: leakage-safe feature engineering, only after owner confirmation.
- Local detailed reports remain ignored in `pipeline/data/reports/`; aggregate results are committed in `docs/phase4-data-quality.md` and `docs/phase5-snapshots.md`.

## Known Bugs
The frozen screen and final collection differ by one issue for `protobuf-net/protobuf-net` and one pull request for `longitachi/ZLPhotoBrowser`. Two repositories (`kubernetes/client-go` and `hoochanlon/hamuleite`) have zero collaboration events, matching their frozen zero counts. These are recorded as quality flags; no stage is incomplete.

## Current Blockers
No Phase 5 implementation blockers. Most snapshots fall below the frozen minimum activity; only 342 labeled snapshots belong to train/validation/test (164/90/88). Treat this as a sample-size limitation, not a reason to retune thresholds using test results. Four Phase 4 quality flags remain retained.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
- Python direct and resolved pins are in `pipeline/pyproject.toml` and `pipeline/requirements.lock`.
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

Phase 5 adds V6 `dataset_versions` and `snapshots` for immutable research inputs, label completeness, and chronological splits. Existing V3 `repo_windows`/`labels` remain the development-seed/dashboard scaffold; Phase 6 should consume the versioned research snapshots. No new dependencies.

## API Changes
Enabled Spring Boot Actuator health at `/actuator/health`. No product API endpoints yet.

## Important Files
- `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`, `config/experiment.yaml`, `config/cohort-candidates.yaml`, `config/cohort.yaml`, `docs/methodology.md`, `docs/phase4-data-quality.md`
- `backend/pom.xml`, `backend/src/main/`, `backend/src/test/`
- `pipeline/pyproject.toml`, `pipeline/requirements.lock`, `pipeline/src/`, `pipeline/tests/`
- `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/src/`

## Reusable Components
None yet.

## Dependencies Added
Pinned in component files. No dependencies or services added in Phase 2.

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
- Phase 5 Python: 59 tests passed with `OSSUSTAIN_TEST_SNAPSHOTS=1`, including real-database rerun idempotency; Ruff passed. Without that flag, 58 pass and the local-database test is skipped.
- Backend: 8 tests passed with `mvn -B -ntp "-Duser.timezone=Asia/Kolkata" -f backend/pom.xml test`; includes V1–V6 migrations and constraints against incomplete labels and duplicate snapshot keys.
- Local PostgreSQL migrated to V6 through Spring Boot/Flyway; temporary backend process stopped afterward, PostgreSQL left running.
- Full cohort: 2,300 snapshots, 395 labeled (149 positive at theta 0.5), 1,755 low-reference, 150 incomplete-future. Of the labeled rows, 53 are purged and never eligible for modeling. Independent SQL recomputation: zero mismatches.
- Earlier frontend foundation checks passed (ESLint, 2 Vitest tests, TypeScript/build); frontend untouched in Phase 5.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- The owner confirmed Phase 5 on 2026-11-18. All four Phase 4 quality flags are retained; no repositories are silently excluded.
- The local `.env` is ignored by Git. Never print, paste, or commit its token or hash secret.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
Review the Phase 5 PR and measured summary, merging Phase 4 prerequisites first. After owner confirmation, begin Phase 6 feature engineering from the versioned `snapshots` table; filter both split and label_status for modeling. Do not use future activity as a feature.

## Last Updated
2026-11-19, `phase-5/snapshots-labels` — Phase 5 completed and verified; snapshot provenance, prevalence, sample-size limitation, and next-phase handoff recorded.

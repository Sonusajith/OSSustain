# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phase 1 Foundation and Phase 2 Research Protocol and Cohort Selection are complete. Phase 3 collector implementation is on `phase-3/core-schema`; metadata/commit collection, privacy-filtered cache, resumable progress, run logging, migration V4, and offline checks are implemented. The live cohort collection has not run because the local `.env` has no `GITHUB_TOKEN`. The approved 12,500-request stop cap applies to future PR/review/response collection only; commit history and non-PR issue collection are excluded and must be budgeted separately.

## Current Phase
Phase 3: Data Collection I (Repository metadata and commits) — in progress

## Current Task
Finish the Phase 3 live collection after the owner adds a GitHub token to local `.env`; verify the per-repository report, then update this handoff and close Phase 3.

## Last Completed Task
Phase 2 acceptance and Definition of Done are complete: versioned protocol and methodology documented; 50 repositories selected deterministically across 17/17/16 star strata; REST-only decision and 12,500-request PR/review/response stop cap approved. Phase 1 was verified and merged as PR #1.

## Completed Phases
Phase 1: Foundation
Phase 2: Research Protocol and Cohort Selection

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.
- Phase 2: versioned label/split/identity protocol; deterministic stratified 50-repository cohort selected from a recorded GitHub REST candidate screen; repositories/cohorts/cohort_memberships Flyway schema; methodology and approved API budget.

## Features In Progress
Phase 3: GitHub REST client with auth, pagination, ETags, retries, rate-limit handling, and a privacy-filtered cache; repository metadata and full commit-history collector; HMAC contributor identities; resumable page-level progress; per-stage run logging and JSON report. Some candidate PR-count searches in Phase 2 were rate limited; unverified candidates were excluded conservatively and the limitation is documented.

## Pending Tasks
- Add a GitHub PAT with public repository read access to local `.env`; never send or commit it.
- Run a one-repository smoke collection, then the full 50-repository cohort; inspect and retain the generated local report for completeness and observed request counts.
- Before Phase 4 collection, refine the API budget using actual pagination and issue counts. The approved 12,500-request cap covers PR/review/response collection only.

## Known Bugs
None confirmed.

## Current Blockers
Live GitHub collection is waiting for `GITHUB_TOKEN` in the ignored local `.env`; `OSSUSTAIN_HASH_SECRET` is already configured locally.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
- Python direct and resolved pins are in `pipeline/pyproject.toml` and `pipeline/requirements.lock`.
- Phase 2 introduced no dependencies; config validation and cohort selection use already pinned Pydantic and PyYAML.
- Approved Phase 2 collection decision: REST-only; 12,500 authenticated requests as the stop cap for PR/review/response collection (about 2.5 quota-hours), excluding commits and non-PR issues.
- Phase 3 collection uses the standard-library `urllib` client and existing pinned dependencies. JSON cache bodies are privacy-filtered before disk writes; contributor keys use HMAC-SHA256 with `OSSUSTAIN_HASH_SECRET`.

## Architecture Changes
Approved by the project owner: upgraded the backend from Spring Boot 3.5.16 to Spring Boot 4.1.2. The Java target remains 21; Boot 4 starter modules are used.

## Database Changes
Added Flyway V1 foundation baseline, V2 cohort-selection tables, V3 core data tables, and V4 `collection_runs` stage history.

## API Changes
Enabled Spring Boot Actuator health at `/actuator/health`. No product API endpoints yet.

## Important Files
- `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`, `config/experiment.yaml`, `config/cohort-candidates.yaml`, `config/cohort.yaml`, `docs/methodology.md`
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
Used a temporary Apache Maven 3.10.0 download, SHA-512 verified against Apache, for backend checks because Maven was absent from PATH. Docker Desktop/Compose was available through an elevated shell for PostgreSQL and Testcontainers checks.

## Testing Status
- Python: 20 tests passed; Ruff passed, including GitHub client, privacy/redaction, configuration, and resumable collection tests.
- Frontend: ESLint passed; 2 Vitest tests passed; TypeScript check and Vite production build passed. Vite reported ready; the sandbox blocked a loopback HTTP probe.
- Backend: `mvn -B -ntp -f backend/pom.xml test` passed: 7 tests, 0 failures, 0 errors, 0 skipped; Testcontainers used Docker Desktop and PostgreSQL 16.15, and Flyway applied V1–V4.
- Compose PostgreSQL 16.15 was healthy (`pg_isready` accepted connections). The service was left running for the user.
- Pipeline uses Python 3.12.12 with the pinned lockfile in the ignored local `.venv`; 20 pytest tests passed and Ruff passed.
- Frontend (Vite 8.3.5): dev server reported ready on `127.0.0.1:5173`; ESLint exited 0; 2 Vitest tests passed; TypeScript check and production build passed. Direct HTTP probing is blocked by environment socket permissions.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- Phase 3 is not complete until all selected repositories have a recorded outcome and the completeness report is reviewed. Do not begin Phase 4 before then.
- The local `.env` is ignored by Git; `GITHUB_TOKEN` is blank and must be set locally for live collection. Never print, paste, or commit the token.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
After the owner fills `GITHUB_TOKEN` locally, run `ossustain-pipeline --config pipeline/config.yaml collect --limit 1`, then run the full cohort with `ossustain-pipeline --config pipeline/config.yaml collect --report pipeline/data/reports/phase3.json`. Review the report, update Memory, and push the completed Phase 3 work before starting Phase 4.

## Last Updated
2026-11-09, `phase-3/core-schema` — Phase 3 implementation and offline checks recorded; shared branch synced; live full-cohort run awaits local GitHub token.

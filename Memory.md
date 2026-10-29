# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phase 1 Foundation and Phase 2 Research Protocol and Cohort Selection are complete on `phase-2/cohort-selection`. The protocol, deterministic stratified 50-repository cohort, methodology, V2 schema, and tests are implemented and verified. The owner approved a 12,500-request authenticated REST stop cap for future PR/review/response collection; commit history and non-PR issue collection are outside that cap and must be budgeted before collection. No data collection or modeling is included.

## Current Phase
Phase 2: Research Protocol and Cohort Selection (complete; awaiting confirmation before Phase 3)

## Current Task
Wait for owner confirmation before starting Phase 3: Data Collection I. The Phase 2 branch and pull request handoff must be completed first.

## Last Completed Task
Completed Phase 2 acceptance and Definition of Done: versioned protocol and methodology documented; 50 repositories selected deterministically across 17/17/16 star strata; REST-only decision and 12,500-request PR/review/response stop cap approved; Flyway V2 schema applied; Python 12 tests and Ruff passed; backend Testcontainers tests passed 2/2 on PostgreSQL 16.15. Phase 1 was verified and merged as PR #1.

## Completed Phases
Phase 1: Foundation
Phase 2: Research Protocol and Cohort Selection

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.
- Phase 2: versioned label/split/identity protocol; deterministic stratified 50-repository cohort selected from a recorded GitHub REST candidate screen; repositories/cohorts/cohort_memberships Flyway schema; methodology and approved API budget.

## Features In Progress
Phase 2 implementation is complete. Some candidate PR-count searches were rate limited; unverified candidates were excluded conservatively and the limitation is documented. No current blockers.

## Pending Tasks
- Before Phase 4 collection, refine the API budget using actual pagination and issue counts. The approved 12,500-request cap covers PR/review/response collection only.
- Await confirmation before starting Phase 3.

## Known Bugs
None confirmed.

## Current Blockers
None.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
- Python direct and resolved pins are in `pipeline/pyproject.toml` and `pipeline/requirements.lock`.
- Phase 2 introduced no dependencies; config validation and cohort selection use already pinned Pydantic and PyYAML.
- Approved Phase 2 collection decision: REST-only; 12,500 authenticated requests as the stop cap for PR/review/response collection (about 2.5 quota-hours), excluding commits and non-PR issues.

## Architecture Changes
Approved by the project owner: upgraded the backend from Spring Boot 3.5.16 to Spring Boot 4.1.2. The Java target remains 21; Boot 4 starter modules are used.

## Database Changes
Added Flyway V1 foundation baseline and V2 cohort-selection tables (`repositories`, `cohorts`, `cohort_memberships`).

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
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `OSSUSTAIN_DATABASE_URL`, `SPRING_DATASOURCE_URL`, and `VITE_API_BASE_URL` (documented in `.env.example`).

## UI Integration Status
Foundation routing shell only; no Stitch screen integrated.

## Google Stitch Screens Integrated
None.

## Google Stitch Screens Pending
Cohort Overview (Phase 10), Repository Detail (Phase 11), Research Results and Methodology & Limitations (Phase 12). Repository Comparison (Phase 14, post-MVP).

## Temporary Workarounds
Used a temporary Apache Maven 3.10.0 download, SHA-512 verified against Apache, for backend checks because Maven was absent from PATH. Docker Desktop/Compose was available through an elevated shell for PostgreSQL and Testcontainers checks.

## Testing Status
- Python Phase 2: 12 tests passed; Ruff passed; `select-cohort` generated 50 entries.
- Frontend: ESLint passed; 2 Vitest tests passed; TypeScript check and Vite production build passed. Vite reported ready; the sandbox blocked a loopback HTTP probe.
- Backend Phase 2: `mvn -f backend/pom.xml test` passed: 2 tests, 0 failures, 0 errors, 0 skipped using Spring Boot 4.1.2, Testcontainers 1.21.4, Docker Engine 29.9.2, and PostgreSQL 16.15; Flyway applied V1 and V2. Maven emitted 401 warnings for optional Flyway community repository metadata; tests passed.
- Compose PostgreSQL 16.15 was healthy (`pg_isready` accepted connections). The service was left running for the user.
- Pipeline (Python 3.12.14): installed the pinned lockfile in the ignored local `.venv`; CLI `--help` passed; 3 pytest tests passed; Ruff passed.
- Frontend (Vite 8.3.5): dev server reported ready on `127.0.0.1:5173`; ESLint exited 0; 2 Vitest tests passed; TypeScript check and production build passed. Direct HTTP probing is blocked by environment socket permissions.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- Phase 1 acceptance criteria and Definition of Done are met. Work only on Phase 2 until its criteria are verified; do not start Phase 3.
- No data collection, ML behavior, real dashboard screens, or authentication has been implemented.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
Complete the final sync, checks, commit, push, and Phase 2 PR handoff for `phase-2/cohort-selection`. Then wait for owner confirmation before Phase 3. Refine the approved collection budget from actual pagination before Phase 4 collection.

## Last Updated
2026-10-29, `phase-2/cohort-selection` — Phase 2 acceptance verified; 12,500-request REST stop cap approved; no collection or Phase 3 work started.

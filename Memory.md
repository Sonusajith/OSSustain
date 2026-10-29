# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phase 1 Foundation is complete. PostgreSQL 16.15, Spring Boot 4.1.2, Flyway, the pipeline CLI, and the Vite frontend shell have been run and verified against the Phase 1 acceptance criteria. Await user confirmation before starting Phase 2.

## Current Phase
Phase 1: Foundation (complete; Phase 2 not started)

## Current Task
Await user confirmation before beginning Phase 2: Research Protocol and Cohort Selection.

## Last Completed Task
Completed Phase 1 verification: PostgreSQL 16.15 Compose health; Spring Boot 4.1.2 startup and Flyway V1 migration; `/actuator/health` returned `{"groups":["liveness","readiness"],"status":"UP"}`; backend Testcontainers integration test passed with Testcontainers 1.21.4; Python CLI, 3 tests, and Ruff passed; Vite reported ready and the frontend's 2 tests, ESLint, TypeScript check, and production build passed.

## Completed Phases
Phase 1: Foundation

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.

## Features In Progress
None. The frontend dev server reported ready. A direct loopback HTTP probe was denied by environment socket permissions, but the Phase 1 criterion that the frontend starts was verified.

## Pending Tasks
- Phase 2 remains gated on explicit user confirmation.

## Known Bugs
None confirmed.

## Current Blockers
None. Direct HTTP probing of the Vite port is denied by this environment; Vite startup itself reported ready and frontend tests/build passed.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
- Python direct and resolved pins are in `pipeline/pyproject.toml` and `pipeline/requirements.lock`.

## Architecture Changes
Approved by the project owner: upgraded the backend from Spring Boot 3.5.16 to Spring Boot 4.1.2. The Java target remains 21; Boot 4 starter modules are used.

## Database Changes
Added Flyway V1 foundation baseline only. No product/domain tables yet; they are introduced in later phases.

## API Changes
Enabled Spring Boot Actuator health at `/actuator/health`. No product API endpoints yet.

## Important Files
- `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`
- `backend/pom.xml`, `backend/src/main/`, `backend/src/test/`
- `pipeline/pyproject.toml`, `pipeline/requirements.lock`, `pipeline/src/`, `pipeline/tests/`
- `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/src/`

## Reusable Components
None yet.

## Dependencies Added
Pinned in component files. No new services beyond PostgreSQL Compose.

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
- Python: 3 tests passed; `ruff check` passed; installed `ossustain-pipeline --help` passed; Compose YAML parsed and the image tag was confirmed as `postgres:16.15`.
- Frontend: ESLint passed; 2 Vitest tests passed; TypeScript check and Vite production build passed. Vite reported ready; the sandbox blocked a loopback HTTP probe.
- Backend: clean package passed with Spring Boot 4.1.2. `mvn test` passed: 1 test, 0 failures, 0 errors, 0 skipped using Testcontainers 1.21.4, Docker Engine 29.9.2, and PostgreSQL 16.15; Flyway validated/applied V1. The app also started against Compose PostgreSQL and the live `/actuator/health` endpoint returned status `UP`.
- Compose PostgreSQL 16.15 was healthy (`pg_isready` accepted connections). The service was left running for the user.
- Pipeline (Python 3.12.14): installed the pinned lockfile in the ignored local `.venv`; CLI `--help` passed; 3 pytest tests passed; Ruff passed.
- Frontend (Vite 8.3.5): dev server reported ready on `127.0.0.1:5173`; ESLint exited 0; 2 Vitest tests passed; TypeScript check and production build passed. Direct HTTP probing is blocked by environment socket permissions.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- Phase 1 acceptance criteria and Definition of Done are met. Do not begin Phase 2 until the user confirms.
- No data collection, ML behavior, real dashboard screens, or authentication has been implemented.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
Wait for user confirmation before Phase 2. Its first task is to establish the versioned experiment configuration and finalize cohort-selection definitions and constraints.

## Last Updated
2026-10-29, `phase-1/foundation` — Phase 1 acceptance checks and Definition of Done verified; no Phase 2 work started.

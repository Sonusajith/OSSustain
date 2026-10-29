# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phase 1 foundation is in progress. The backend has been upgraded to Spring Boot 4.1.2 per the project owner's decision; database-backed verification remains blocked by missing Docker in the current environment.

## Current Phase
Phase 1: Foundation

## Current Task
Verify PostgreSQL Compose startup, Flyway migration, health endpoint, and Testcontainers in a Docker-enabled environment.

## Last Completed Task
Created the initial monorepo skeleton. Python tests and lint pass; frontend lint, tests, and production build pass; backend sources and tests compile.

## Completed Phases
None

## Completed Features
None; Phase 1 acceptance criteria have not all been verified.

## Features In Progress
- PostgreSQL 16 Compose service, Spring Boot/Flyway health API, Python pipeline scaffold, and Vite React/TypeScript routing shell.
- Runtime verification of PostgreSQL and backend is pending.

## Pending Tasks
- Run `docker compose up -d postgres` and confirm PostgreSQL health.
- Run the backend integration test with Testcontainers and confirm Flyway migration plus `/actuator/health`.
- Start the backend against the Compose database and confirm the endpoint manually.
- Re-run the documented checks from a clean setup before closing Phase 1.

## Known Bugs
None confirmed.

## Current Blockers
- Docker CLI/daemon is not available in the current environment; PostgreSQL Compose and Testcontainers cannot run here.
- The project targets Java 21. The current environment provides Java 27, which Spring Boot 4.1.2 supports.
- Maven 3.10.0 was downloaded temporarily for checks; it is not installed on PATH.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.3.
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
Used a temporary Apache Maven 3.10.0 download, SHA-512 verified against Apache, for backend build checks because Maven was absent from PATH. No workaround for missing Docker.

## Testing Status
- Python: 3 tests passed; `ruff check` passed; installed `ossustain-pipeline --help` passed; Compose YAML parsed and the image tag was confirmed as `postgres:16.15`.
- Frontend: ESLint passed; 2 Vitest tests passed; TypeScript check and Vite production build passed. Vite reported ready; the sandbox blocked a loopback HTTP probe.
- Backend: `mvn -DskipTests package` passed with Spring Boot 4.1.2, compiling main and test sources. `mvn test` discovered the Testcontainers integration test but failed before test execution because Docker is unavailable; no test failures were reported.
- `docker compose up -d postgres` could not run because Docker is not installed/available on PATH. PostgreSQL migration and `/actuator/health` response remain unverified.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- Do not mark Phase 1 complete until the database, backend startup/migration, Testcontainers health test, CLI, and frontend startup/build criteria have all been verified.
- No data collection, ML behavior, real dashboard screens, or authentication has been implemented.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
On a machine with Docker Desktop/Compose and Java 21 available, run the README setup, pass the PostgreSQL and backend integration/startup checks, then update this handoff and assess Phase 1 against its full Definition of Done. Ask before beginning Phase 2.

## Last Updated
2026-10-29, `phase-1/foundation` — upgraded backend to Spring Boot 4.1.2; package passes, Docker-backed test remains blocked.

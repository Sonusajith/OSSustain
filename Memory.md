# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phase 1 foundation is in progress. The backend uses Spring Boot 4.1.2. PostgreSQL 16.15 Compose startup, the Flyway baseline migration, the Testcontainers-backed health integration test, backend startup, and a live `/actuator/health` response have now been verified.

## Current Phase
Phase 1: Foundation

## Current Task
Complete the remaining Phase 1 verification, especially a live frontend HTTP check, then assess the Phase 1 Definition of Done.

## Last Completed Task
Verified PostgreSQL 16.15 Compose health; Spring Boot 4.1.2 startup and Flyway V1 migration; `/actuator/health` returned `{"groups":["liveness","readiness"],"status":"UP"}`; backend Testcontainers integration test passed after pinning Testcontainers 1.21.4. Python tests/lint/CLI and frontend lint/tests/production build had passed in the initial foundation verification.

## Completed Phases
None

## Completed Features
None; Phase 1 acceptance criteria have not all been verified.

## Features In Progress
- PostgreSQL 16 Compose service, Spring Boot/Flyway health API, Python pipeline scaffold, and Vite React/TypeScript routing shell.
- Direct frontend dev-server HTTP response verification is pending (the loopback probe is denied by the environment).

## Pending Tasks
- Verify the frontend dev server responds over HTTP in an environment that permits loopback access.
- Re-run the documented checks from a clean setup before closing Phase 1.

## Known Bugs
None confirmed.

## Current Blockers
- No backend/database blocker remains. The current environment denies loopback access to the Vite frontend port, so its HTTP response was not verified here.
- The project targets Java 21. The current environment provides Java 27; the Spring Boot 4.1.2 build and tests pass on it.
- Maven 3.10.0 was downloaded temporarily for checks; it is not installed on PATH.

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
- Frontend: lint, 2 tests, TypeScript check, and production build passed; Vite reported ready in the initial verification. A live loopback HTTP probe is blocked by environment socket permissions, so that runtime response remains unverified.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- Do not mark Phase 1 complete until all criteria are rechecked against `Phases.md`; the direct frontend HTTP response and clean-setup walkthrough remain unverified.
- No data collection, ML behavior, real dashboard screens, or authentication has been implemented.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
On a machine that permits local loopback access, verify the Vite dev server responds, rerun the README setup from a clean environment, and assess every Phase 1 acceptance criterion and Definition of Done. Ask before beginning Phase 2.

## Last Updated
2026-10-29, `phase-1/foundation` — verified Boot 4.1.2, PostgreSQL/Flyway, and health integration; Testcontainers pinned to 1.21.4 for Docker Engine 29 compatibility.

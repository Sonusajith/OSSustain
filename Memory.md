# OSSustain: Development Memory

**Purpose:** a compact handoff for the next development session.

## Project Summary
OSSustain studies whether public GitHub repositories face significant contribution-activity decline over 90 days. Architecture: Python offline pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard. See `PRD.md` and `Architecture.md`.

## Development Status
Phase 1 Foundation, Phase 2 Research Protocol and Cohort Selection, and Phase 3 Data Collection I are complete. The 50-repository cohort has metadata and full commit histories in PostgreSQL: 55,206 unique commits and 2,638 anonymized contributors. The local completeness report records 50/50 repositories successful and zero failures. The approved 12,500-request stop cap applies to future PR/review/response collection only; commit history and non-PR issue collection were budgeted outside that cap.

## Current Phase
Phase 3: Data Collection I (Repository metadata and commits) — complete; awaiting owner confirmation before Phase 4

## Current Task
Phase 3 collection, verification, and completion commit are on `phase-3/core-schema`; the branch is pushed. The PR creation link is recorded below. Wait for owner confirmation before Phase 4.

## Last Completed Task
Completed Phase 3 acceptance and Definition of Done: all 50 cohort repositories have metadata and completed commit progress; 55,206 unique commits and 2,638 anonymized contributors are stored; report shows 50/50 complete, zero failed, and cumulative per-repository commit totals; reruns resumed an interrupted page and produced no duplicate commit rows. Phase 2 protocol and methodology, 50-repository cohort, and approved API budget remain documented. Phase 1 was verified and merged as PR #1.

## Completed Phases
Phase 1: Foundation
Phase 2: Research Protocol and Cohort Selection
Phase 3: Data Collection I (Repository metadata and commits)

## Completed Features
- Phase 1 foundation: PostgreSQL Compose, Spring Boot/Flyway health API, Python pipeline CLI/config/DB scaffold, and React/TypeScript routing shell with lint/test/build tooling.
- Phase 2: versioned label/split/identity protocol; deterministic stratified 50-repository cohort selected from a recorded GitHub REST candidate screen; repositories/cohorts/cohort_memberships Flyway schema; methodology and approved API budget.
- Phase 3: privacy-filtered GitHub REST cache and client; repository metadata and commit collection; HMAC contributor identities; idempotent page-level resume; collection run history; full-cohort report.

## Features In Progress
No features remain in progress. A transient truncated response while collecting `kubernetes/client-go` was preserved as a failed attempt in `collection_runs`; the collector retry/resume fix recovered it, and the final run completed all 50 repositories with no failed progress or duplicate commit rows. Some candidate PR-count searches in Phase 2 were rate limited; unverified candidates were excluded conservatively and the limitation is documented.

## Pending Tasks
- Create the Phase 3 PR from `phase-3/core-schema`: https://github.com/Sonusajith/OSSustain/compare/main...phase-3/core-schema?expand=1 (`gh` is unavailable in this environment).
- Await owner confirmation before beginning Phase 4.
- Before Phase 4 collection, refine the API budget using actual PR/review pagination and issue counts. The approved 12,500-request cap covers PR/review/response collection only; commit history and non-PR issues are outside it.
- Local full-cohort report: `pipeline/data/reports/phase3-full.json` (ignored by Git with other collected data).

## Known Bugs
None confirmed.

## Current Blockers
None. Live collection completed using the local token; the token and hash secret remain in ignored `.env` and were not committed.

## Technical Decisions
- PostgreSQL 16.15 image; schema ownership remains with Flyway in `backend/`.
- Java target 21 and Spring Boot 4.1.2; Testcontainers 1.21.4. Version 1.21.4 is pinned to support newer Docker Engine versions used by Docker Desktop.
- Python 3.12 with psycopg 3.3.6, pydantic 2.14.1, PyYAML 6.0.3, pytest 9.2.0, and ruff 0.14.3.
- Node 22.13+ with React 19.3.0, React Router 7.18.3, Vite 8.3.5, TypeScript 5.9.3, and pnpm 11.25.0. Frontend tool versions and full transitive lock are in `frontend/package.json` and `frontend/pnpm-lock.yaml`.
- Python direct and resolved pins are in `pipeline/pyproject.toml` and `pipeline/requirements.lock`.
- Phase 2 introduced no dependencies; config validation and cohort selection use already pinned Pydantic and PyYAML.
- Approved Phase 2 collection decision: REST-only; 12,500 authenticated requests as the stop cap for PR/review/response collection (about 2.5 quota-hours), excluding commits and non-PR issues.
- Phase 3 collection uses the standard-library `urllib` client and existing pinned dependencies. JSON cache bodies are privacy-filtered before disk writes; contributor keys use HMAC-SHA256 with `OSSUSTAIN_HASH_SECRET`.
- The final collection totals are 50 repositories, 55,206 unique commits, 2,638 contributors, and 50 completed commit checkpoints. A rerun verified idempotence; `collection_runs` retains one historical transient failure followed by successful recovery.

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
- Python: 21 tests passed; Ruff passed, including GitHub client retry, privacy/redaction, configuration, and resumable collection tests.
- Frontend: ESLint passed; 2 Vitest tests passed; TypeScript check and Vite production build passed. Vite reported ready; the sandbox blocked a loopback HTTP probe.
- Backend: `mvn -B -ntp -f backend/pom.xml test` passed: 7 tests, 0 failures, 0 errors, 0 skipped; Testcontainers used Docker Desktop and PostgreSQL 16.15, and Flyway applied V1–V4.
- Compose PostgreSQL 16.15 was healthy (`pg_isready` accepted connections). The service was left running for the user.
- Pipeline uses Python 3.12.12 with the pinned lockfile in the ignored local `.venv`; 21 pytest tests passed and Ruff passed.
- Frontend (Vite 8.3.5): dev server reported ready on `127.0.0.1:5173`; ESLint exited 0; 2 Vitest tests passed; TypeScript check and production build passed. Direct HTTP probing is blocked by environment socket permissions.

## Deployment Status
Not started.

## Important Context for the Next AI Session
- Phase 3 is complete. Do not begin Phase 4 until the owner confirms.
- The local `.env` is ignored by Git. Never print, paste, or commit its token or hash secret.
- Use only chronological evaluation and leakage-safe features in later research phases.

## Recommended Next Action
Open the Phase 3 PR using the branch link, then wait for owner confirmation before Phase 4. Refine the Phase 4 REST API budget using observed pagination.

## Last Updated
2026-11-09, `phase-3/core-schema` — Phase 3 full-cohort report verified: 50/50 repositories, 55,206 commits, 2,638 contributors; zero incomplete progress; retry and cumulative report tests pass.

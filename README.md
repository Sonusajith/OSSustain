# OSSustain

OSSustain is a research-oriented early-warning system for contribution-activity decline in public GitHub repositories. It is organized as three separate local components: a Python research pipeline, a Spring Boot read API, and a React + TypeScript dashboard. See [PRD.md](PRD.md), [Architecture.md](Architecture.md), and [Phases.md](Phases.md) for product and research details.

## Phase 1 foundation

This phase provides runnable component skeletons only. It does not collect repository data, train models, expose product data, or implement dashboard screens.

### Prerequisites

- Docker Engine with Docker Compose v2
- Python 3.12
- Java 21 and Maven 3.10.0
- Node.js 22.13+ and pnpm 11.25.0

### Configure and start PostgreSQL

From the repository root, copy `.env.example` to `.env` (PowerShell: `Copy-Item .env.example .env`) and start PostgreSQL 16:

```sh
docker compose up -d postgres
docker compose ps
```

The database listens on `localhost:5432` by default. The example credentials are for local development only; override them in `.env` if needed. The named volume keeps local database files between restarts. Stop the service with `docker compose down`; use `docker compose down -v` only when you intend to delete the local database volume.

### Start the backend

In a second terminal, from the repository root:

```sh
mvn -f backend/pom.xml spring-boot:run
```

Flyway applies the versioned foundation migration at startup. If you change the Compose database settings, set the matching `SPRING_DATASOURCE_URL`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` values in the backend terminal. Check the health endpoint at <http://localhost:8080/actuator/health>.

Run backend tests (the integration test starts PostgreSQL with Testcontainers and requires Docker):

```sh
mvn -f backend/pom.xml test
```

### Run the pipeline scaffold

Create and activate a virtual environment, then install its pinned dependencies:

```sh
python -m venv .venv
# PowerShell
.venv\Scripts\Activate.ps1
Copy-Item pipeline/config.example.yaml pipeline/config.yaml
python -m pip install -r pipeline/requirements.lock
python -m pip install --no-deps -e pipeline
ossustain-pipeline --help
python -m pytest -c pipeline/pyproject.toml
python -m ruff check pipeline/src pipeline/tests
```

The configuration loader reads a YAML file and validates its PostgreSQL URL. The scaffold opens no database connection unless a later stage explicitly requests it. Set `OSSUSTAIN_DATABASE_URL` in the process environment to override the value in the config file.

### Start the frontend shell

From `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Vite prints the local URL (normally <http://localhost:5173>). The shell has route placeholders only; no Stitch design or product screen is integrated in Phase 1.

Run frontend checks:

```sh
pnpm lint
pnpm test
pnpm build
```

### Component layout

- `backend/`: Spring Boot application, Flyway schema ownership, health endpoint, and integration test.
- `pipeline/`: Python package, configuration loader, PostgreSQL connection helper, CLI, and tests.
- `frontend/`: strict TypeScript Vite application with a routing shell and build/test/lint tooling.
- `docker-compose.yml`: PostgreSQL 16 only; no additional services.

Runtime and development dependency versions are pinned in `backend/pom.xml`, `pipeline/pyproject.toml`, `frontend/package.json`, and `frontend/pnpm-lock.yaml`.

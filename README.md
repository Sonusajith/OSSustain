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
mvn -f backend/pom.xml spring-boot:run "-Dspring-boot.run.jvmArguments=-Duser.timezone=Asia/Kolkata"
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

### Start the frontend dashboard

Start PostgreSQL and the backend first. The cohort overview reads the latest
repository cohort and dataset summary from the API. Set `VITE_API_BASE_URL` in
the frontend environment if the API runs at a different URL.

From `frontend/`:

```sh
pnpm install --frozen-lockfile
pnpm api:types
pnpm dev
```

Vite prints the local URL (normally <http://localhost:5173>). The Cohort
Overview supports URL-backed search, risk, size, and quality filters, sorting,
and pagination. Repository Detail at `/repositories/:id` loads stored repository
metadata, monthly metric trends with expandable accessible tables, prediction
indicators, and prediction history. Its charts and tables show stored values and
leave missing measures blank; the available API has first-response times but no
separate review-duration series. Research Results and Methodology remain
placeholders for Phase 12. API types are generated from the backend OpenAPI
contract by `pnpm api:types`.

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

## Phase 2 research protocol and cohort

The versioned research definitions are in `config/experiment.yaml`; cohort screening and deterministic membership are in `config/cohort-candidates.yaml` and `config/cohort.yaml`. Definitions, eligibility rationale, and the REST budget estimate are documented in [docs/methodology.md](docs/methodology.md). The Phase 2 selector performs no network requests and does not collect repository history:

```sh
ossustain-pipeline select-cohort --candidate-config config/cohort-candidates.yaml --output config/cohort.yaml
python -m pytest -c pipeline/pyproject.toml
```

The collection plan is REST-only. The approved 12,500-request stop cap covers PR/review/response collection only; commit history and non-PR issue collection are excluded and must be budgeted from measured pagination before Phase 4 collection. See `docs/methodology.md` for details.

## Phase 3 repository and commit collection

Set `GITHUB_TOKEN` to a GitHub personal access token and `OSSUSTAIN_HASH_SECRET` to a random secret of at least 32 characters in the ignored local `.env`. The token is used only for GitHub REST requests. Contributor IDs are stored as keyed HMAC-SHA256 values. The on-disk JSON cache removes logins, names, email addresses, and commit messages before writing.

With PostgreSQL running and the pipeline environment installed, first collect one repository as a smoke run, then collect the full selected cohort:

```sh
ossustain-pipeline --config pipeline/config.yaml collect --limit 1
ossustain-pipeline --config pipeline/config.yaml collect --report pipeline/data/reports/phase3.json
```

The collector follows GitHub pagination, ETags, and rate limits; stores progress after each page so an interrupted run can resume; and writes a per-repository JSON completeness report with cumulative stored-commit counts. Rerunning a completed cohort skips its commit history; pass `--refresh` to start a new history snapshot. Collection cache, reports, and raw local data stay under the ignored `pipeline/data/` directory. See [docs/database.md](docs/database.md) for the run log and progress tables.

## Phase 5 snapshots and labels

After Phase 4 collection and validation, start the backend once so Flyway applies V6.
Then run the snapshot builder from the repository root with the pipeline environment activated:

```powershell
ossustain-pipeline --config pipeline/config.example.yaml build-snapshots
python -m pytest -c pipeline/pyproject.toml
python -m ruff check pipeline/src pipeline/tests
```

The command reads `config/cohort.yaml`, `config/experiment.yaml`, and
`pipeline/data/reports/phase4-validation.json`. Override these with `--cohort`,
`--experiment`, and `--quality-report`; use `--report` to change the default
`pipeline/data/reports/phase5-snapshots.json` output. It makes no GitHub requests.
The report includes label prevalence by prediction date, split, and size group,
plus sensitivity at 0.3/0.5/0.7. Incomplete futures are null; low-reference activity
is unlabeled. Purged dates never belong to a training, validation, or test split.

To verify database reruns against the already collected local cohort:

```powershell
$env:OSSUSTAIN_TEST_SNAPSHOTS='1'
python -m pytest -c pipeline/pyproject.toml
Remove-Item Env:OSSUSTAIN_TEST_SNAPSHOTS
```

This optional test writes/reuses the research snapshot dataset and checks that IDs,
counts, and labels remain unchanged on rerun. It requires migrated PostgreSQL and
the local Phase 4 validation report. The ordinary suite skips this test when the
flag is unset. See [docs/phase5-snapshots.md](docs/phase5-snapshots.md) for window
semantics, exclusions, versioning, and measured results.

## Phase 6 feature engineering

After the Phase 5 snapshots exist and commit, PR, review, and issue collections
are complete, start the backend once so Flyway applies V7, then build the
registered feature set:

```powershell
ossustain-pipeline --config pipeline/config.example.yaml build-features
python -m pytest -c pipeline/pyproject.toml
python -m ruff check pipeline/src pipeline/tests
```

Use `--dataset-version-id` to select a specific dataset and `--report` to choose
the JSON summary path (default: `pipeline/data/reports/phase6-features.json`).
The stage makes no GitHub requests. It requires all four collection stages to be
complete for every repository in the dataset. Feature definitions, strict cutoff
rules, missing-value policy, and interpretation limits are in
[`docs/phase6-features.md`](docs/phase6-features.md).

## Phase 7 temporal modeling

After V8 has been applied and the Phase 6 feature set exists, run the model
stage:

```powershell
ossustain-pipeline --config pipeline/config.example.yaml train
python -m pytest -c pipeline/pyproject.toml
python -m ruff check pipeline/src pipeline/tests
```

The frozen search grid and seeds are in `config/modeling.yaml`. The stage uses
only labeled snapshots assigned to train, validation, or test; tunes parameters
and probability cutoffs on validation, then evaluates each final configuration
on test once. It records scores, calibration bins, repository-clustered 95% CIs,
and validation permutation importance in PostgreSQL. Model artifacts and the
run summary are local under ignored `pipeline/artifacts/` and `pipeline/data/`.
See [`docs/phase7-modeling.md`](docs/phase7-modeling.md) for the selection
protocol and cohort limitations.

## Phase 8 predictions and explanations

After Phase 7 has stored selected models and local artifacts, start the backend
once to apply Flyway V9, then generate versioned predictions and explanations:

```powershell
ossustain-pipeline --config pipeline/config.example.yaml predict --dataset-version-id 1
ossustain-pipeline --config pipeline/config.example.yaml explain --dataset-version-id 1
```

Model choice uses the highest validation PR-AUC among the models selected within
each feature family. Risk categories use that model's validation-score tertiles;
they are relative categories for this cohort, not calibrated probabilities of
decline. The pipeline stores the cutoffs, prediction date, probability, category,
limitation flags, and model/dataset references. Explanations compare each observed
feature with its validation median one feature at a time and describe associations,
not causes. See [`docs/phase8-predictions.md`](docs/phase8-predictions.md).

## Phase 9 backend read API

Start PostgreSQL and the Spring Boot API after Flyway has applied migrations V1–V9:

```powershell
docker compose up -d postgres
mvn -f backend/pom.xml spring-boot:run "-Dspring-boot.run.jvmArguments=-Duser.timezone=Asia/Kolkata"
```

The API reads stored results at `http://localhost:8080/api/v1`. It provides the
cohort repository list and detail, monthly metrics, prediction history and
latest prediction with indicators, plus model versions, evaluations, feature
importance, dataset summary, and label/methodology definitions. The OpenAPI 3.1
contract is served at <http://localhost:8080/openapi.yaml>. The health endpoint
remains at <http://localhost:8080/actuator/health>.

The default CORS origin is `http://localhost:5173`. Set `FRONTEND_ORIGIN` in the
backend environment to a comma-separated list when using another frontend URL.
Run the read API integration and migration tests with Docker available:

```powershell
mvn -B -ntp "-Duser.timezone=Asia/Kolkata" -f backend/pom.xml test
```

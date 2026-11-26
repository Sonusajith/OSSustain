# OSSustain

OSSustain is a research-oriented early-warning system for contribution-activity decline in public GitHub repositories. It includes a Python research pipeline and bounded on-demand worker, PostgreSQL, a Spring Boot API, and a React + TypeScript dashboard. See [PRD.md](PRD.md), [Architecture.md](Architecture.md), and [Phases.md](Phases.md) for product and research details.

## Local setup

### Prerequisites

- Docker Engine with Docker Compose v2
- Python 3.12
- Java 21 and Maven 3.10.0
- Node.js 22.19+ and pnpm 11.25.0

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

### Run the research pipeline and worker

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

The pipeline reads the local `.env` for `GITHUB_TOKEN` and `OSSUSTAIN_HASH_SECRET`. The research commands use the configured PostgreSQL database. The Phase 16 worker is separate from the Spring API and can be run locally with `ossustain-pipeline --config pipeline/config.yaml worker`.

### Start the frontend dashboard

Start PostgreSQL and the backend first. The cohort overview reads the latest
repository cohort and dataset summary from the API. Vite reads
`VITE_API_BASE_URL` from the repository root `.env`; update it there if the API
runs at a different URL, then restart Vite so it reloads the setting.

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
separate review-duration series. Research Results compares stored model runs,
held-out performance, paired feature-family results, size groups, calibration,
and feature importance. Methodology & Limitations shows the versioned label,
chronological splits, sensitivity counts, feature dictionary, and retained data
quality flags. Both screens read the Spring API; charts include accessible
tabular values and findings are scoped to this observational cohort. API types
are generated from the backend OpenAPI contract by `pnpm api:types`.

The Repository Comparison screen at `/compare` lets you select two to four
repositories from the latest cohort and compare their stored estimates and
latest monthly metrics in an accessible table.

The signed-in on-demand screen at `/analyze` searches public GitHub repositories
by name or accepts a GitHub repository URL. It shows the repository identity
before selection, then submits that selection to the existing analysis flow.
Search calls GitHub's public REST API without authentication, so no GitHub token
is sent from the browser; searches are debounced and respect GitHub rate limits.
Unauthenticated repository search is limited to 10 requests per minute; the
client pauses when GitHub's response headers indicate that limit was reached.
To run the worker in Docker, first ensure the selected trained model artifacts
are present under `pipeline/artifacts/`, set `GITHUB_TOKEN` and
`OSSUSTAIN_HASH_SECRET` in `.env`, then run
`docker compose up -d --build analysis-worker`. The worker has read-only access
to model artifacts and never stores raw GitHub responses.
Production deployments also require a stable `OSSUSTAIN_ANALYSIS_IP_HASH_SECRET`
and `MODEL_ARTIFACTS_DIR`; see `deploy/production.env.example`. The UI and API
enforce public-only submissions, a 300-request job cap, a 1,000-request hourly
worker cap, a queue of at most 20 jobs, and three new submissions per client IP
per hour. Completed jobs expire after 30 days; compact results are reused for
24 hours for the same repository and selected model.

Run frontend checks:

```sh
pnpm lint
pnpm test
pnpm build
```

### Component layout

- `backend/`: Spring Boot API, Flyway schema ownership, analysis endpoints, and integration tests.
- `pipeline/`: Python research pipeline, bounded analysis worker, PostgreSQL connection helper, CLI, and tests.
- `frontend/`: strict TypeScript Vite application with a routing shell and build/test/lint tooling.
- `docker-compose.yml`: PostgreSQL 16 and the on-demand worker service; start the worker after setting its token, hash secret, and model artifacts.

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

## Phase 4 collaboration collection and validation

After Phase 3 completes, start the backend once so Flyway applies V4 and V5.
Then collect pull requests, reviews, non-PR issues, and first-response data,
followed by the per-repository completeness and quality report:

```powershell
ossustain-pipeline --config pipeline/config.example.yaml collect-collaboration --pr-request-cap 12500 --issue-request-cap 25000 --report pipeline/data/reports/phase4-quality.json
ossustain-pipeline --config pipeline/config.example.yaml validate --report pipeline/data/reports/phase4-validation.json
```

The collector resumes completed stages, uses the privacy-filtered GitHub cache,
and stops before exceeding either hard request cap. Keep the local `.env` token
and hash secret private. Review the quality report before continuing; snapshots
require a complete Phase 4 collection and this report. The ledger and detailed
reports are local and ignored by Git. See [docs/database.md](docs/database.md)
for retry behavior and the report fields.

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

The API reads stored results at `http://localhost:8080/api/v1`. Opening that
base URL returns an API index with links to the available resources. It provides
the cohort repository list and detail, monthly metrics, prediction history and
latest prediction with indicators, plus model versions, evaluations, feature
importance, dataset summary, and label/methodology definitions. The dashboard
itself runs separately at <http://localhost:5173> after starting Vite. The
OpenAPI 3.1 contract is served at <http://localhost:8080/openapi.yaml>. The
health endpoint remains at <http://localhost:8080/actuator/health>.

### Phase 17 accounts and administrator setup

Phase 17 keeps research pages public and requires an account for on-demand
analysis. There is no public registration. Set `OSSUSTAIN_ADMIN_USERNAME` and
`OSSUSTAIN_ADMIN_PASSWORD` in the backend process environment before its first
start; use a unique password with at least 16 characters. The backend creates
that first administrator if the username does not exist. Sign in at `/login` and
change the initial password when prompted. An administrator can then create
researcher or administrator accounts; each generated temporary password is
shown once and must be changed at first sign-in. Keep these credentials private.

For PowerShell development, set the variables in the backend terminal before
starting Spring Boot:

```powershell
$env:OSSUSTAIN_ADMIN_USERNAME = "your-admin-name"
$env:OSSUSTAIN_ADMIN_PASSWORD = Read-Host "Enter a unique password (16+ characters)"
mvn -f backend/pom.xml spring-boot:run "-Dspring-boot.run.jvmArguments=-Duser.timezone=Asia/Kolkata"
```

The dashboard uses the same `/login` page. Public research screens need no
account. Analysis job status is visible only to its owner and administrators.
Production Compose enables secure session cookies; production must be served over
HTTPS and configured with `OSSUSTAIN_ADMIN_USERNAME` and
`OSSUSTAIN_ADMIN_PASSWORD` in the private deployment environment file.

The default CORS origin is `http://localhost:5173`. Set `FRONTEND_ORIGIN` in the
backend environment to a comma-separated list when using another frontend URL.
Run the read API integration and migration tests with Docker available:

```powershell
mvn -B -ntp "-Duser.timezone=Asia/Kolkata" -f backend/pom.xml test
```

## Production container deployment

The production Compose stack is separate from the development PostgreSQL
service. Copy `deploy/production.env.example` to `deploy/.env.production`, set a
private database password and the public dashboard URL, then start the stack:

```powershell
Copy-Item deploy/production.env.example deploy/.env.production
docker compose --env-file deploy/.env.production -f compose.production.yaml up -d --build
```

The full clean-machine deployment, backup, restore, security, accessibility, and
performance guidance is in [`docs/production-readiness.md`](docs/production-readiness.md).

# OSSustain: Architecture

**Status:** Approved architecture, including the Phase 16 database-backed on-demand analysis worker.

## 1. Architecture Overview

A **modular monolith plus a scheduled research pipeline and one bounded on-demand worker**, with no microservices or external queue.

```
GitHub REST API ◄── Python pipeline/worker ──► PostgreSQL ◄──► Spring Boot API ◄── REST/JSON ── React + TS SPA
                       ▲                         ▲
                       └── read-only model artifacts (worker)    └── Flyway migrations (backend-owned)
```

**Phase 16 decision:** Spring accepts and reports durable analysis jobs in PostgreSQL. A single Python worker polls and claims jobs, calls GitHub, computes features, and scores with an already validation-selected model. The worker alone receives `GITHUB_TOKEN`; it reads artifacts from a configured read-only mount. Job results never enter frozen cohort, snapshot, or evaluation tables. The scheduled research pipeline remains unchanged.

## 2. Technology Stack and Rationale

| Component | Choice | Reason |
|---|---|---|
| Frontend | React + TypeScript (strict), Vite | Specified; fast, simple tooling |
| Routing / server state | React Router, TanStack Query | Handles dashboard reads and asynchronous analysis job status |
| Charts | Recharts | Adequate for time series and bar charts; keeps dependencies small |
| Styling | Tailwind CSS *(confirm against the Stitch export)* | Stitch exports are commonly HTML/Tailwind-style; the final choice follows the export |
| API typing | OpenAPI spec from backend, `openapi-typescript` | Generates frontend types and prevents contract drift |
| Backend | Java 21, Spring Boot 4.1.2 (Web MVC, Data JPA, Validation, Actuator), springdoc-openapi | Specified; mature REST API and bounded job handling |
| Database | **PostgreSQL 16** | Strong analytical SQL (window functions, percentiles), JSONB for flexible feature storage, good Python and Java support |
| Migrations | Flyway (in backend) | Single owner of the schema |
| Pipeline | Python 3.12, pandas, NumPy, scikit-learn, SQLAlchemy, psycopg, httpx, tenacity, pydantic, PyYAML, joblib, pytest, ruff | Standard ML stack; direct HTTP client gives full control over rate limits and ETags |
| Local infra | Docker Compose (PostgreSQL and Python worker) | Reproducible local database and analysis processing |
| CI (optional) | GitHub Actions: lint and test per component | Cheap quality gate |

**Deliberately not used:** Redis, message queues, Kafka, Spark, microservices, MongoDB, Redux, GraphQL on the backend, deep-learning frameworks, XGBoost/LightGBM (scikit-learn's gradient boosting suffices for the MVP), MLflow (the `model_versions` table is enough for the MVP).

## 3. Frontend Approach

- **SPA**, feature-based structure: `features/cohort`, `features/repository`, `features/research`, `features/methodology`.
- **State:** server state in TanStack Query; filter, sort, and pagination state in URL search params; minimal local component state. No global store.
- **Data access:** a single typed API client layer (`api/`); components never call `fetch` directly.
- **Charts:** wrapper components around Recharts, each with a data-table fallback for accessibility.
- **Required UI states:** a shared pattern for loading, empty, and error states.
- **Stitch integration:** see Section 14.

## 4. Backend Approach

- Layered: `controller` → `service` → `repository` (Spring Data JPA/JDBC projections) → DB. Phase 16 adds only the bounded analysis submit/status API alongside existing research reads.
- DTOs as Java records; entities never exposed directly.
- Global exception handler returning a consistent error body.
- Read-heavy time-series queries may use JPQL or native SQL projections rather than loading full entities.
- OpenAPI served by springdoc; Actuator health endpoint.
- `POST /analyses` validates and enqueues a public repository; `GET /analyses/{jobId}` returns job state and result. The API never calls GitHub or the worker directly.

## 5. Database Approach

- PostgreSQL; schema owned by Flyway migrations in `backend/`.
- The Python pipeline writes using SQLAlchemy Core against the migrated schema and **never issues DDL**.
- Normalized raw-event tables for GitHub data; derived tables for snapshots, features, models, evaluations, predictions.
- Features stored as **JSONB keyed by feature name** per snapshot, with a `feature_definitions` table (simpler than a column per feature while features are still evolving). Frequently queried display series use a separate `repository_metrics_monthly` table.
- Long-running, repeatable pipeline stages upsert on natural keys (e.g., GitHub IDs) for idempotency.

## 6. Authentication Approach

- **No user accounts in Phase 16.** Research pages are public reads; the analysis endpoint is public and quota-bounded, and stores no user profile data.
- GitHub token: research pipeline and Python worker only, via environment variable; never in the frontend or Spring backend.
- If authentication or admin features are adopted in Phase 17, add Spring Security and documented authorization rules in that phase.

## 7. API Strategy

REST/JSON under `/api/v1`; research lists are read-only and paginated, while Phase 16 exposes only the bounded analysis submit/status operations.

| Endpoint | Purpose |
|---|---|
| `GET /repositories` (filters: `risk`, `sizeGroup`, `q`, `page`, `sort`) | Cohort list with latest prediction summary |
| `GET /repositories/{id}` | Metadata and data-quality flags |
| `GET /repositories/{id}/metrics` | Monthly time series of activity, contributor, retention, and responsiveness metrics |
| `GET /repositories/{id}/predictions` | Prediction history |
| `GET /repositories/{id}/predictions/latest` | Latest prediction and top indicators |
| `GET /research/models` | Model versions and metadata |
| `GET /research/evaluations` (filters: `split`, `featureSet`, `stratum`) | Metrics |
| `GET /research/feature-importance` | Global importance by model |
| `GET /research/dataset-summary` | Counts, label prevalence by period, quality summary |
| `GET /research/label-definition` | Label parameters, split dates, and feature dictionary |
| `POST /analyses` | Enqueue an on-demand analysis for a public `owner/repository` |
| `GET /analyses/{jobId}` | Read job state and result |
| `GET /actuator/health` | Health |

Error format: `{ timestamp, status, code, message, path }`.

## 8. Third-Party Services

- **GitHub REST API** (research pipeline and the on-demand worker). Cohort-selection discovery may use the search API.
- **Rate-limit budget** (important): authenticated REST allows 5,000 requests/hour. Commit listing is cheap (100 per page). Per-PR reviews and first-response data are expensive (multiple calls per PR) and can reach hundreds of thousands of calls for large repositories. Mitigations, in order: (1) cohort criteria cap PR volume; (2) restrict the observation period (e.g., ~3–4 years); (3) store raw responses so nothing is re-fetched; (4) if still infeasible, use a bounded GraphQL fallback **for review and response data only**, which must be approved (see Planning Notes).
- Avoid the `stats/*` endpoints (asynchronous 202 responses, capped); derive contributor metrics from commits.

## 9. AI / ML Architecture

- **Pipeline stages (each a CLI command, idempotent):** `select-cohort` → `collect` → `validate` → `build-snapshots` → `build-features` → `train` → `evaluate` → `predict` → `explain`.
- **Operational definitions (proposed; finalize in Phase 2):**
  - *Activity* = non-bot commits to the default branch in a window; a secondary variant adds merged PRs, used for sensitivity analysis.
  - *Label* = 1 if future-window activity ≤ θ × reference-window activity, with θ default 0.5 (sensitivity: 0.3, 0.7), and only if reference activity ≥ a minimum (default 20 commits; to be justified from the data).
  - *Snapshots* every 30 days; features from trailing windows (30/90/180 days).
  - *Splits:* chronological with 90-day purge gaps. All hyperparameter tuning uses the validation split only; the test split is evaluated once per final configuration.
- **Models:** threshold baseline (e.g., recent activity decline), Logistic Regression (scaled, class-weighted), Random Forest, Gradient Boosting, each in two feature sets (activity-only; extended).
- **Uncertainty:** bootstrap confidence intervals resampled by **repository** (snapshots from one repository are correlated).
- **Explainability:** fitted-model probability SHAP with validation backgrounds; the threshold-rule baseline uses labeled local substitution indicators. Cohort predictions retain their stored method labels.
- **Risk categories:** probability cutoffs chosen on validation data, documented, with calibration checked.
- **Artifacts:** joblib model files stored locally under `pipeline/artifacts/` (gitignored), referenced from `model_versions`.

## 10. High-Level Application and Data Flow

1. `select-cohort` writes the cohort config and `cohort_memberships`.
2. `collect` pulls GitHub data → raw JSON cache → normalized tables (`commits`, `pull_requests`, `reviews`, `issues`, …).
3. `validate` writes the quality report and flags.
4. `build-snapshots` creates `snapshots` with reference and future activity, label, and label status.
5. `build-features` computes feature JSONB per snapshot and the monthly display metrics.
6. `train`/`evaluate` fit models on train, tune on validation, report on test; write `model_versions` and `evaluation_results`.
7. `predict`/`explain` write `predictions` and `prediction_explanations`.
8. Spring Boot reads the research tables and serves JSON; React renders them.
9. For on-demand analysis, Spring stores a bounded job; the worker collects only the requested repository's preceding 180 days, computes registered features, scores with the selected artifact, and writes a separate compact result for the status endpoint.

## 11. Main System Modules

| Module | Location | Maps to overview module |
|---|---|---|
| Cohort selection | pipeline | Repository Selection |
| Collection | pipeline | Data Collection |
| Validation & snapshots | pipeline | Data Management |
| Feature engineering | pipeline | Feature Engineering |
| Modeling & evaluation | pipeline | Prediction, Model Evaluation |
| Explanation | pipeline + backend | Risk Explanation |
| Read API | backend | all dashboard data |
| Dashboard | frontend | Repository Analytics, Research Dashboard |
| Repository comparison | frontend + backend | Repository comparison |
| On-demand analysis | frontend + backend + worker | Bounded live repository analysis |

## 12. Database Entities

- `repositories` (github_id, full_name, default_branch, created_at, stars_at_selection, size_group, status flags, quality flags)
- `cohorts`, `cohort_memberships` (repo, cohort, stratum, inclusion notes)
- `contributors` (github_id/login, is_bot, type)
- `commits` (sha, repository_id, author_contributor_id nullable, committed_at, is_merge)
- `pull_requests` (github_id, repository_id, author_id, created_at, merged_at, closed_at, state)
- `pull_request_reviews` (pull_request_id, reviewer_id, submitted_at, state)
- `issues` (github_id, repository_id, author_id, created_at, closed_at, first_response_at nullable)
- `collection_runs` (stage, repo, started/finished, status, API calls used, notes)
- `dataset_versions` (id, created_at, config hash, code revision, description)
- `snapshots` (repository_id, prediction_date, reference_activity, future_activity, label, label_status, split, dataset_version_id)
- `snapshot_features` (snapshot_id, features JSONB, feature_set_version, completeness flags)
- `feature_definitions` (name, group, description, window, handling of missing)
- `repository_metrics_monthly` (repository_id, month, display metrics)
- `model_versions` (algorithm, feature_set, params JSONB, seed, dataset_version_id, label_config JSONB, trained_at, code_revision, artifact_path, is_selected)
- `evaluation_results` (model_version_id, split, stratum, metric, value, ci_low, ci_high)
- `feature_importances` (model_version_id, method, feature, value)
- `predictions` (repository_id, snapshot_id, model_version_id, probability, risk_category, predicted_for_date)
- `prediction_explanations` (prediction_id, feature, value, contribution/direction, rank)
- `analysis_jobs` (UUID, canonical repository, state, hashed client IP, request count, attempt count, lease and timestamps)
- `analysis_results` (job, selected model version, score/category, UTC prediction date, compact features/indicators, limitations and request count)
- `on_demand_api_requests` (hourly worker request ledger; old entries are purged by the worker)

**Relationships:** repository 1–N commits/PRs/issues/snapshots; PR 1–N reviews; snapshot 1–1 snapshot_features; model_version 1–N evaluation_results/importances/predictions; prediction 1–N explanations; dataset_version 1–N snapshots and model_versions.

## 13. Cross-Cutting Concerns

**Security:** parameterized queries; CORS limited to the frontend origin; secrets only in environment variables; `.env.example` committed, `.env` ignored; dependency vulnerability checks; no emails or raw event payloads persisted for on-demand work. Only public repositories are accepted. The anonymous endpoint is bounded by 3 submissions per client IP per hour, 20 waiting jobs, one active job per canonical repository, 300 GitHub requests per job, and 1,000 on-demand requests per hour. Job/result metadata expires after 30 days; cached compact results are reusable for 24 hours. GitHub token is available only to the Python worker.

**Performance:** research training remains offline; submitted-repository analysis is asynchronous and bounded; indexes on `(repository_id, prediction_date)` and on `(model_version_id, split)`; precomputed monthly metrics; pagination.

**Scalability:** sized for ~100 repositories and tens of thousands of snapshots; a single PostgreSQL instance is sufficient. Scaling out is not a goal.

**Error handling:** pipeline: retry with exponential backoff for transient errors, a hard stop with a clear message on auth or quota failures, per-repository failure isolation recorded in `collection_runs`. Backend: a global handler with a consistent body. Frontend: error boundaries plus per-query error states with retry.

**Logging/monitoring:** pipeline uses Python `logging` with structured stage and repository context and writes run summaries to `collection_runs`; backend uses SLF4J and Actuator health. No external monitoring in the MVP.

**Testing:**
- Pipeline (pytest): window and label boundary tests, leakage test (mutating post-*t* data must not change features), identity and bot handling, idempotent re-runs, small fixture datasets.
- Backend: JUnit plus Testcontainers (PostgreSQL) for repository and API tests.
- Frontend: Vitest + React Testing Library + MSW; one or two Playwright smoke tests optional.
- Cross-component: a contract check that the OpenAPI types compile in the frontend.

**Deployment:** Local Compose runs PostgreSQL and can build/run the Python worker; backend and frontend can run from their development commands. Production Compose includes the worker and mounts selected model artifacts read-only from `MODEL_ARTIFACTS_DIR`; GitHub and database credentials come from the production environment file.

## 14. Google Stitch UI Integration Strategy

- Stitch output is **design and implementation input**, not production code. Place raw exports in `frontend/stitch-imports/<screen-name>/` (reference only, excluded from the build).
- Per screen: review → identify components → build them in `src/components` (shared) or `src/features/<feature>/components` → replace placeholder data with TanStack Query hooks → add loading, empty, and error states → verify accessibility and responsiveness.
- Preserve the visual appearance; adapt the implementation to this architecture. Do not introduce a competing design system. Shared styling tokens come from the Stitch design as supplied.
- Charts: Stitch will likely deliver static chart placeholders; replace them with real chart components that follow the same look.

## 15. Project Structure

```
ossustain/
├── PRD.md  Architecture.md  Rules.md  Phases.md  Memory.md
├── README.md                    # setup and run order (written during development)
├── docker-compose.yml           # PostgreSQL for local development
├── .env.example                 # documented variables, no secrets
├── config/
│   ├── cohort.yaml              # inclusion criteria + final repo list
│   └── experiment.yaml          # label params, windows, split dates, seeds, models
├── backend/                     # Spring Boot
│   ├── pom.xml
│   └── src/
│       ├── main/java/.../ossustain/
│       │   ├── api/             # controllers, DTO records, exception handler
│       │   ├── service/
│       │   ├── persistence/     # JPA entities / projections / repositories
│       │   └── config/
│       ├── main/resources/db/migration/   # Flyway (schema owner)
│       └── test/
├── pipeline/                    # Python
│   ├── pyproject.toml
│   ├── src/ossustain_pipeline/
│   │   ├── cli.py               # stage commands
│   │   ├── config/              # pydantic config loading
│   │   ├── github/              # client, pagination, rate limiting, cache
│   │   ├── collect/             # per-resource collectors
│   │   ├── validate/
│   │   ├── snapshots/           # windows + labels
│   │   ├── features/            # one module per feature group
│   │   ├── modeling/            # baselines, training, splits, metrics
│   │   ├── explain/
│   │   └── db/                  # SQLAlchemy table defs + writers (no DDL)
│   ├── tests/
│   └── artifacts/               # models, reports (gitignored)
├── frontend/
│   ├── package.json  vite.config.ts  tsconfig.json
│   ├── stitch-imports/          # raw Stitch exports, reference only
│   └── src/
│       ├── api/                 # generated types + typed client
│       ├── components/          # shared UI and chart wrappers, state components
│       ├── features/{cohort,repository,research,methodology}/
│       ├── routes/
│       ├── hooks/  utils/
│       └── test/
├── data/                        # raw JSON cache, exports (gitignored)
├── docs/                        # methodology notes, feature dictionary, report drafts
└── scripts/                     # helper scripts for setup
```

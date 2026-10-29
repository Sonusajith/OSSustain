# OSSustain: Architecture (Proposed)

**Status:** Proposed architecture for future development. Nothing described here exists yet.

## 1. Architecture Overview

A **modular monolith plus an offline pipeline**, with no microservices.

```
GitHub REST API
      │
      ▼
 Python pipeline (CLI)  ──writes──►  PostgreSQL  ◄──reads──  Spring Boot API  ◄── REST/JSON ──  React + TS SPA
 (collect → validate → snapshot →         ▲
  features → train → evaluate → predict)  │
      │                                    └── Flyway migrations (owned by backend)
      └── local files: raw JSON cache, model artifacts, exports (gitignored)
```

**Key decision:** Spring Boot does **not** call Python at runtime in the MVP. Predictions are precomputed by the pipeline and stored in PostgreSQL. This keeps the MVP simple, makes results reproducible, and avoids a second runtime service. A Python inference service is a post-MVP option only if on-demand analysis is adopted.

## 2. Technology Stack and Rationale

| Component | Choice | Reason |
|---|---|---|
| Frontend | React + TypeScript (strict), Vite | Specified; fast, simple tooling |
| Routing / server state | React Router, TanStack Query | Simple handling of loading, error, and caching for read-only data |
| Charts | Recharts | Adequate for time series and bar charts; keeps dependencies small |
| Styling | Tailwind CSS *(confirm against the Stitch export)* | Stitch exports are commonly HTML/Tailwind-style; the final choice follows the export |
| API typing | OpenAPI spec from backend, `openapi-typescript` | Generates frontend types and prevents contract drift |
| Backend | Java 21, Spring Boot 4.1.2 (Web MVC, Data JPA, Validation, Actuator), springdoc-openapi | Specified; mature, simple read-only REST |
| Database | **PostgreSQL 16** | Strong analytical SQL (window functions, percentiles), JSONB for flexible feature storage, good Python and Java support |
| Migrations | Flyway (in backend) | Single owner of the schema |
| Pipeline | Python 3.12, pandas, NumPy, scikit-learn, SQLAlchemy, psycopg, httpx, tenacity, pydantic, PyYAML, joblib, pytest, ruff | Standard ML stack; direct HTTP client gives full control over rate limits and ETags |
| Local infra | Docker Compose (PostgreSQL only) | Reproducible local DB |
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

- Layered: `controller` → `service` → `repository` (Spring Data JPA/JDBC projections) → DB. Read-only in the MVP.
- DTOs as Java records; entities never exposed directly.
- Global exception handler returning a consistent error body.
- Read-heavy time-series queries may use JPQL or native SQL projections rather than loading full entities.
- OpenAPI served by springdoc; Actuator health endpoint.
- No write endpoints in the MVP.

## 5. Database Approach

- PostgreSQL; schema owned by Flyway migrations in `backend/`.
- The Python pipeline writes using SQLAlchemy Core against the migrated schema and **never issues DDL**.
- Normalized raw-event tables for GitHub data; derived tables for snapshots, features, models, evaluations, predictions.
- Features stored as **JSONB keyed by feature name** per snapshot, with a `feature_definitions` table (simpler than a column per feature while features are still evolving). Frequently queried display series use a separate `repository_metrics_monthly` table.
- Long-running, repeatable pipeline stages upsert on natural keys (e.g., GitHub IDs) for idempotency.

## 6. Authentication Approach

- **MVP: none.** The dashboard is public and read-only, with no user data. Pipeline operations are CLI-only on the developer's machine, not exposed over HTTP.
- GitHub token: pipeline only, via environment variable; never in the frontend or backend.
- Post-MVP, if admin features or on-demand analysis are added: Spring Security with a minimal approach (e.g., a single admin role) would be introduced in its own phase.

## 7. API Strategy

REST/JSON, versioned under `/api/v1`, read-only, paginated lists.

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
| `GET /actuator/health` | Health |

Error format: `{ timestamp, status, code, message, path }`.

## 8. Third-Party Services

- **GitHub REST API** (pipeline only). Cohort-selection discovery may use the search API.
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
- **Explainability:** LR coefficients; permutation importance; per-prediction indicators (LR standardized contribution; for tree models, feature value vs. cohort percentile plus global importance). SHAP post-MVP.
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
8. Spring Boot reads these tables and serves JSON; React renders them.

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
| Repository comparison | frontend + backend | *post-MVP* |

## 12. Proposed Database Entities

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

**Relationships:** repository 1–N commits/PRs/issues/snapshots; PR 1–N reviews; snapshot 1–1 snapshot_features; model_version 1–N evaluation_results/importances/predictions; prediction 1–N explanations; dataset_version 1–N snapshots and model_versions.

## 13. Cross-Cutting Concerns

**Security:** read-only API; parameterized queries only; CORS limited to the frontend origin; token and DB credentials only in environment variables; `.env.example` committed, `.env` ignored; dependency vulnerability checks; no personal data beyond public GitHub logins already public (store the minimum, with no emails).

**Performance:** heavy work offline; indexes on `(repository_id, prediction_date)` and on `(model_version_id, split)`; precomputed monthly metrics; pagination.

**Scalability:** sized for ~100 repositories and tens of thousands of snapshots; a single PostgreSQL instance is sufficient. Scaling out is not a goal.

**Error handling:** pipeline: retry with exponential backoff for transient errors, a hard stop with a clear message on auth or quota failures, per-repository failure isolation recorded in `collection_runs`. Backend: a global handler with a consistent body. Frontend: error boundaries plus per-query error states with retry.

**Logging/monitoring:** pipeline uses Python `logging` with structured stage and repository context and writes run summaries to `collection_runs`; backend uses SLF4J and Actuator health. No external monitoring in the MVP.

**Testing:**
- Pipeline (pytest): window and label boundary tests, leakage test (mutating post-*t* data must not change features), identity and bot handling, idempotent re-runs, small fixture datasets.
- Backend: JUnit plus Testcontainers (PostgreSQL) for repository and API tests.
- Frontend: Vitest + React Testing Library + MSW; one or two Playwright smoke tests optional.
- Cross-component: a contract check that the OpenAPI types compile in the frontend.

**Deployment:** MVP is local-run (Docker Compose for PostgreSQL; documented commands for the pipeline, backend, and frontend). Production readiness (Phase 13): containerize the backend and frontend, load a database snapshot, and optionally host on a free or low-cost platform.

## 14. Google Stitch UI Integration Strategy

- Stitch output is **design and implementation input**, not production code. Place raw exports in `frontend/stitch-imports/<screen-name>/` (reference only, excluded from the build).
- Per screen: review → identify components → build them in `src/components` (shared) or `src/features/<feature>/components` → replace placeholder data with TanStack Query hooks → add loading, empty, and error states → verify accessibility and responsiveness.
- Preserve the visual appearance; adapt the implementation to this architecture. Do not introduce a competing design system. Shared styling tokens come from the Stitch design as supplied.
- Charts: Stitch will likely deliver static chart placeholders; replace them with real chart components that follow the same look.

## 15. Proposed Project Structure (does not exist yet)

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

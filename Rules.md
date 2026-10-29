# OSSustain: Rules for AI Coding Agents

These rules apply to every future coding session on this project. Development has not started.

## Before Writing Code

1. Read `PRD.md` before implementing product features.
2. Read `Architecture.md` before making technical decisions.
3. Read `Rules.md` (this file) before modifying the project.
4. Check `Phases.md` and work only in the **current phase** unless explicitly instructed otherwise.
5. Read `Memory.md` to learn current progress and update it after meaningful progress.
6. Inspect the actual project structure before creating files. Never assume a file exists.
7. Search for existing code to reuse before writing new code.

## Always Do

- Keep the pipeline, backend, and frontend separated as in `Architecture.md`.
- Treat **data leakage prevention** as the top technical priority: every feature must use only data strictly before the prediction date.
- Make randomness reproducible (explicit seeds) and record config, dataset, and model versions.
- Make pipeline stages idempotent and resumable.
- Store `null` for unavailable data; never silently impute zero without a documented rule and an indicator.
- Report real results; never tune on the test set, never cherry-pick.
- Phrase explanations as **association**, not causation.
- Verify claims (run tests, run the app) before stating something works.
- Explain major architectural changes before making them and record them in `Memory.md`.

## Never Do

- Never invent existing features, files, endpoints, or results. Never claim something is implemented without verifying.
- Never use the test split for model selection, feature selection, or threshold selection.
- Never use random k-fold or shuffled splits for evaluation. Chronological only.
- Never include post-prediction-date information in features, and never use the future-window activity as a feature.
- Never commit secrets, tokens, `.env`, raw data caches, or model artifacts.
- Never expose the GitHub token to the backend or frontend.
- Never add write or admin endpoints, or authentication, outside the phase that introduces them.
- Never introduce microservices, queues, caches, or new databases without an approved architecture change.
- Never fabricate placeholder statistics in the UI as if real.
- Never make visual design decisions that override the Stitch designs.

## Conventions

| Area | Rule |
|---|---|
| Java | Java 21 with Spring Boot 4.x; packages `lowercase`; classes `PascalCase`; methods/fields `camelCase`; constants `UPPER_SNAKE`; DTOs as `record`s named `*Response`/`*Request`; avoid Lombok |
| Python | `snake_case` modules/functions, `PascalCase` classes; full type hints; `ruff` for lint and format; pydantic for config validation |
| TypeScript/React | Components `PascalCase.tsx`; hooks `useX.ts`; utilities `camelCase.ts`; `strict` mode; no `any` |
| Database | `snake_case` plural table names; `*_id` foreign keys; timestamps as `timestamptz` (UTC); changes only via Flyway migrations |
| API | Plural nouns, `/api/v1`, camelCase JSON, ISO-8601 UTC timestamps |
| Files | One main component/class per file; folder organization follows `Architecture.md` |

**Separation of concerns:** controllers contain no business logic; services contain no HTTP concerns; React components contain no `fetch` calls (use the API layer and hooks); the pipeline's feature code is pure functions of (data, prediction date, config).
**Reusable code:** extract shared logic only after a second real use; shared UI goes in `components/`.
**Type safety:** frontend API types are generated from the backend's OpenAPI document; do not hand-write duplicates.

## Architecture Rules

- The backend must use Spring Boot 4.x. Use the Boot 4 starter modules (for example, `spring-boot-starter-webmvc` and `spring-boot-starter-flyway`); do not add Spring Boot 3.x dependencies.
- Schema changes **only** via Flyway migrations in `backend/`. The pipeline never runs DDL.
- Spring Boot reads precomputed results; it does not run ML or call Python in the MVP.
- Features are stored as JSONB keyed by registered names in `feature_definitions`; every new feature must have a dictionary entry and a leakage test.
- The label definition and its parameters live in `config/experiment.yaml`, never hard-coded.
- Server state in TanStack Query; filter state in URL params; no Redux or global store.
- Changing the stack, adding a service, or changing the schema's ownership requires an explicit explanation and approval first.

## UI Integration Rules (Google Stitch)

Treat Stitch designs and generated frontend output as **design and implementation input**, not unquestionable production code. When Stitch output is provided, you must:

- Review the provided UI before modifying it, and understand the purpose of each screen before connecting functionality.
- Preserve the intended visual appearance unless explicitly asked to redesign it.
- Refactor generated code to match `Architecture.md`; break large generated files into reusable components; remove duplicated components and styling.
- Replace placeholder data with the real data flow (TanStack Query → typed API client).
- Connect interactions (filters, sorting, navigation, tabs) to real logic.
- Add loading, empty, error, and success states required by `PRD.md`.
- Ensure responsive behavior (usable from 360 px) and the accessibility requirements (keyboard access, contrast, semantic markup, a table or text alternative for every chart, never color alone for risk category).
- Preserve visual consistency across screens; do not introduce a separate design system that conflicts with Stitch; do not rewrite the UI because you prefer another style.
- Never assume generated UI is secure, optimized, accessible, or production-ready without reviewing it.
- Keep raw exports in `frontend/stitch-imports/` as reference only.
- If Stitch output conflicts with a functional requirement in `PRD.md`, prioritize the product requirement and explain the conflict. If it conflicts with `Architecture.md`, preserve the visual intent and adapt the implementation.
- Record each integrated screen in `Memory.md`.
- Integrate each screen **in the phase of its feature** (see `Phases.md`), not all at once.

## Security Rules

- Secrets only through environment variables; document names in `.env.example`.
- Parameterized queries only; validate all request parameters (Bean Validation); bound page sizes.
- CORS restricted to the configured frontend origin.
- Store only public GitHub logins and the minimum needed metadata; do not store emails or private data.
- Respect GitHub's terms and rate limits; use a User-Agent; honor secondary rate-limit responses.
- Run dependency vulnerability checks before release (Phase 13).
- No authentication in the MVP; if introduced later, use Spring Security in its own phase with authorization rules documented.

## Error Handling Rules

- Pipeline: retry transient errors with backoff (tenacity); fail fast and clearly on invalid token or exhausted quota; isolate per-repository failures and record them; never swallow exceptions silently.
- Backend: one global exception handler; consistent error body; no stack traces in responses.
- Frontend: handle every query's loading, error (with retry), and empty state; use error boundaries at route level; show user-friendly messages.

## Logging Rules

- Python `logging` with stage and repository context; no tokens or secrets in logs; log API calls used per run.
- Backend SLF4J at appropriate levels; no sensitive data.
- Frontend: no `console.log` left in committed code.

## Testing Rules

- Every pipeline feature gets unit tests with small fixtures. Leakage tests and window/label boundary tests are mandatory.
- Test idempotency of collection and snapshot stages.
- Backend: Testcontainers-based API/repository tests for each endpoint.
- Frontend: component tests for each data-driven screen (loading, error, empty, success) using MSW.
- Tests must pass before a phase is marked done. Do not delete or weaken tests to make them pass.
- Do not write tests that call the live GitHub API in CI; use recorded fixtures.

## Dependency Rules

- Prefer the standard library and already-approved libraries (listed in `Architecture.md`).
- Before adding a dependency: check for an existing solution, confirm maintenance and license, add it with a pinned version, and note it in `Memory.md`.
- **Avoid** in the MVP: Redux, GraphQL on the backend, XGBoost/LightGBM, TensorFlow/PyTorch, MLflow, Celery/Redis/Kafka, Lombok, notebook-only logic, heavy UI component libraries that conflict with the Stitch design.
- Notebooks may be used for exploration only; production logic lives in `pipeline/src`.

## Documentation Rules

- Every config option and environment variable is documented. Every feature has a dictionary entry. Keep `README.md` setup instructions current. Research-relevant decisions (thresholds, exclusions) are recorded in `docs/` with their justification.

## Performance Rules

- Do heavy computation offline; keep API responses small and paginated; use database indexes for the main query paths; avoid N+1 queries; memoize expensive frontend computations only when measured as needed.

## AI Coding Agent Rules

- Work on one phase at a time; stop and report when its definition of done is met.
- Do not silently change architecture, dependencies, or schema; explain first.
- Update `Memory.md` after: completing a meaningful feature, an architectural decision, a database change, adding an important dependency, discovering a major bug, creating a temporary workaround, integrating or significantly modifying Stitch UI, before ending a major session, and before changing phases.
- Use the same phase names as `Phases.md`.
- If a requirement is ambiguous, ask rather than guess; if you assume, record the assumption.
- When something fails, report it honestly with evidence; do not claim success.

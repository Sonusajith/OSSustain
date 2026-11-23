# Phase 16 Architecture Proposal

**Status:** Approved by the project owner; implemented on `phase-16/on-demand-analysis`. The approved design is recorded in `Architecture.md`.

## Current constraints

- Before Phase 16, the Spring API was read-only; GitHub credentials remain limited to Python processes.
- The pipeline currently processes the frozen cohort, uses Flyway-managed tables, and stores model artifacts under the ignored `pipeline/artifacts/` directory.
- Versioned datasets, snapshots, and evaluation results represent the fixed research study. An on-demand repository must not be added to those counts or used to retrain/select models.
- GitHub collection must be bounded, resumable, privacy-filtered, and rate-limit aware.

## Recommended design

1. The dashboard submits a canonical `owner/repository` identifier to `POST /api/v1/analyses`. The API rejects URLs, private repositories, malformed names, and duplicate active work. It stores a durable job and returns `202 Accepted` with a job ID.
2. `GET /api/v1/analyses/{jobId}` returns queued/running/succeeded/failed state and the completed result. The API never calls GitHub or Python directly.
3. A single Python pipeline worker polls PostgreSQL for jobs using a lease and bounded retry policy. It owns `GITHUB_TOKEN`, calls the existing privacy-filtered GitHub client, and reuses the existing feature and prediction code. It never retrains or changes the selected model.
4. Flyway adds job and result tables. On-demand results are stored separately from versioned research snapshots, labels, and cohort summaries. A result records its canonical repository, model version, requested/observed time, probability, limitations, explanation method, and compact input summary.
5. The worker receives the trained model artifacts through a read-only configured volume. Artifacts remain uncommitted. If the required selected artifact is unavailable, the job fails clearly rather than training a replacement.

## Approved operating limits

- Only public GitHub repositories; verify visibility and canonical identity through GitHub's API.
- One worker at a time; at most 20 waiting jobs; one active job per canonical repository.
- Maximum 300 GitHub requests per job and a shared ceiling of 1,000 requests per hour for on-demand work. If a cap prevents complete collection, fail the job with a request-limit status and do not store a partial prediction.
- At most 3 submissions per client IP per hour and a 24-hour cached result per repository/model version. Treat these as abuse controls, not authentication.
- Do not accept a GitHub token from the browser. The worker uses the operator's token and existing global rate-limit handling.

## Decisions and consequences

- This adds a Python worker process and durable job/result schema, but no Redis, external queue, model-training service, or new database.
- The endpoint is public and unauthenticated. IP quotas limit ordinary use but do not provide strong identity; authentication remains a conditional later phase.
- Collection uses the 180 days preceding the UTC prediction date. If a request cap or GitHub error interrupts collection, the job fails and no partial prediction is stored. First-ever contributor and newcomer-retention inputs are unavailable because the bounded history cannot identify the true first contribution; the selected model's fitted training preprocessor handles those missing values and the result carries a limitation.
- Raw GitHub responses remain in worker memory only. Compact results and job metadata expire after 30 days; successful compact results are reusable for 24 hours for the same repository and selected model. The hourly API request ledger is purged by the worker.
- Local and production Compose mount `pipeline/artifacts/` read-only. Production sets `MODEL_ARTIFACTS_DIR`; no artifact is committed.

## Alternative

Use a CLI command for arbitrary public repositories and keep the web API/dashboard read-only. This avoids the worker, durable job tables, and anonymous write endpoint, but does not provide interactive browser submission or job status.

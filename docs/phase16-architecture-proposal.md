# Phase 16 Architecture Proposal

**Status:** Proposal for owner approval. This document does not change the approved architecture. No Phase 16 implementation should begin until the owner approves a design and `Architecture.md` is revised.

## Current constraints

- The Spring API is read-only; GitHub credentials belong only to the Python pipeline.
- The pipeline currently processes the frozen cohort, uses Flyway-managed tables, and stores model artifacts under the ignored `pipeline/artifacts/` directory.
- Versioned datasets, snapshots, and evaluation results represent the fixed research study. An on-demand repository must not be added to those counts or used to retrain/select models.
- GitHub collection must be bounded, resumable, privacy-filtered, and rate-limit aware.

## Recommended design

1. The dashboard submits a canonical `owner/repository` identifier to `POST /api/v1/analyses`. The API rejects URLs, private repositories, malformed names, and duplicate active work. It stores a durable job and returns `202 Accepted` with a job ID.
2. `GET /api/v1/analyses/{jobId}` returns queued/running/succeeded/failed state and the completed result. The API never calls GitHub or Python directly.
3. A single Python pipeline worker polls PostgreSQL for jobs using a lease and bounded retry policy. It owns `GITHUB_TOKEN`, calls the existing privacy-filtered GitHub client, and reuses the existing feature and prediction code. It never retrains or changes the selected model.
4. Flyway adds job and result tables. On-demand results are stored separately from versioned research snapshots, labels, and cohort summaries. A result records its canonical repository, model version, requested/observed time, probability, limitations, explanation method, and compact input summary.
5. The worker receives the trained model artifacts through a read-only configured volume. Artifacts remain uncommitted. If the required selected artifact is unavailable, the job fails clearly rather than training a replacement.

## Proposed operating limits (defaults to approve or change)

- Only public GitHub repositories; verify visibility and canonical identity through GitHub's API.
- One worker at a time; at most 20 waiting jobs; one active job per canonical repository.
- Maximum 300 GitHub requests per job and a shared ceiling of 1,000 requests per hour for on-demand work. Stop and report an insufficient-data result when a cap prevents required features.
- At most 3 submissions per client IP per hour and a 24-hour cached result per repository/model version. Treat these as abuse controls, not authentication.
- Do not accept a GitHub token from the browser. The worker uses the operator's token and existing global rate-limit handling.

## Consequences and open decisions

- This adds a Python worker process and durable job/result schema, but no Redis, external queue, model-training service, or new database.
- An unauthenticated public write endpoint can still be abused through distributed clients. The proposed quotas limit ordinary use but do not provide strong identity; decide whether Phase 16 is public or restricted to a later Phase 17 authentication gate.
- Choose the collection lookback and what constitutes sufficient event coverage before defining inference behavior. The model expects the registered feature set, including up to 180 days of history.
- Define result and event retention/purge behavior before storing submitted-repository data.
- Confirm how production deployment supplies the ignored model artifacts to the worker.

## Alternative

Use a CLI command for arbitrary public repositories and keep the web API/dashboard read-only. This avoids the worker, durable job tables, and anonymous write endpoint, but does not provide interactive browser submission or job status.

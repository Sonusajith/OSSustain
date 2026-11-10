"""Run the repository-metadata and commit-history collection stages."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse

from ossustain_pipeline.collect.models import (
    CohortSelection,
    SelectedRepository,
    redact_commit_page,
    redact_repository_metadata,
)
from ossustain_pipeline.collect.store import PostgresCollectionStore
from ossustain_pipeline.github.client import GitHubAPIError, GitHubClient


def _repository_url(repository: SelectedRepository) -> str:
    owner, name = repository.full_name.split("/", maxsplit=1)
    return f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"


def _commit_url(repository: SelectedRepository, snapshot: datetime) -> str:
    query = urlencode(
        {
            "per_page": 100,
            "page": 1,
            "until": snapshot.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
    )
    return f"{_repository_url(repository)}/commits?{query}"


def _page_number(cursor: str) -> int:
    values = parse_qs(urlparse(cursor).query).get("page", ["1"])
    try:
        page_number = int(values[0])
    except ValueError as error:
        raise ValueError("GitHub pagination cursor has an invalid page number") from error
    if page_number < 1:
        raise ValueError("GitHub pagination cursor page number must be positive")
    return page_number


def _validate_metadata(metadata: Any, selected: SelectedRepository) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise ValueError("Repository metadata response must be an object")
    if metadata.get("id") != selected.github_id:
        raise ValueError(f"GitHub ID mismatch for {selected.full_name}")
    if not isinstance(metadata.get("full_name"), str) or not isinstance(
        metadata.get("default_branch"), str
    ):
        raise ValueError(f"Repository metadata is incomplete for {selected.full_name}")
    if not isinstance(metadata.get("created_at"), str):
        raise ValueError(f"Repository creation time is missing for {selected.full_name}")
    if not isinstance(metadata.get("stargazers_count"), int):
        raise ValueError(f"Repository star count is missing for {selected.full_name}")
    if not isinstance(metadata.get("archived"), bool) or not isinstance(
        metadata.get("fork"), bool
    ):
        raise ValueError(f"Repository status is missing for {selected.full_name}")
    return metadata


def run_collection(
    cohort: CohortSelection,
    client: GitHubClient,
    store: PostgresCollectionStore,
    *,
    hash_secret: str,
    report_path: Path,
    refresh: bool = False,
    repository_limit: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    started_at = (now or datetime.now(UTC)).astimezone(UTC)
    cohort_id = store.ensure_cohort(cohort)
    repositories = (
        cohort.repositories[:repository_limit] if repository_limit else cohort.repositories
    )
    outcomes: list[dict[str, Any]] = []

    for selected in repositories:
        repository_id = store.upsert_selected_repository(
            cohort_id,
            cohort.cohort_name,
            selected,
            cohort.selection_date,
        )
        outcome: dict[str, Any] = {
            "github_id": selected.github_id,
            "full_name": selected.full_name,
            "metadata_status": "pending",
            "commit_status": "pending",
            "commits_processed": 0,
            "pages_processed": 0,
            "errors": [],
        }

        metadata_run_id = store.start_run(repository_id, "repository_metadata")
        metadata_start_requests = client.requests_made
        try:
            response = client.get_json(
                _repository_url(selected),
                transform=redact_repository_metadata,
            )
            metadata = _validate_metadata(response.body, selected)
            store.update_repository_metadata(repository_id, metadata)
            outcome["metadata_status"] = "done"
            store.finish_run(
                metadata_run_id,
                status="done",
                requests_used=client.requests_made - metadata_start_requests,
                records_processed=1,
                error_summary=None,
            )
        except Exception as error:
            summary = f"{type(error).__name__}: {str(error)[:500]}"
            outcome["metadata_status"] = "failed"
            outcome["errors"].append(summary)
            store.finish_run(
                metadata_run_id,
                status="failed",
                requests_used=client.requests_made - metadata_start_requests,
                records_processed=0,
                error_summary=summary,
            )
            outcome["commit_status"] = "skipped"
            outcome["commits_stored"] = store.count_commits(repository_id)
            outcomes.append(outcome)
            continue

        first_cursor = _commit_url(selected, started_at)
        progress = store.begin_commit_progress(
            repository_id,
            first_cursor,
            refresh=refresh,
        )
        if progress is None:
            outcome["commit_status"] = "already_done"
            outcome["commits_stored"] = store.count_commits(repository_id)
            outcomes.append(outcome)
            continue

        commits_run_id = store.start_run(repository_id, "commits")
        commits_start_requests = client.requests_made
        requests_recorded = 0
        cursor = progress["cursor"]
        records_processed = 0
        pages_processed = 0
        try:
            while cursor:
                page_number = _page_number(cursor)
                page_request_start = client.requests_made
                try:
                    page = client.get_json(
                        cursor,
                        transform=lambda payload: redact_commit_page(payload, hash_secret),
                    )
                except GitHubAPIError as error:
                    if error.status_code != 409:
                        raise
                    delta = client.requests_made - page_request_start
                    store.finish_empty_commit_collection(repository_id, delta)
                    requests_recorded += delta
                    cursor = None
                    outcome["commit_status"] = "done"
                    break
                if not isinstance(page.body, list):
                    raise ValueError(f"Commit page {page_number} was not a JSON array")
                delta = client.requests_made - page_request_start
                store.save_commit_page(
                    repository_id,
                    page.body,
                    next_cursor=page.next_url,
                    page_number=page_number,
                    requests_used=delta,
                )
                requests_recorded += delta
                records_processed += len(page.body)
                pages_processed += 1
                cursor = page.next_url
                outcome["commit_status"] = "done" if cursor is None else "running"

            outcome["commits_processed"] = records_processed
            outcome["pages_processed"] = pages_processed
            store.finish_run(
                commits_run_id,
                status="done",
                requests_used=client.requests_made - commits_start_requests,
                records_processed=records_processed,
                error_summary=None,
            )
        except Exception as error:
            requests_delta = client.requests_made - commits_start_requests - requests_recorded
            store.fail_commit_progress(repository_id, requests_delta)
            summary = f"{type(error).__name__}: {str(error)[:500]}"
            outcome["commit_status"] = "failed"
            outcome["errors"].append(summary)
            outcome["commits_processed"] = records_processed
            outcome["pages_processed"] = pages_processed
            store.finish_run(
                commits_run_id,
                status="failed",
                requests_used=client.requests_made - commits_start_requests,
                records_processed=records_processed,
                error_summary=summary,
            )
        outcome["commits_stored"] = store.count_commits(repository_id)
        outcomes.append(outcome)

    finished_at = datetime.now(UTC)
    report = {
        "cohort_name": cohort.cohort_name,
        "cohort_config_hash": cohort.config_hash,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "repositories_requested": len(repositories),
        "repositories_succeeded": sum(
            row["metadata_status"] == "done" and row["commit_status"] in {"done", "already_done"}
            for row in outcomes
        ),
        "repositories_failed": sum(bool(row["errors"]) for row in outcomes),
        "requests_used": client.requests_made,
        "repositories": outcomes,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

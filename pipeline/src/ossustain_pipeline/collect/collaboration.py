"""Bounded PR, review, issue, and first-response collection."""

import json
import os
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from ossustain_pipeline.collect.models import (
    CohortSelection,
    SelectedRepository,
    redact_comments,
    redact_pull_request,
    redact_pull_request_page,
    redact_repository_issue_page,
    redact_reviews,
    redact_search_page,
)
from ossustain_pipeline.collect.store import PostgresCollectionStore
from ossustain_pipeline.github.client import (
    GitHubAPIError,
    GitHubClient,
    RequestBudget,
    RequestBudgetExceeded,
)

SEARCH_LIMIT = 1000
PAGE_SIZE = 100


class UnpartitionableSearchResults(ValueError):
    pass


class _BudgetLedger:
    def __init__(self, path: Path, pr_requests: int, issue_requests: int) -> None:
        self.path = path
        self.journal_path = path.with_suffix(path.suffix + ".journal")
        snapshot_pr_requests = 0
        snapshot_issue_requests = 0
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            snapshot_pr_requests = int(data.get("pr_requests_used", 0))
            snapshot_issue_requests = int(data.get("issue_requests_used", 0))
        journal_entries = []
        if self.journal_path.exists():
            journal_entries = [
                json.loads(line)
                for line in self.journal_path.read_text(encoding="utf-8").splitlines()
            ]
        baselines = [entry for entry in journal_entries if "baseline" in entry]
        if baselines:
            baseline = baselines[0]["baseline"]
            snapshot_pr_requests = max(
                snapshot_pr_requests, int(baseline["pr_requests_used"])
            )
            snapshot_issue_requests = max(
                snapshot_issue_requests, int(baseline["issue_requests_used"])
            )
        pr_journal_total = snapshot_pr_requests + sum(
            entry.get("category") == "pr" for entry in journal_entries
        )
        issue_journal_total = snapshot_issue_requests + sum(
            entry.get("category") == "issue" for entry in journal_entries
        )
        self.pr_requests = max(pr_requests, pr_journal_total)
        self.issue_requests = max(issue_requests, issue_journal_total)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        if not baselines:
            self._append_entry(
                {
                    "baseline": {
                        "pr_requests_used": max(pr_requests, snapshot_pr_requests),
                        "issue_requests_used": max(issue_requests, snapshot_issue_requests),
                    }
                }
            )

    def record_pr_request(self) -> None:
        self._record("pr")

    def record_issue_request(self) -> None:
        self._record("issue")

    def _record(self, category: str) -> None:
        self._append_entry({"category": category})
        if category == "pr":
            self.pr_requests += 1
        else:
            self.issue_requests += 1

    def _append_entry(self, entry: dict[str, Any]) -> None:
        with self.journal_path.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(entry) + "\n")
            journal.flush()
            os.fsync(journal.fileno())


def _default_budget_ledger_path() -> Path:
    """Keep the durable request ledger outside synced project directories."""
    configured_path = os.environ.get("OSSUSTAIN_BUDGET_LEDGER")
    if configured_path:
        return Path(configured_path)
    state_root = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("XDG_STATE_HOME")
        or str(Path.home() / ".local" / "state")
    )
    return Path(state_root) / "ossustain" / "phase4-budget-ledger.json"


def _repository_url(repository: SelectedRepository) -> str:
    owner, name = repository.full_name.split("/", maxsplit=1)
    return f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"


def _search_url(
    repository: SelectedRepository, kind: str, start: date, end: date, size: int
) -> str:
    query = f"repo:{repository.full_name} is:{kind} created:{start.isoformat()}..{end.isoformat()}"
    return "https://api.github.com/search/issues?" + urlencode({"q": query, "per_page": size})


def _search_items(
    client: GitHubClient,
    repository: SelectedRepository,
    kind: str,
    start: date,
    end: date,
    hash_secret: str,
    budget: RequestBudget,
) -> Iterator[dict[str, Any]]:
    count_page = client.get_json(
        _search_url(repository, kind, start, end, 1),
        transform=lambda payload: redact_search_page(payload, hash_secret),
        budget=budget,
    ).body
    if count_page["incomplete_results"]:
        raise ValueError(f"Incomplete GitHub search results for {repository.full_name} ({kind})")
    total = count_page["total_count"]
    if not isinstance(total, int):
        raise ValueError("GitHub search response is missing total_count")
    if total > SEARCH_LIMIT:
        if start >= end:
            raise UnpartitionableSearchResults(
                f"Search result limit cannot be partitioned for {repository.full_name}"
            )
        midpoint = start + (end - start) // 2
        yield from _search_items(client, repository, kind, start, midpoint, hash_secret, budget)
        yield from _search_items(
            client, repository, kind, midpoint + timedelta(days=1), end, hash_secret, budget
        )
        return

    url = _search_url(repository, kind, start, end, PAGE_SIZE)
    while url:
        page = client.get_json(
            url,
            transform=lambda payload: redact_search_page(payload, hash_secret),
            budget=budget,
        )
        if page.body["incomplete_results"]:
            raise ValueError(f"Incomplete GitHub search page for {repository.full_name} ({kind})")
        yield from page.body["items"]
        url = page.next_url


def _repository_issue_items(
    client: GitHubClient,
    repository: SelectedRepository,
    start: date,
    end: date,
    hash_secret: str,
    budget: RequestBudget,
) -> Iterator[dict[str, Any]]:
    """Page repository issues when Search API has more than 1,000 on one day."""
    url = (
        f"{_repository_url(repository)}/issues?"
        + urlencode(
            {
                "state": "all",
                "sort": "created",
                "direction": "desc",
                "per_page": PAGE_SIZE,
            }
        )
    )
    while url:
        page = client.get_json(
            url,
            transform=lambda payload: redact_repository_issue_page(payload, hash_secret),
            budget=budget,
        )
        for issue in page.body:
            created_at = issue.get("created_at")
            if not created_at:
                continue
            created_date = date.fromisoformat(created_at[:10])
            if start <= created_date <= end and not issue["is_pull_request"]:
                yield {key: value for key, value in issue.items() if key != "is_pull_request"}
        if page.body and min(
            date.fromisoformat(item["created_at"][:10])
            for item in page.body
            if item.get("created_at")
        ) < start:
            return
        url = page.next_url


def _issue_items(
    client: GitHubClient,
    repository: SelectedRepository,
    start: date,
    end: date,
    hash_secret: str,
    budget: RequestBudget,
) -> Iterator[dict[str, Any]]:
    seen_numbers: set[int] = set()
    try:
        for issue in _search_items(
            client, repository, "issue", start, end, hash_secret, budget
        ):
            number = int(issue["number"])
            if number not in seen_numbers:
                seen_numbers.add(number)
                yield issue
    except UnpartitionableSearchResults:
        for issue in _repository_issue_items(
            client, repository, start, end, hash_secret, budget
        ):
            number = int(issue["number"])
            if number not in seen_numbers:
                seen_numbers.add(number)
                yield issue


def _pull_request_detail(
    client: GitHubClient,
    repository: SelectedRepository,
    number: int,
    budget: RequestBudget,
) -> dict[str, Any]:
    url = f"{_repository_url(repository)}/pulls/{number}"
    try:
        return client.get_json(url, transform=redact_pull_request, budget=budget).body
    except GitHubAPIError as error:
        if error.status_code != 422:
            raise
        list_url = (
            f"{_repository_url(repository)}/pulls?"
            + urlencode(
                {
                    "state": "all",
                    "sort": "created",
                    "direction": "asc",
                    "per_page": PAGE_SIZE,
                }
            )
        )
        while list_url:
            page = client.get_json(
                list_url,
                transform=redact_pull_request_page,
                budget=budget,
            )
            for pull_request in page.body:
                if pull_request.get("number") == number:
                    return pull_request
            list_url = page.next_url
        raise error


def _first_response(
    client: GitHubClient,
    repository: SelectedRepository,
    number: int,
    author: dict[str, Any] | None,
    comments_count: int,
    hash_secret: str,
    budget: RequestBudget,
) -> str | None:
    if comments_count < 1:
        return None
    url = f"{_repository_url(repository)}/issues/{number}/comments?per_page=100"
    response_times: list[str] = []
    while url:
        page = client.get_json(
            url,
            transform=lambda payload: redact_comments(payload, hash_secret),
            budget=budget,
        )
        for comment in page.body:
            if comment.get("created_at") and (
                not author or not comment.get("author") or
                comment["author"]["contributor_key"] != author["contributor_key"]
            ):
                response_times.append(comment["created_at"])
        url = page.next_url
    return min(response_times) if response_times else None


def _paged_reviews(
    client: GitHubClient,
    repository: SelectedRepository,
    number: int,
    hash_secret: str,
    budget: RequestBudget,
) -> Iterator[dict[str, Any]]:
    url = f"{_repository_url(repository)}/pulls/{number}/reviews?per_page=100"
    while url:
        page = client.get_json(
            url,
            transform=lambda payload: redact_reviews(payload, hash_secret),
            budget=budget,
        )
        yield from page.body
        url = page.next_url


def _run_stage(
    store: PostgresCollectionStore,
    client: GitHubClient,
    repository_id: int,
    stage: str,
    collect: Any,
) -> int:
    run_id = store.start_run(repository_id, stage)
    requests_before = client.requests_made
    records_processed = 0
    try:
        records_processed = int(collect())
    except Exception as error:
        store.finish_run(
            run_id,
            status="failed",
            requests_used=client.requests_made - requests_before,
            records_processed=records_processed,
            error_summary=f"{type(error).__name__}: {str(error)[:400]}",
        )
        raise
    store.finish_run(
        run_id,
        status="done",
        requests_used=client.requests_made - requests_before,
        records_processed=records_processed,
        error_summary=None,
    )
    return records_processed


def run_collaboration_collection(
    cohort: CohortSelection,
    client: GitHubClient,
    store: PostgresCollectionStore,
    *,
    hash_secret: str,
    report_path: Path,
    pr_request_cap: int = 12_500,
    issue_request_cap: int = 25_000,
    repository_limit: int | None = None,
    budget_ledger_path: Path | None = None,
) -> dict[str, Any]:
    start = date.fromisoformat(str(cohort.criteria["observation_start"]))
    end = date.fromisoformat(str(cohort.criteria["observation_end"]))
    repositories = (
        cohort.repositories[:repository_limit] if repository_limit else cohort.repositories
    )
    stale_runs = store.fail_stale_runs()
    db_pr_requests = store.request_totals(("pull_requests", "reviews", "responses"))
    db_issue_requests = store.request_totals(("issues",))
    ledger = _BudgetLedger(
        budget_ledger_path or _default_budget_ledger_path(),
        db_pr_requests,
        db_issue_requests,
    )
    pr_request_start = ledger.pr_requests
    issue_request_start = ledger.issue_requests
    pr_budget = RequestBudget(
        pr_request_cap, used=pr_request_start, on_consume=ledger.record_pr_request
    )
    issue_budget = RequestBudget(
        issue_request_cap, used=issue_request_start, on_consume=ledger.record_issue_request
    )
    cohort_id = store.ensure_cohort(cohort)
    results: list[dict[str, Any]] = []
    pr_budget_exhausted = pr_budget.used >= pr_budget.limit
    issue_budget_exhausted = issue_budget.used >= issue_budget.limit

    for selected in repositories:
        repo_id = store.upsert_selected_repository(
            cohort_id, cohort.cohort_name, selected, cohort.selection_date
        )
        row: dict[str, Any] = {
            "full_name": selected.full_name,
            "pull_requests": 0,
            "reviews": 0,
            "issues": 0,
            "pr_responses": 0,
            "issue_responses": 0,
            "status": "done",
            "errors": [],
        }
        stage_status: dict[str, str] = {}
        if store.stage_completed(repo_id, "pull_requests"):
            stage_status["pull_requests"] = "already_done"
        elif pr_budget_exhausted:
            stage_status["pull_requests"] = "budget_exhausted"
        else:
            def collect_pull_requests(
                selected_repo: SelectedRepository = selected,
                selected_repo_id: int = repo_id,
            ) -> int:
                processed = 0
                for listed in _search_items(
                    client, selected_repo, "pr", start, end, hash_secret, pr_budget
                ):
                    detail = _pull_request_detail(
                        client,
                        selected_repo,
                        listed["number"],
                        pr_budget,
                    )
                    response = _first_response(
                        client,
                        selected_repo,
                        listed["number"],
                        listed.get("author"),
                        listed.get("comments", 0),
                        hash_secret,
                        pr_budget,
                    )
                    store.upsert_pull_request(
                        selected_repo_id,
                        {**listed, **detail, "first_response_at": response},
                    )
                    processed += 1
                return processed

            try:
                _run_stage(store, client, repo_id, "pull_requests", collect_pull_requests)
                stage_status["pull_requests"] = "done"
            except RequestBudgetExceeded as error:
                pr_budget_exhausted = True
                stage_status["pull_requests"] = "budget_exhausted"
                row["errors"].append(str(error))
            except Exception as error:
                stage_status["pull_requests"] = "failed"
                row["errors"].append(f"pull_requests: {type(error).__name__}: {str(error)[:300]}")

        pr_review_targets = store.pull_request_targets(repo_id, start, end)
        if store.review_stage_completed(repo_id):
            stage_status["reviews"] = "already_done"
        elif pr_budget_exhausted:
            stage_status["reviews"] = "budget_exhausted"
        else:
            def collect_reviews(
                selected_repo: SelectedRepository = selected,
                targets: list[tuple[int, int]] = pr_review_targets,
            ) -> int:
                processed = 0
                for number, pull_id in targets:
                    for review in _paged_reviews(
                        client, selected_repo, number, hash_secret, pr_budget
                    ):
                        store.upsert_review(pull_id, review)
                        processed += 1
                return processed

            try:
                _run_stage(store, client, repo_id, "reviews", collect_reviews)
                stage_status["reviews"] = "done"
            except RequestBudgetExceeded as error:
                pr_budget_exhausted = True
                stage_status["reviews"] = "budget_exhausted"
                row["errors"].append(str(error))
            except Exception as error:
                stage_status["reviews"] = "failed"
                row["errors"].append(f"reviews: {type(error).__name__}: {str(error)[:300]}")

        if store.stage_completed(repo_id, "issues"):
            stage_status["issues"] = "already_done"
        elif issue_budget_exhausted:
            stage_status["issues"] = "budget_exhausted"
        else:
            def collect_issues(
                selected_repo: SelectedRepository = selected,
                selected_repo_id: int = repo_id,
            ) -> int:
                processed = 0
                for issue in _issue_items(
                    client, selected_repo, start, end, hash_secret, issue_budget
                ):
                    response = _first_response(
                        client,
                        selected_repo,
                        issue["number"],
                        issue.get("author"),
                        issue.get("comments", 0),
                        hash_secret,
                        issue_budget,
                    )
                    store.upsert_issue(
                        selected_repo_id, {**issue, "first_response_at": response}
                    )
                    processed += 1
                return processed

            try:
                _run_stage(store, client, repo_id, "issues", collect_issues)
                stage_status["issues"] = "done"
            except RequestBudgetExceeded as error:
                issue_budget_exhausted = True
                stage_status["issues"] = "budget_exhausted"
                row["errors"].append(str(error))
            except Exception as error:
                stage_status["issues"] = "failed"
                row["errors"].append(f"issues: {type(error).__name__}: {str(error)[:300]}")

        row["stage_status"] = stage_status
        row.update(store.collaboration_counts(repo_id, start, end))
        row["pr_response_missing"] = row["pull_requests"] - row["pr_responses"]
        row["issue_response_missing"] = row["issues"] - row["issue_responses"]
        row["status"] = (
            "done"
            if all(status in {"done", "already_done"} for status in stage_status.values())
            else "budget_exhausted"
            if "budget_exhausted" in stage_status.values()
            else "failed"
        )
        row["insufficient_collaboration_data"] = row["status"] != "done" or (
            row["pull_requests"] == 0 and row["issues"] == 0
        )
        results.append(row)

    report = {
        "cohort_name": cohort.cohort_name,
        "cohort_config_hash": cohort.config_hash,
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "repositories_requested": len(repositories),
        "repositories_processed": len(results),
        "repositories_failed": sum(row["status"] != "done" for row in results),
        "stale_runs_marked_failed": stale_runs,
        "pr_requests_used": pr_budget.used - pr_request_start,
        "pr_requests_used_lifetime": pr_budget.used,
        "issue_requests_used": issue_budget.used - issue_request_start,
        "issue_requests_used_lifetime": issue_budget.used,
        "total_requests_used": client.requests_made,
        "request_caps": {
            "pull_requests_reviews_responses": pr_budget.limit,
            "non_pull_request_issues": issue_budget.limit,
        },
        "repositories": results,
    }
    totals = {
        key: sum(row[key] for row in results)
        for key in ("pull_requests", "reviews", "issues", "pr_responses", "issue_responses")
    }
    totals["pr_responses_missing"] = sum(row["pr_response_missing"] for row in results)
    totals["issue_responses_missing"] = sum(row["issue_response_missing"] for row in results)
    report["quality_summary"] = totals
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

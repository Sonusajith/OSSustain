import json
from datetime import date
from urllib.parse import parse_qs, urlparse

from ossustain_pipeline.collect.collaboration import (
    _BudgetLedger,
    _default_budget_ledger_path,
    _first_response,
    _issue_items,
    _pull_request_detail,
    _search_items,
)
from ossustain_pipeline.collect.models import (
    SelectedRepository,
    redact_repository_issue_page,
    redact_search_page,
)
from ossustain_pipeline.github.client import ApiPage, GitHubAPIError, RequestBudget

SECRET = "fixture-hash-secret-that-is-more-than-32-characters"


def _repository() -> SelectedRepository:
    return SelectedRepository(
        github_id=50,
        full_name="sample/project",
        default_branch="main",
        created_at="2020-01-01",
        stars=500,
        primary_language="Python",
        archived=False,
        fork=False,
        size_group="small",
    )


class PartitionClient:
    def get_json(self, url, *, transform=None, budget=None):
        budget.consume()
        query = parse_qs(urlparse(url).query)
        terms = query["q"][0]
        bounds = terms.split("created:", maxsplit=1)[1]
        start, end = bounds.split("..")
        per_page = int(query["per_page"][0])
        if per_page == 1:
            total = 1001 if start == "2022-01-01" and end == "2022-01-02" else 600
            raw = {"total_count": total, "incomplete_results": False, "items": []}
        else:
            raw = {
                "total_count": 1,
                "incomplete_results": False,
                "items": [
                    {
                        "number": 1 if start == "2022-01-01" else 2,
                        "state": "closed",
                        "created_at": f"{start}T01:00:00Z",
                        "closed_at": None,
                        "comments": 0,
                        "user": {"id": 42, "login": "private-login", "type": "User"},
                        "body": "must not be cached",
                    }
                ],
            }
        return ApiPage(transform(raw) if transform else raw, None)


def test_search_splits_ranges_over_github_1000_result_limit() -> None:
    client = PartitionClient()
    budget = RequestBudget(10)

    rows = list(
        _search_items(
            client,
            _repository(),
            "issue",
            date(2022, 1, 1),
            date(2022, 1, 2),
            SECRET,
            budget,
        )
    )

    assert len(rows) == 2
    assert rows[0]["number"] == 1
    assert rows[1]["number"] == 2
    assert budget.used == 5
    assert "private-login" not in str(rows)


def test_issue_search_limit_falls_back_to_repository_pagination() -> None:
    class IssueFallbackClient:
        def get_json(self, url, *, transform=None, budget=None):
            budget.consume()
            if "/search/issues?" in url:
                payload = {"total_count": 1001, "incomplete_results": False, "items": []}
            else:
                payload = [
                    {
                        "number": 10,
                        "state": "closed",
                        "created_at": "2022-01-01T01:00:00Z",
                        "closed_at": "2022-01-02T01:00:00Z",
                        "comments": 0,
                        "user": {"id": 42, "login": "private-login", "type": "User"},
                        "body": "private body",
                    },
                    {
                        "number": 11,
                        "state": "closed",
                        "created_at": "2022-01-01T02:00:00Z",
                        "pull_request": {"url": "must be excluded"},
                    },
                    {
                        "number": 12,
                        "state": "open",
                        "created_at": "2021-12-31T23:00:00Z",
                    },
                ]
            return ApiPage(transform(payload), None)

    rows = list(
        _issue_items(
            IssueFallbackClient(),
            _repository(),
            date(2022, 1, 1),
            date(2022, 1, 1),
            SECRET,
            RequestBudget(5),
        )
    )

    assert [row["number"] for row in rows] == [10]
    assert "private-login" not in str(rows)
    assert "private body" not in str(rows)


def test_issue_list_redaction_marks_pull_requests_without_profile_data() -> None:
    rows = redact_repository_issue_page(
        [
            {"number": 1, "user": {"id": 42, "login": "private-login"}},
            {"number": 2, "pull_request": {}, "user": {"id": 43}},
        ],
        SECRET,
    )

    assert rows[0]["is_pull_request"] is False
    assert rows[1]["is_pull_request"] is True
    assert "private-login" not in str(rows)


def test_pull_request_detail_422_falls_back_to_paginated_list() -> None:
    class PullRequestFallbackClient:
        def get_json(self, url, *, transform=None, budget=None):
            budget.consume()
            if url.endswith("/pulls/779"):
                raise GitHubAPIError(422, url)
            payload = [
                {
                    "number": 779,
                    "state": "closed",
                    "created_at": "2024-01-01T00:00:00Z",
                    "merged_at": "2024-01-03T00:00:00Z",
                    "closed_at": "2024-01-03T00:00:00Z",
                    "user": {"id": 42, "login": "private-login"},
                }
            ]
            return ApiPage(transform(payload), None)

    details = _pull_request_detail(
        PullRequestFallbackClient(), _repository(), 779, RequestBudget(3)
    )

    assert details["merged_at"] == "2024-01-03T00:00:00Z"


def test_search_redaction_discards_profile_and_body_fields() -> None:
    redacted = redact_search_page(
        {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "number": 7,
                    "state": "open",
                    "created_at": "2024-01-01T00:00:00Z",
                    "closed_at": None,
                    "comments": 1,
                    "user": {"id": 42, "login": "private-login", "type": "User"},
                    "body": "private issue body",
                }
            ],
        },
        SECRET,
    )

    serialized = str(redacted)
    assert redacted["items"][0]["author"]["contributor_key"]
    assert "private-login" not in serialized
    assert "private issue body" not in serialized
    assert "id" not in redacted["items"][0]["author"]


def test_first_response_skips_author_comments_and_chooses_earliest_other_comment() -> None:
    class CommentClient:
        def get_json(self, url, *, transform=None, budget=None):
            budget.consume()
            raw = [
                {"created_at": "2024-01-02T00:00:00Z", "user": {"id": 100, "login": "author"}},
                {"created_at": "2024-01-03T00:00:00Z", "user": {"id": 200, "login": "reviewer"}},
                {"created_at": "2024-01-01T00:00:00Z", "user": {"id": 300, "login": "earlier"}},
            ]
            return ApiPage(transform(raw), None)

    from ossustain_pipeline.collect.models import contributor_identity

    author = contributor_identity({"id": 100, "login": "author", "type": "User"}, SECRET)
    result = _first_response(
        CommentClient(), _repository(), 7, author, 3, SECRET, RequestBudget(3)
    )

    assert result == "2024-01-01T00:00:00Z"


def test_budget_ledger_persists_request_reservations(tmp_path) -> None:
    path = tmp_path / "budget.json"
    ledger = _BudgetLedger(path, pr_requests=4, issue_requests=8)

    ledger.record_pr_request()
    ledger.record_issue_request()

    entries = [
        json.loads(line)
        for line in path.with_suffix(path.suffix + ".journal")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert entries[1:] == [{"category": "pr"}, {"category": "issue"}]
    restarted = _BudgetLedger(path, pr_requests=0, issue_requests=0)
    assert restarted.pr_requests == 5
    assert restarted.issue_requests == 9
    restarted_after_db_commit = _BudgetLedger(path, pr_requests=100, issue_requests=200)
    assert restarted_after_db_commit.pr_requests == 100
    assert restarted_after_db_commit.issue_requests == 200


def test_default_budget_ledger_uses_local_state_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("OSSUSTAIN_BUDGET_LEDGER", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)

    assert _default_budget_ledger_path() == (
        tmp_path / "local" / "ossustain" / "phase4-budget-ledger.json"
    )

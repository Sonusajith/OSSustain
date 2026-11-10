import json
from email.message import Message
from http.client import IncompleteRead
from io import BytesIO
from urllib.error import HTTPError

import pytest

from ossustain_pipeline.github.cache import JsonResponseCache
from ossustain_pipeline.github.client import (
    GitHubAPIError,
    GitHubClient,
    RequestBudget,
    RequestBudgetExceeded,
)


class FakeResponse:
    def __init__(self, body: object, headers: dict[str, str] | None = None) -> None:
        self.status = 200
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_etag_cache_reuses_redacted_body_and_next_link(tmp_path) -> None:
    url = "https://api.github.com/repos/example/project/commits?per_page=100&page=1"
    next_url = "https://api.github.com/repos/example/project/commits?per_page=100&page=2"
    responses = [
        FakeResponse(
            [{"sha": "abc123"}],
            {
                "ETag": '"page-one"',
                "Link": f'<{next_url}>; rel="next", <{next_url}>; rel="last"',
            },
        ),
        HTTPError(url, 304, "Not Modified", Message(), BytesIO(b"")),
    ]
    requests = []

    def open_request(request, timeout):
        requests.append(request)
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    client = GitHubClient("test-token", JsonResponseCache(tmp_path), opener=open_request)

    first = client.get_json(url)
    second = client.get_json(url)

    assert first.body == [{"sha": "abc123"}]
    assert second.body == first.body
    assert first.next_url == next_url
    assert second.next_url == next_url
    assert requests[0].get_header("Authorization") == "Bearer test-token"
    assert requests[1].get_header("If-none-match") == '"page-one"'
    assert client.requests_made == 2


def test_rate_limit_retries_using_retry_after(tmp_path) -> None:
    url = "https://api.github.com/repos/example/project"
    headers = Message()
    headers["Retry-After"] = "3"
    responses = [
        HTTPError(url, 403, "rate limited", headers, BytesIO(b'{"message":"rate limit exceeded"}')),
        FakeResponse({"id": 8}),
    ]
    delays = []

    def open_request(request, timeout):
        response = responses.pop(0)
        if isinstance(response, HTTPError):
            raise response
        return response

    client = GitHubClient(
        "test-token",
        JsonResponseCache(tmp_path),
        max_retries=1,
        opener=open_request,
        sleep=delays.append,
    )

    result = client.get_json(url)

    assert result.body == {"id": 8}
    assert delays == [3.0]
    assert client.requests_made == 2


def test_incomplete_response_retries(tmp_path) -> None:
    url = "https://api.github.com/repos/example/project"
    responses = [IncompleteRead(b'{"partial":', 10), FakeResponse({"complete": True})]
    attempts = 0
    delays = []

    def open_request(request, timeout):
        nonlocal attempts
        attempts += 1
        response = responses.pop(0)
        if isinstance(response, IncompleteRead):
            raise response
        return response

    client = GitHubClient(
        "test-token",
        JsonResponseCache(tmp_path),
        max_retries=1,
        opener=open_request,
        sleep=delays.append,
    )

    result = client.get_json(url)

    assert result.body == {"complete": True}
    assert attempts == 2
    assert delays == [1]
    assert client.requests_made == 2


def test_auth_failure_is_not_retried(tmp_path) -> None:
    url = "https://api.github.com/repos/example/project"
    attempts = 0

    def open_request(request, timeout):
        nonlocal attempts
        attempts += 1
        raise HTTPError(url, 401, "Unauthorized", Message(), BytesIO(b"{}"))

    client = GitHubClient(
        "invalid-token",
        JsonResponseCache(tmp_path),
        max_retries=3,
        opener=open_request,
        sleep=lambda _: None,
    )

    with pytest.raises(GitHubAPIError) as error:
        client.get_json(url)

    assert error.value.status_code == 401
    assert attempts == 1


def test_request_budget_stops_before_sending_an_over_budget_request(tmp_path) -> None:
    url = "https://api.github.com/repos/example/project"
    attempts = 0

    def open_request(request, timeout):
        nonlocal attempts
        attempts += 1
        return FakeResponse({"id": 8})

    budget = RequestBudget(limit=1)
    client = GitHubClient(
        "test-token",
        JsonResponseCache(tmp_path),
        opener=open_request,
    )

    assert client.get_json(url, budget=budget).body == {"id": 8}
    with pytest.raises(RequestBudgetExceeded, match="budget of 1"):
        client.get_json(url + "?page=2", budget=budget)

    assert budget.used == 1
    assert client.requests_made == 1
    assert attempts == 1

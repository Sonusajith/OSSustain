"""GitHub REST client with ETags, pagination links, retries, and rate-limit handling."""

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.message import Message
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ossustain_pipeline.github.cache import CachedResponse, JsonResponseCache


class GitHubAPIError(RuntimeError):
    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"GitHub API returned HTTP {status_code} for {urlparse(url).path}")
        self.status_code = status_code


class GitHubRateLimitError(GitHubAPIError):
    pass


@dataclass(frozen=True)
class ApiPage:
    body: Any
    next_url: str | None


def _header(headers: Message, name: str) -> str | None:
    value = headers.get(name)
    return str(value) if value is not None else None


def next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for match in re.finditer(r"<([^>]+)>\s*;\s*rel=\"([^\"]+)\"", link_header):
        if match.group(2) == "next":
            return match.group(1)
    return None


class GitHubClient:
    def __init__(
        self,
        token: str,
        cache: JsonResponseCache,
        *,
        user_agent: str = "OSSustain-Research/0.1",
        timeout_seconds: float = 30,
        max_retries: int = 5,
        base_delay_seconds: float = 1,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not token.strip():
            raise ValueError("GITHUB_TOKEN is required for collection")
        self._token = token
        self._cache = cache
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self.requests_made = 0

    def get_json(
        self,
        url: str,
        *,
        transform: Callable[[Any], Any] | None = None,
    ) -> ApiPage:
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "api.github.com":
            raise ValueError("GitHub API requests must use https://api.github.com")

        cached = self._cache.read(url)
        force_refresh = False
        for attempt in range(self._max_retries + 1):
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": self._user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if cached and cached.etag and not force_refresh:
                headers["If-None-Match"] = cached.etag
            request = Request(url, headers=headers)
            self.requests_made += 1
            try:
                with self._opener(request, timeout=self._timeout_seconds) as response:
                    body_bytes = response.read()
                    body = json.loads(body_bytes) if body_bytes else None
                    if transform is not None:
                        body = transform(body)
                    entry = CachedResponse(
                        body=body,
                        etag=_header(response.headers, "ETag"),
                        link=_header(response.headers, "Link"),
                    )
                    self._cache.write(url, entry)
                    return ApiPage(body=body, next_url=next_link(entry.link))
            except HTTPError as error:
                if error.code == 304:
                    if cached is not None:
                        return ApiPage(body=cached.body, next_url=next_link(cached.link))
                    if not force_refresh:
                        force_refresh = True
                        continue
                    raise ValueError(
                        f"GitHub returned 304 without a cached response for {parsed_url.path}"
                    ) from None
                if self._is_rate_limited(error.code, error.headers, error.read()):
                    if attempt < self._max_retries:
                        self._sleep(self._retry_delay(attempt, error.headers, rate_limited=True))
                        continue
                    raise GitHubRateLimitError(error.code, url) from error
                if error.code in {500, 502, 503, 504} and attempt < self._max_retries:
                    self._sleep(self._retry_delay(attempt, error.headers, rate_limited=False))
                    continue
                raise GitHubAPIError(error.code, url) from error
            except (URLError, TimeoutError, OSError) as error:
                if attempt >= self._max_retries:
                    raise RuntimeError(f"GitHub request failed for {parsed_url.path}") from error
                self._sleep(self._retry_delay(attempt, None, rate_limited=False))
            except json.JSONDecodeError as error:
                raise ValueError(f"GitHub returned invalid JSON for {parsed_url.path}") from error
        raise RuntimeError(f"GitHub request retry loop ended unexpectedly for {parsed_url.path}")

    def _is_rate_limited(
        self,
        status_code: int,
        headers: Message | None,
        body: bytes,
    ) -> bool:
        if status_code == 429:
            return True
        if status_code != 403:
            return False
        remaining = _header(headers, "X-RateLimit-Remaining") if headers else None
        message = body.decode("utf-8", errors="ignore").lower()
        return (
            remaining == "0"
            or "secondary rate limit" in message
            or "rate limit exceeded" in message
        )

    def _retry_delay(
        self,
        attempt: int,
        headers: Message | None,
        *,
        rate_limited: bool,
    ) -> float:
        if headers:
            retry_after = _header(headers, "Retry-After")
            if retry_after:
                try:
                    return max(0, float(retry_after))
                except ValueError:
                    pass
            reset = _header(headers, "X-RateLimit-Reset")
            remaining = _header(headers, "X-RateLimit-Remaining")
            if reset and remaining == "0":
                try:
                    return max(1, float(reset) - self._clock() + 1)
                except ValueError:
                    pass
        if rate_limited:
            return max(60, self._base_delay_seconds * (2**attempt))
        return min(60, self._base_delay_seconds * (2**attempt))

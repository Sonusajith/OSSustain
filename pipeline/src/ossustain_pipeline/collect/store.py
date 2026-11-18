"""PostgreSQL writes for repository metadata, commits, progress, and run history."""

import json
from datetime import UTC, date, datetime, time
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ossustain_pipeline.collect.models import CohortSelection, SelectedRepository


def _midnight_utc(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _optional_timestamp(value: str | None) -> datetime | None:
    return _timestamp(value) if value else None


class PostgresCollectionStore:
    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def ensure_cohort(self, cohort: CohortSelection) -> int:
        criteria = json.loads(json.dumps(cohort.criteria, default=str))
        with self._connection.transaction():
            row = self._connection.execute(
                """
                INSERT INTO cohorts (name, selection_date, config_hash, criteria)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    selection_date = EXCLUDED.selection_date,
                    config_hash = EXCLUDED.config_hash,
                    criteria = EXCLUDED.criteria
                RETURNING id
                """,
                (cohort.cohort_name, cohort.selection_date, cohort.config_hash, Jsonb(criteria)),
            ).fetchone()
        return int(row[0])

    def upsert_selected_repository(
        self,
        cohort_id: int,
        cohort_name: str,
        selected: SelectedRepository,
        selection_date: date,
    ) -> int:
        with self._connection.transaction():
            row = self._connection.execute(
                """
                INSERT INTO repositories (
                    github_id, full_name, default_branch, created_at, stars_at_selection,
                    size_group, primary_language, archived, fork, selected_at, cohort_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (github_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    default_branch = EXCLUDED.default_branch,
                    created_at = EXCLUDED.created_at,
                    stars_at_selection = EXCLUDED.stars_at_selection,
                    size_group = EXCLUDED.size_group,
                    primary_language = EXCLUDED.primary_language,
                    archived = EXCLUDED.archived,
                    fork = EXCLUDED.fork,
                    selected_at = EXCLUDED.selected_at,
                    cohort_version = EXCLUDED.cohort_version
                RETURNING id
                """,
                (
                    selected.github_id,
                    selected.full_name,
                    selected.default_branch,
                    _midnight_utc(selected.created_at),
                    selected.stars,
                    selected.size_group,
                    selected.primary_language,
                    selected.archived,
                    selected.fork,
                    _midnight_utc(selection_date),
                    cohort_name,
                ),
            ).fetchone()
            repository_id = int(row[0])
            self._connection.execute(
                """
                INSERT INTO cohort_memberships (cohort_id, repository_id, stratum, inclusion_notes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cohort_id, repository_id) DO UPDATE SET
                    stratum = EXCLUDED.stratum,
                    inclusion_notes = EXCLUDED.inclusion_notes
                """,
                (cohort_id, repository_id, selected.size_group, selected.inclusion_notes),
            )
        return repository_id

    def update_repository_metadata(self, repository_id: int, metadata: dict[str, Any]) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                UPDATE repositories
                SET full_name = %s,
                    default_branch = %s,
                    created_at = %s,
                    primary_language = %s,
                    archived = %s,
                    fork = %s,
                    metadata = %s
                WHERE id = %s
                """,
                (
                    metadata["full_name"],
                    metadata["default_branch"],
                    _timestamp(metadata["created_at"]),
                    metadata["language"],
                    metadata["archived"],
                    metadata["fork"],
                    Jsonb({"collected_stargazers_count": metadata["stargazers_count"]}),
                    repository_id,
                ),
            )

    def start_run(self, repository_id: int, stage: str) -> int:
        with self._connection.transaction():
            row = self._connection.execute(
                """
                INSERT INTO collection_runs (repo_id, stage, status)
                VALUES (%s, %s, 'running')
                RETURNING id
                """,
                (repository_id, stage),
            ).fetchone()
        return int(row[0])

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        requests_used: int,
        records_processed: int,
        error_summary: str | None,
    ) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                UPDATE collection_runs
                SET status = %s,
                    finished_at = now(),
                    requests_used = %s,
                    records_processed = %s,
                    error_summary = %s
                WHERE id = %s
                """,
                (status, requests_used, records_processed, error_summary, run_id),
            )

    def request_totals(self, stages: tuple[str, ...]) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(sum(requests_used), 0) FROM collection_runs WHERE stage = ANY(%s)",
            (list(stages),),
        ).fetchone()
        return int(row[0])

    def stage_completed(self, repository_id: int, stage: str) -> bool:
        row = self._connection.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM collection_runs
                WHERE repo_id = %s AND stage = %s AND status = 'done'
            )
            """,
            (repository_id, stage),
        ).fetchone()
        return bool(row[0])

    def review_stage_completed(self, repository_id: int) -> bool:
        row = self._connection.execute(
            """
            SELECT
                (SELECT finished_at FROM collection_runs
                 WHERE repo_id = %s AND stage = 'pull_requests' AND status = 'done'
                 ORDER BY finished_at DESC LIMIT 1) IS NOT NULL
                AND
                (SELECT finished_at FROM collection_runs
                 WHERE repo_id = %s AND stage = 'pull_requests' AND status = 'done'
                 ORDER BY finished_at DESC LIMIT 1)
                <
                (SELECT finished_at FROM collection_runs
                 WHERE repo_id = %s AND stage = 'reviews' AND status = 'done'
                 ORDER BY finished_at DESC LIMIT 1)
            """,
            (repository_id, repository_id, repository_id),
        ).fetchone()
        return bool(row[0])

    def pull_request_targets(
        self, repository_id: int, start: date, end: date
    ) -> list[tuple[int, int]]:
        rows = self._connection.execute(
            """
            SELECT github_number, id FROM pull_requests
            WHERE repo_id = %s
              AND created_at >= %s
              AND created_at < %s + interval '1 day'
            ORDER BY github_number
            """,
            (repository_id, _midnight_utc(start), _midnight_utc(end)),
        ).fetchall()
        return [(int(number), int(row_id)) for number, row_id in rows]

    def repository_id_for_github_id(self, github_id: int) -> int | None:
        row = self._connection.execute(
            "SELECT id FROM repositories WHERE github_id = %s",
            (github_id,),
        ).fetchone()
        return int(row[0]) if row else None

    def count_repository_commits(self, repository_id: int) -> int:
        return self.count_commits(repository_id)

    def collaboration_counts(self, repository_id: int, start: date, end: date) -> dict[str, int]:
        pull_requests = self._connection.execute(
            """
            SELECT count(*), count(first_response_at)
            FROM pull_requests
            WHERE repo_id = %s AND created_at >= %s AND created_at < %s + interval '1 day'
            """,
            (repository_id, _midnight_utc(start), _midnight_utc(end)),
        ).fetchone()
        reviews = self._connection.execute(
            """
            SELECT count(*) FROM reviews review
            JOIN pull_requests pull_request ON pull_request.id = review.pull_request_id
            WHERE pull_request.repo_id = %s
              AND pull_request.created_at >= %s
              AND pull_request.created_at < %s + interval '1 day'
            """,
            (repository_id, _midnight_utc(start), _midnight_utc(end)),
        ).fetchone()
        issues = self._connection.execute(
            """
            SELECT count(*), count(first_response_at)
            FROM issues
            WHERE repo_id = %s AND created_at >= %s AND created_at < %s + interval '1 day'
            """,
            (repository_id, _midnight_utc(start), _midnight_utc(end)),
        ).fetchone()
        return {
            "pull_requests": int(pull_requests[0]),
            "pr_responses": int(pull_requests[1]),
            "reviews": int(reviews[0]),
            "issues": int(issues[0]),
            "issue_responses": int(issues[1]),
        }

    def fail_stale_runs(self, older_than_minutes: int = 10) -> int:
        with self._connection.transaction():
            result = self._connection.execute(
                """
                UPDATE collection_runs
                SET status = 'failed', finished_at = now(),
                    error_summary = COALESCE(
                        error_summary, 'Marked failed after interrupted process'
                    )
                WHERE status = 'running'
                  AND started_at < now() - (%s * interval '1 minute')
                """,
                (older_than_minutes,),
            )
        return result.rowcount

    def count_commits(self, repository_id: int) -> int:
        row = self._connection.execute(
            "SELECT count(*) FROM commits WHERE repo_id = %s",
            (repository_id,),
        ).fetchone()
        return int(row[0])

    def _ensure_contributor(
        self, author: dict[str, Any] | None, first_seen_at: str
    ) -> int | None:
        if not author:
            return None
        row = self._connection.execute(
            """
            INSERT INTO contributors (contributor_key, is_bot, first_seen_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (contributor_key) DO UPDATE SET
                is_bot = contributors.is_bot OR EXCLUDED.is_bot,
                first_seen_at = LEAST(contributors.first_seen_at, EXCLUDED.first_seen_at)
            RETURNING id
            """,
            (author["contributor_key"], author["is_bot"], _timestamp(first_seen_at)),
        ).fetchone()
        return int(row[0])

    def upsert_issue(self, repository_id: int, issue: dict[str, Any]) -> None:
        with self._connection.transaction():
            author_id = self._ensure_contributor(issue.get("author"), issue["created_at"])
            self._connection.execute(
                """
                INSERT INTO issues (repo_id, github_number, author_id, created_at, closed_at,
                                    first_response_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (repo_id, github_number) DO UPDATE SET
                    author_id = EXCLUDED.author_id,
                    created_at = EXCLUDED.created_at,
                    closed_at = EXCLUDED.closed_at,
                    first_response_at = CASE
                        WHEN issues.first_response_at IS NULL THEN EXCLUDED.first_response_at
                        WHEN EXCLUDED.first_response_at IS NULL THEN issues.first_response_at
                        ELSE LEAST(issues.first_response_at, EXCLUDED.first_response_at)
                    END
                """,
                (
                    repository_id,
                    issue["number"],
                    author_id,
                    _timestamp(issue["created_at"]),
                    _optional_timestamp(issue.get("closed_at")),
                    _optional_timestamp(issue.get("first_response_at")),
                ),
            )

    def upsert_pull_request(
        self, repository_id: int, pull_request: dict[str, Any]
    ) -> int:
        with self._connection.transaction():
            author_id = self._ensure_contributor(
                pull_request.get("author"), pull_request["created_at"]
            )
            merged_at = _optional_timestamp(pull_request.get("merged_at"))
            state = "merged" if merged_at else pull_request["state"]
            row = self._connection.execute(
                """
                INSERT INTO pull_requests (repo_id, github_number, author_id, state, created_at,
                                           merged_at, closed_at, first_response_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (repo_id, github_number) DO UPDATE SET
                    author_id = EXCLUDED.author_id,
                    state = EXCLUDED.state,
                    created_at = EXCLUDED.created_at,
                    merged_at = EXCLUDED.merged_at,
                    closed_at = EXCLUDED.closed_at,
                    first_response_at = CASE
                        WHEN pull_requests.first_response_at IS NULL THEN EXCLUDED.first_response_at
                        WHEN EXCLUDED.first_response_at IS NULL THEN pull_requests.first_response_at
                        ELSE LEAST(pull_requests.first_response_at, EXCLUDED.first_response_at)
                    END
                RETURNING id
                """,
                (
                    repository_id,
                    pull_request["number"],
                    author_id,
                    state,
                    _timestamp(pull_request["created_at"]),
                    merged_at,
                    _optional_timestamp(pull_request.get("closed_at")),
                    _optional_timestamp(pull_request.get("first_response_at")),
                ),
            ).fetchone()
        return int(row[0])

    def upsert_review(self, pull_request_id: int, review: dict[str, Any]) -> None:
        if not isinstance(review.get("github_id"), int):
            return
        submitted_at = _optional_timestamp(review.get("submitted_at"))
        author_id = (
            self._ensure_contributor(review.get("reviewer"), review["submitted_at"])
            if review.get("submitted_at")
            else None
        )
        with self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO reviews (pull_request_id, github_id, reviewer_id, state, submitted_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pull_request_id, github_id) WHERE github_id IS NOT NULL
                DO UPDATE SET reviewer_id = EXCLUDED.reviewer_id,
                              state = EXCLUDED.state,
                              submitted_at = EXCLUDED.submitted_at
                """,
                (pull_request_id, review["github_id"], author_id, review["state"], submitted_at),
            )

    def get_progress(self, repository_id: int) -> dict[str, Any] | None:
        row = self._connection.execute(
            """
            SELECT cursor, last_page, status, requests_used
            FROM collection_progress
            WHERE repo_id = %s AND resource_type = 'commits'
            """,
            (repository_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "cursor": row[0],
            "last_page": row[1],
            "status": row[2],
            "requests_used": row[3],
        }

    def begin_commit_progress(
        self,
        repository_id: int,
        initial_cursor: str,
        *,
        refresh: bool,
    ) -> dict[str, Any] | None:
        progress = self.get_progress(repository_id)
        if progress and progress["status"] == "done" and not refresh:
            return None
        resume = bool(
            progress
            and progress["status"] in {"running", "failed"}
            and progress["cursor"]
            and not refresh
        )
        cursor = progress["cursor"] if resume else initial_cursor
        last_page = progress["last_page"] if resume else 0
        requests_used = progress["requests_used"] if resume else 0
        with self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO collection_progress (
                    repo_id, resource_type, cursor, last_page, status, requests_used, updated_at
                )
                VALUES (%s, 'commits', %s, %s, 'running', %s, now())
                ON CONFLICT (repo_id, resource_type) DO UPDATE SET
                    cursor = EXCLUDED.cursor,
                    last_page = EXCLUDED.last_page,
                    status = 'running',
                    requests_used = EXCLUDED.requests_used,
                    updated_at = now()
                """,
                (repository_id, cursor, last_page, requests_used),
            )
        return {
            "cursor": cursor,
            "last_page": last_page,
            "status": "running",
            "requests_used": requests_used,
        }

    def save_commit_page(
        self,
        repository_id: int,
        commits: list[dict[str, Any]],
        *,
        next_cursor: str | None,
        page_number: int,
        requests_used: int,
    ) -> None:
        with self._connection.transaction():
            contributor_ids: dict[str, int] = {}
            contributors: dict[str, tuple[bool, datetime]] = {}
            for commit in commits:
                author = commit.get("author")
                if not author:
                    continue
                key = author["contributor_key"]
                committed_at = _timestamp(commit["committed_at"])
                prior = contributors.get(key)
                contributors[key] = (
                    author["is_bot"] or (prior[0] if prior else False),
                    min(committed_at, prior[1]) if prior else committed_at,
                )
            for key, (is_bot, first_seen_at) in contributors.items():
                contributor = self._connection.execute(
                    """
                    INSERT INTO contributors (contributor_key, is_bot, first_seen_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (contributor_key) DO UPDATE SET
                        is_bot = contributors.is_bot OR EXCLUDED.is_bot,
                        first_seen_at = LEAST(contributors.first_seen_at, EXCLUDED.first_seen_at)
                    RETURNING id
                    """,
                    (key, is_bot, first_seen_at),
                ).fetchone()
                contributor_ids[key] = int(contributor[0])
            for commit in commits:
                author = commit.get("author")
                contributor_id = (
                    contributor_ids[author["contributor_key"]] if author else None
                )
                self._connection.execute(
                    """
                    INSERT INTO commits (repo_id, contributor_id, sha, committed_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (repo_id, sha) DO UPDATE SET
                        contributor_id = EXCLUDED.contributor_id,
                        committed_at = EXCLUDED.committed_at
                    """,
                    (
                        repository_id,
                        contributor_id,
                        commit["sha"],
                        _timestamp(commit["committed_at"]),
                    ),
                )
            self._connection.execute(
                """
                UPDATE collection_progress
                SET cursor = %s,
                    last_page = %s,
                    status = %s,
                    requests_used = requests_used + %s,
                    updated_at = now()
                WHERE repo_id = %s AND resource_type = 'commits'
                """,
                (
                    next_cursor,
                    page_number,
                    "done" if next_cursor is None else "running",
                    requests_used,
                    repository_id,
                ),
            )

    def fail_commit_progress(self, repository_id: int, requests_used: int) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                UPDATE collection_progress
                SET status = 'failed', requests_used = requests_used + %s, updated_at = now()
                WHERE repo_id = %s AND resource_type = 'commits'
                """,
                (requests_used, repository_id),
            )

    def finish_empty_commit_collection(self, repository_id: int, requests_used: int) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                UPDATE collection_progress
                SET cursor = NULL, last_page = 0, status = 'done',
                    requests_used = requests_used + %s, updated_at = now()
                WHERE repo_id = %s AND resource_type = 'commits'
                """,
                (requests_used, repository_id),
            )

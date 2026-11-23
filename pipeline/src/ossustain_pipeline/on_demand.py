"""Durable database-backed worker for bounded, public-repository analysis jobs."""

import hmac
import logging
import re
import time
from datetime import UTC, date, datetime, timedelta
from math import isfinite, nan
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import quote, urlencode

import psycopg
from psycopg.types.json import Jsonb

from ossustain_pipeline.config import load_config
from ossustain_pipeline.db import connect
from ossustain_pipeline.features.core import (
    CommitEvent,
    IssueEvent,
    PullRequestEvent,
    ReviewEvent,
    compute_features,
)
from ossustain_pipeline.github.cache import CachedResponse
from ossustain_pipeline.github.client import (
    GitHubAPIError,
    GitHubClient,
    GitHubRateLimitError,
    RequestBudget,
    RequestBudgetExceeded,
)
from ossustain_pipeline.predictions.core import (
    RiskCutoffs,
    activity_baseline_score,
    local_feature_deltas,
    risk_category,
    validation_risk_cutoffs,
)
from ossustain_pipeline.predictions.runner import (
    _choose_model,
    _feature_names,
    _load_artifact,
    _load_training_rows,
    _scores,
)

LOGGER = logging.getLogger(__name__)
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
MAX_JOB_REQUESTS = 300
MAX_GLOBAL_HOURLY_REQUESTS = 1000
LOOKBACK_DAYS = 180


class _MemoryCache:
    """Keep response payloads in memory only; on-demand events are never disk-cached."""

    def read(self, url: str) -> None:
        return None

    def write(self, url: str, response: CachedResponse) -> None:
        return None


def _mask_bounded_history_features(features: dict[str, Any]) -> dict[str, Any]:
    """Avoid treating the beginning of a bounded lookback as repository first activity."""
    bounded = dict(features)
    bounded["new_contributors_90d"] = None
    bounded["newcomer_retention_rate_90d"] = None
    return bounded


def _pages(client: GitHubClient, url: str, budget: RequestBudget):
    while url:
        page = client.get_json(url, budget=budget)
        yield page.body
        url = page.next_url


def _request_budget(connection: psycopg.Connection[Any], job_id: str) -> RequestBudget:
    def reserve() -> None:
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(771603017)")
            updated = connection.execute(
                """UPDATE analysis_jobs SET requests_used = requests_used + 1,
                     lease_until = now() + interval '10 minutes'
                   WHERE id = %s AND requests_used < %s AND status = 'running' RETURNING id""",
                (job_id, MAX_JOB_REQUESTS),
            ).fetchone()
            if updated is None:
                raise RequestBudgetExceeded("The analysis request budget has been exhausted")
            global_row = connection.execute(
                """INSERT INTO on_demand_api_requests (requested_at)
                   SELECT now() WHERE (SELECT count(*) FROM on_demand_api_requests
                     WHERE requested_at > now() - interval '1 hour') < %s RETURNING requested_at""",
                (MAX_GLOBAL_HOURLY_REQUESTS,),
            ).fetchone()
            if global_row is None:
                raise RequestBudgetExceeded(
                    "The on-demand hourly request budget has been exhausted"
                )

    return RequestBudget(MAX_JOB_REQUESTS, on_consume=reserve)


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _collect(
    client: GitHubClient,
    budget: RequestBudget,
    repository: str,
    hash_secret: str,
    today: date,
) -> tuple[
    list[CommitEvent], list[PullRequestEvent], list[IssueEvent], list[ReviewEvent], list[str]
]:
    owner, name = repository.split("/", maxsplit=1)
    base = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    metadata = client.get_json(base, budget=budget).body
    if metadata.get("private") is not False:
        raise ValueError("Repository is not public or could not be verified as public")
    if metadata.get("disabled") or metadata.get("archived"):
        raise ValueError("Disabled or archived repositories cannot be analyzed")
    canonical = str(metadata.get("full_name", ""))
    if canonical.casefold() != repository.casefold():
        repository = canonical
        owner, name = repository.split("/", maxsplit=1)
        base = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    start = datetime.combine(today - timedelta(days=LOOKBACK_DAYS), datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    since, until = start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")
    commits: list[CommitEvent] = []
    for page in _pages(
        client,
        f"{base}/commits?{urlencode({'since': since, 'until': until, 'per_page': 100})}",
        budget,
    ):
        for item in page:
            commit = item.get("commit", {})
            committed_at = _timestamp((commit.get("committer") or {}).get("date"))
            if committed_at is None:
                continue
            author = item.get("author") or {}
            login = str(author.get("login", "")).casefold()
            is_bot = str(author.get("type", "")).casefold() == "bot" or login.endswith("[bot]")
            identity = author.get("id")
            contributor_id = (
                int.from_bytes(
                    hmac.digest(hash_secret.encode(), str(identity).encode(), "sha256"), "big"
                )
                if isinstance(identity, int) and identity > 0
                else None
            )
            commits.append(CommitEvent(committed_at, contributor_id, is_bot))

    trailing_start = today - timedelta(days=90)
    pull_requests: list[PullRequestEvent] = []
    reviews: list[ReviewEvent] = []
    pulls_url = f"{base}/pulls?state=all&sort=created&direction=desc&per_page=100"
    for page in _pages(client, pulls_url, budget):
        old_page = True
        for pull in page:
            created = _timestamp(pull.get("created_at"))
            if created is None:
                continue
            if created.date() < start.date():
                continue
            old_page = False
            merged = _timestamp(pull.get("merged_at"))
            first_response = None
            number = int(pull["number"])
            author_id = (pull.get("user") or {}).get("id")
            if created.date() >= trailing_start:
                for route in (
                    f"{base}/issues/{number}/comments?per_page=100",
                    f"{base}/pulls/{number}/reviews?per_page=100",
                ):
                    for response_page in _pages(client, route, budget):
                        for event in response_page:
                            responder_id = (event.get("user") or {}).get("id")
                            if author_id is not None and responder_id == author_id:
                                continue
                            responded = _timestamp(
                                event.get("created_at") or event.get("submitted_at")
                            )
                            if responded is not None and responded >= created:
                                first_response = (
                                    min(first_response, responded) if first_response else responded
                                )
                            if "/reviews?" in route:
                                reviews.append(ReviewEvent(number, created, responded))
            pull_requests.append(PullRequestEvent(number, created, merged, first_response))
        if old_page:
            break

    issues: list[IssueEvent] = []
    issues_url = f"{base}/issues?state=all&sort=created&direction=desc&per_page=100"
    for page in _pages(client, issues_url, budget):
        old_page = True
        for issue in page:
            created = _timestamp(issue.get("created_at"))
            if created is None or created.date() < start.date():
                continue
            old_page = False
            if "pull_request" in issue:
                continue
            response = None
            author_id = (issue.get("user") or {}).get("id")
            if int(issue.get("comments", 0)) > 0:
                route = f"{base}/issues/{int(issue['number'])}/comments?per_page=100"
                for response_page in _pages(client, route, budget):
                    for event in response_page:
                        responder_id = (event.get("user") or {}).get("id")
                        if author_id is not None and responder_id == author_id:
                            continue
                        responded = _timestamp(event.get("created_at"))
                        if responded is not None and responded >= created:
                            response = min(response, responded) if response else responded
            issues.append(IssueEvent(created, response))
        if old_page:
            break
    return commits, pull_requests, issues, reviews, []


def _score(connection: psycopg.Connection[Any], features: dict[str, Any]) -> dict[str, Any]:
    selected = _choose_model(connection, None)
    (
        model_id,
        dataset_id,
        feature_set_id,
        family,
        algorithm,
        artifact_path,
        _dataset_hash,
        _cohort,
        threshold,
        _validation_pr_auc,
        _params,
        _seed,
    ) = selected
    names = _feature_names(connection, int(feature_set_id), family)
    if not names:
        raise ValueError("Selected model has no registered input features")
    _label, rows = _load_training_rows(
        connection,
        dataset_version_id=int(dataset_id),
        feature_set_id=int(feature_set_id),
        names=names,
    )
    validation = [row for row in rows if row.split == "validation"]
    model = None if algorithm == "threshold_baseline" else _load_artifact(artifact_path)
    validation_scores = (
        [activity_baseline_score(row.features) for row in validation]
        if model is None
        else _scores(model, validation, names)
    )
    cutoffs_row = connection.execute(
        "SELECT risk_low_cutoff, risk_high_cutoff FROM model_versions WHERE id = %s", (model_id,)
    ).fetchone()
    cutoffs = (
        validation_risk_cutoffs(validation_scores)
        if cutoffs_row is None or cutoffs_row[0] is None or cutoffs_row[1] is None
        else RiskCutoffs(float(cutoffs_row[0]), float(cutoffs_row[1]))
    )
    mapped: dict[str, float] = {}
    missing = []
    for feature in names:
        value = features.get(feature)
        if value is None:
            missing.append(feature)
            mapped[feature] = nan
        else:
            mapped[feature] = float(value)
    score = (
        activity_baseline_score(mapped)
        if model is None
        else float(
            model.predict_proba([[mapped[field] for field in names]])[0][
                list(model.classes_).index(1)
            ]
        )
    )
    medians = {}
    for feature in names:
        available = [row.features[feature] for row in validation if isfinite(row.features[feature])]
        if available:
            medians[feature] = float(median(available))
    indicators = local_feature_deltas(model, names, mapped, medians)[:5]
    return {
        "model_version_id": int(model_id),
        "probability": score,
        "risk_category": risk_category(score, cutoffs),
        "feature_set_name": family,
        "algorithm": algorithm,
        "validation_threshold": float(threshold),
        "features": features,
        "indicators": indicators,
        "missing_features": missing,
    }


def _process(connection: psycopg.Connection[Any], row: tuple[Any, ...], config: Any) -> None:
    job_id, repository = str(row[0]), row[1]
    token = config.github_token.get_secret_value() if config.github_token else ""
    hash_secret = config.hash_secret.get_secret_value() if config.hash_secret else ""
    if not token or len(hash_secret) < 32:
        raise ValueError("Worker needs GITHUB_TOKEN and a 32-character OSSUSTAIN_HASH_SECRET")
    budget = _request_budget(connection, job_id)
    client = GitHubClient(token, _MemoryCache())
    today = datetime.now(UTC).date()
    commits, pulls, issues, reviews, _ = _collect(client, budget, repository, hash_secret, today)
    result = compute_features(commits, pulls, issues, reviews, today)
    features = _mask_bounded_history_features(result.features)
    prediction = _score(connection, features)
    total_requests = connection.execute(
        "SELECT requests_used FROM analysis_jobs WHERE id = %s", (job_id,)
    ).fetchone()[0]
    limitations = [
        "rolling_180_day_observation",
        "not_a_research_cohort_prediction",
        "first_observed_contributor_features_unavailable_with_bounded_history",
    ]
    if prediction["missing_features"]:
        limitations.append("missing_model_inputs_imputed_by_training_preprocessor")
    if not commits:
        limitations.append("no_observed_commits_in_180_days")
    with connection.transaction():
        changed = connection.execute(
            """UPDATE analysis_jobs SET status = 'succeeded', finished_at = now(),
               lease_until = NULL WHERE id = %s AND status = 'running' RETURNING id""",
            (job_id,),
        ).fetchone()
        if changed is None:
            return
        connection.execute(
            """INSERT INTO analysis_results
               (job_id, repository_full_name, model_version_id, probability, risk_category,
                prediction_date, feature_set_name, algorithm, limitation_flags, features,
                indicators, request_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                job_id,
                repository,
                prediction["model_version_id"],
                prediction["probability"],
                prediction["risk_category"],
                today,
                prediction["feature_set_name"],
                prediction["algorithm"],
                Jsonb(limitations),
                Jsonb(prediction["features"]),
                Jsonb(prediction["indicators"]),
                total_requests,
            ),
        )


def _claim(connection: psycopg.Connection[Any]) -> tuple[Any, ...] | None:
    return connection.execute("""
        UPDATE analysis_jobs SET status = 'running', started_at = COALESCE(started_at, now()),
            attempt_count = attempt_count + 1, lease_until = now() + interval '10 minutes'
        WHERE id = (SELECT id FROM analysis_jobs
          WHERE status = 'queued' OR (status = 'running' AND lease_until < now())
          ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING id, repository_full_name, attempt_count
        """).fetchone()


def run_worker(config_path: Path, *, poll_seconds: int = 5, once: bool = False) -> None:
    config = load_config(config_path)
    with connect(config) as connection:
        last_purge = 0.0
        while True:
            if time.monotonic() - last_purge >= 3600:
                with connection.transaction():
                    connection.execute(
                        "DELETE FROM analysis_jobs WHERE created_at < now() - interval '30 days'"
                    )
                    connection.execute(
                        """DELETE FROM on_demand_api_requests
                           WHERE requested_at < now() - interval '1 hour'"""
                    )
                last_purge = time.monotonic()
            job = _claim(connection)
            if job is None:
                if once:
                    return
                time.sleep(poll_seconds)
                continue
            try:
                _process(connection, job, config)
            except Exception as error:
                LOGGER.exception("On-demand analysis failed for job %s", job[0])
                permanent_github_error = (
                    isinstance(error, GitHubAPIError)
                    and not isinstance(error, GitHubRateLimitError)
                    and error.status_code in {401, 403, 404}
                )
                status = (
                    "failed"
                    if int(job[2]) >= 3
                    or isinstance(error, (ValueError, RequestBudgetExceeded))
                    or permanent_github_error
                    else "queued"
                )
                if isinstance(error, RequestBudgetExceeded):
                    code = "request_limit"
                elif isinstance(error, GitHubRateLimitError):
                    code = "github_rate_limit"
                elif isinstance(error, GitHubAPIError) and error.status_code == 404:
                    code = "repository_unavailable"
                elif isinstance(error, GitHubAPIError) and error.status_code == 401:
                    code = "github_auth_failed"
                elif isinstance(error, GitHubAPIError) and error.status_code == 403:
                    code = "repository_unavailable"
                elif isinstance(error, ValueError) and any(
                    term in str(error).lower() for term in ("model", "artifact")
                ):
                    code = "model_unavailable"
                else:
                    code = "analysis_failed"
                connection.execute(
                    """UPDATE analysis_jobs SET status = %s, error_code = %s,
                       finished_at = CASE WHEN %s = 'failed' THEN now() ELSE NULL END,
                       lease_until = NULL WHERE id = %s AND status = 'running'""",
                    (status, code, status, job[0]),
                )
            if once:
                return

"""Validated cohort input and privacy-preserving GitHub record transforms."""

import hashlib
import hmac
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

SizeGroup = Literal["small", "medium", "large"]


class SelectedRepository(BaseModel):
    model_config = ConfigDict(extra="ignore")

    github_id: int = Field(gt=0)
    full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    default_branch: str = Field(min_length=1)
    created_at: date
    stars: int = Field(ge=0)
    primary_language: str | None
    archived: bool
    fork: bool
    size_group: SizeGroup
    inclusion_notes: str = ""


class CohortSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cohort_name: str = Field(min_length=1)
    screen_id: str = Field(min_length=1)
    criteria: dict[str, Any]
    repositories: list[SelectedRepository] = Field(min_length=1)

    @property
    def selection_date(self) -> date:
        try:
            return date.fromisoformat(str(self.criteria["selection_date"]))
        except (KeyError, ValueError) as error:
            raise ValueError("Cohort criteria must contain an ISO selection_date") from error

    @property
    def config_hash(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_cohort(path: Path) -> CohortSelection:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Cohort configuration not found: {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in cohort configuration: {path}") from error
    if not isinstance(raw, dict):
        raise ValueError("Cohort configuration must be a YAML mapping")
    try:
        cohort = CohortSelection.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"Invalid cohort configuration: {error}") from error
    ids = [repository.github_id for repository in cohort.repositories]
    if len(ids) != len(set(ids)):
        raise ValueError("Cohort repositories must have unique GitHub IDs")
    return cohort


def contributor_identity(user: Any, hash_secret: str) -> dict[str, Any] | None:
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    if not isinstance(user_id, int) or user_id <= 0:
        return None
    login = user.get("login")
    is_bot = str(user.get("type", "")).casefold() == "bot" or str(login or "").casefold().endswith(
        "[bot]"
    )
    key = hmac.new(
        hash_secret.encode("utf-8"),
        str(user_id).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return {"contributor_key": key, "is_bot": is_bot}


def redact_repository_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Repository metadata response must be a JSON object")
    fields = (
        "id",
        "full_name",
        "name",
        "default_branch",
        "created_at",
        "stargazers_count",
        "language",
        "archived",
        "fork",
    )
    return {field: payload.get(field) for field in fields}


def redact_commit_page(payload: Any, hash_secret: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Commit page response must be a JSON array")
    redacted: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Commit page entries must be JSON objects")
        commit = item.get("commit")
        if not isinstance(commit, dict):
            raise ValueError("Commit response entry is missing its commit object")
        author = commit.get("author")
        committer = commit.get("committer")
        committed_at = None
        if isinstance(author, dict):
            committed_at = author.get("date")
        if not committed_at and isinstance(committer, dict):
            committed_at = committer.get("date")
        sha = item.get("sha")
        if not isinstance(sha, str) or not sha.strip() or not committed_at:
            raise ValueError("Commit response entry is missing a SHA or commit timestamp")
        redacted.append(
            {
                "sha": sha,
                "committed_at": committed_at,
                "author": contributor_identity(item.get("author"), hash_secret),
            }
        )
    return redacted

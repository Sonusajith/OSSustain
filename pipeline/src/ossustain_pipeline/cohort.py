"""Deterministic selection from a versioned, pre-screened candidate set."""

from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SizeGroup = Literal["small", "medium", "large"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SizeBand(StrictModel):
    min_stars: int = Field(ge=0)
    max_stars: int = Field(ge=1)
    target_size: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_band(self) -> "SizeBand":
        if self.min_stars > self.max_stars:
            raise ValueError("min_stars must not exceed max_stars")
        return self


class CohortCriteria(StrictModel):
    selection_date: date
    observation_start: date
    observation_end: date
    created_before: date
    pushed_within_days: int = Field(ge=1)
    max_prs_in_observation_period: int = Field(ge=1)
    random_seed: int = Field(ge=0)
    size_groups: dict[SizeGroup, SizeBand]

    @model_validator(mode="after")
    def validate_criteria(self) -> "CohortCriteria":
        if self.observation_start >= self.observation_end:
            raise ValueError("observation_start must precede observation_end")
        if self.created_before > self.observation_start:
            raise ValueError("created_before must guarantee repository age at observation start")
        if set(self.size_groups) != {"small", "medium", "large"}:
            raise ValueError("size_groups must define small, medium, and large")
        ordered = [self.size_groups[name] for name in ("small", "medium", "large")]
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.min_stars <= previous.max_stars:
                raise ValueError("star bands must be ordered and non-overlapping")
        if sum(band.target_size for band in ordered) != 50:
            raise ValueError("size-group target sizes must sum to 50 repositories")
        return self


class CandidateRepository(StrictModel):
    github_id: int = Field(gt=0)
    full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    default_branch: str = Field(min_length=1)
    created_at: date
    pushed_at: date
    stars: int = Field(ge=0)
    primary_language: str | None
    archived: bool
    fork: bool
    prs_in_observation_period: int = Field(ge=0)


class CandidateFile(StrictModel):
    screen_id: str
    criteria: CohortCriteria
    candidates: list[CandidateRepository]

    @model_validator(mode="after")
    def validate_candidates(self) -> "CandidateFile":
        ids = [candidate.github_id for candidate in self.candidates]
        names = [candidate.full_name.casefold() for candidate in self.candidates]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("candidate repositories must have unique GitHub IDs and names")
        return self


def _size_group(stars: int, bands: dict[SizeGroup, SizeBand]) -> SizeGroup | None:
    for name, band in bands.items():
        if band.min_stars <= stars <= band.max_stars:
            return name
    return None


def select_repositories(candidate_file: CandidateFile) -> list[dict[str, object]]:
    """Select target counts per star band using stable PR/stars/name ordering."""
    criteria = candidate_file.criteria
    latest_allowed_push = criteria.selection_date.toordinal() - criteria.pushed_within_days
    bands: dict[SizeGroup, list[tuple[CandidateRepository, SizeGroup]]] = {
        "small": [],
        "medium": [],
        "large": [],
    }

    for candidate in candidate_file.candidates:
        group = _size_group(candidate.stars, criteria.size_groups)
        if group is None:
            continue
        if candidate.archived or candidate.fork:
            continue
        if candidate.created_at >= criteria.created_before:
            continue
        if candidate.pushed_at.toordinal() < latest_allowed_push:
            continue
        if candidate.prs_in_observation_period > criteria.max_prs_in_observation_period:
            continue
        bands[group].append((candidate, group))

    selected: list[dict[str, object]] = []
    shortages: list[str] = []
    for group in ("small", "medium", "large"):
        ordered = sorted(
            bands[group],
            key=lambda row: sha256(
                f"{criteria.random_seed}:{row[0].full_name.casefold()}".encode()
            ).hexdigest(),
        )
        target_size = criteria.size_groups[group].target_size
        if len(ordered) < target_size:
            shortages.append(f"{group}: need {target_size}, found {len(ordered)}")
        for candidate, stratum in ordered[:target_size]:
            selected.append(
                {
                    **candidate.model_dump(mode="json"),
                    "size_group": stratum,
                    "inclusion_notes": (
                        f"Non-fork, non-archived; created before {criteria.created_before}; "
                        f"pushed within {criteria.pushed_within_days} days; "
                        f"{candidate.prs_in_observation_period} PRs in the observation period."
                    ),
                }
            )
    if shortages:
        raise ValueError("Insufficient eligible candidates: " + "; ".join(shortages))
    return selected


def select_cohort(candidate_config_path: Path, output_path: Path) -> list[dict[str, object]]:
    """Load candidate screen results, write a deterministic cohort config."""
    try:
        raw = yaml.safe_load(candidate_config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(
            f"Cohort candidate configuration not found: {candidate_config_path}"
        ) from error
    except yaml.YAMLError as error:
        raise ValueError(
            f"Invalid YAML in cohort candidate configuration: {candidate_config_path}"
        ) from error
    if not isinstance(raw, dict):
        raise ValueError("Cohort candidate configuration must be a YAML mapping")
    try:
        candidate_file = CandidateFile.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"Invalid cohort candidate configuration: {error}") from error

    selected = select_repositories(candidate_file)
    output = {
        "cohort_name": "ossustain-public-repositories-v1",
        "screen_id": candidate_file.screen_id,
        "criteria": candidate_file.criteria.model_dump(mode="json"),
        "repositories": selected,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(output, sort_keys=False), encoding="utf-8")
    return selected

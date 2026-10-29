"""Validated, versioned definitions for the Phase 2 research protocol."""

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabelPolicy(StrictModel):
    theta: float = Field(gt=0, lt=1)
    sensitivity_theta: tuple[float, float]
    min_reference_commits: int = Field(ge=1)
    reference_window_days: int = Field(ge=1)
    future_window_days: int = Field(ge=1)
    activity_definition: Literal["non_bot_default_branch_commits"]

    @model_validator(mode="after")
    def validate_sensitivity_thresholds(self) -> "LabelPolicy":
        if any(not 0 < threshold < 1 for threshold in self.sensitivity_theta):
            raise ValueError("sensitivity thresholds must be between 0 and 1")
        if len(set(self.sensitivity_theta)) != len(self.sensitivity_theta):
            raise ValueError("sensitivity thresholds must be distinct")
        if self.theta in self.sensitivity_theta:
            raise ValueError("sensitivity thresholds must differ from the primary theta")
        return self


class SplitWindow(StrictModel):
    start: date
    end: date

    @model_validator(mode="after")
    def validate_range(self) -> "SplitWindow":
        if self.start > self.end:
            raise ValueError("split start must be on or before its end")
        return self


class IdentityPolicy(StrictModel):
    exclude_github_type_bot: bool
    exclude_login_suffix: str
    unlinked_author_policy: Literal["retain_as_null"]
    identity_key: Literal["github_user_id"]


class ExperimentConfig(StrictModel):
    protocol_version: str
    selection_date: date
    observation_start: date
    observation_end: date
    snapshot_interval_days: int = Field(ge=1)
    purge_gap_days: int = Field(ge=90)
    random_seed: int = Field(ge=0)
    label: LabelPolicy
    identity: IdentityPolicy
    splits: dict[Literal["train", "validation", "test"], SplitWindow]

    @model_validator(mode="after")
    def validate_timeline(self) -> "ExperimentConfig":
        if self.observation_start >= self.observation_end:
            raise ValueError("observation_start must precede observation_end")
        if set(self.splits) != {"train", "validation", "test"}:
            raise ValueError("splits must define train, validation, and test")

        train, validation, test = (self.splits[name] for name in ("train", "validation", "test"))
        minimum_prediction_date = date.fromordinal(
            self.observation_start.toordinal() + self.label.reference_window_days
        )
        if train.start < minimum_prediction_date:
            raise ValueError("train starts before a complete reference window is available")
        last_labeled_future_date = date.fromordinal(
            test.end.toordinal() + self.label.future_window_days
        )
        if last_labeled_future_date > self.observation_end:
            raise ValueError("test ends before its future-label windows are complete")
        if validation.start.toordinal() - train.end.toordinal() < self.purge_gap_days:
            raise ValueError("train/validation split gap is shorter than purge_gap_days")
        if test.start.toordinal() - validation.end.toordinal() < self.purge_gap_days:
            raise ValueError("validation/test split gap is shorter than purge_gap_days")
        if train.start < self.observation_start or test.end > self.observation_end:
            raise ValueError("prediction split dates must lie within the observation period")
        if train.end >= validation.start or validation.end >= test.start:
            raise ValueError("split windows must be strictly chronological")
        return self


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load and validate the experiment configuration from YAML."""
    try:
        values = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Experiment configuration not found: {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in experiment configuration: {path}") from error
    if not isinstance(values, dict):
        raise ValueError("Experiment configuration must be a YAML mapping")
    try:
        return ExperimentConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError(f"Invalid experiment configuration: {error}") from error

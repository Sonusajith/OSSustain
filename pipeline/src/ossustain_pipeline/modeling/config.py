"""Validated model search and temporal evaluation protocol."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LogisticGrid(StrictModel):
    c: list[float]
    class_weight: list[Literal["balanced"] | None]


class ForestGrid(StrictModel):
    n_estimators: list[int]
    max_depth: list[int | None]
    min_samples_leaf: list[int]
    class_weight: list[Literal["balanced"]]


class GradientGrid(StrictModel):
    n_estimators: list[int]
    learning_rate: list[float]
    max_depth: list[int]


class ModelGrids(StrictModel):
    logistic_regression: LogisticGrid
    random_forest: ForestGrid
    gradient_boosting: GradientGrid


class ModelingConfig(StrictModel):
    protocol_version: str
    random_seed: int = Field(ge=0)
    selection_metric: Literal["pr_auc"]
    decision_threshold_metric: Literal["f1"]
    bootstrap_resamples: int = Field(ge=100)
    confidence_level: float = Field(gt=0, lt=1)
    calibration_bins: int = Field(ge=2, le=20)
    permutation_repeats: int = Field(ge=1)
    models: ModelGrids

    @model_validator(mode="after")
    def validate_grids(self) -> "ModelingConfig":
        if not self.protocol_version.strip():
            raise ValueError("protocol_version must not be empty")
        if any(value <= 0 for value in self.models.logistic_regression.c):
            raise ValueError("logistic regression C values must be positive")
        if any(value < 1 for value in self.models.random_forest.n_estimators):
            raise ValueError("random forest n_estimators values must be positive")
        if any(value < 1 for value in self.models.random_forest.min_samples_leaf):
            raise ValueError("random forest min_samples_leaf values must be positive")
        if any(value <= 0 for value in self.models.gradient_boosting.learning_rate):
            raise ValueError("gradient boosting learning rates must be positive")
        return self


def load_modeling_config(path: Path) -> ModelingConfig:
    """Read a versioned modeling configuration from YAML."""
    try:
        values = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Modeling configuration not found: {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in modeling configuration: {path}") from error
    if not isinstance(values, dict):
        raise ValueError("Modeling configuration must be a YAML mapping")
    try:
        return ModelingConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError(f"Invalid modeling configuration: {error}") from error

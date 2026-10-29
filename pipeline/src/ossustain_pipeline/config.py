"""Load and validate the pipeline's foundation configuration."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, PostgresDsn, ValidationError


class PipelineConfig(BaseModel):
    database_url: PostgresDsn


def load_config(path: Path) -> PipelineConfig:
    """Load YAML configuration and apply the environment URL override."""
    try:
        values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as error:
        raise ValueError(f"Configuration file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML configuration in {path}") from error

    if not isinstance(values, dict):
        raise ValueError("Configuration must be a YAML mapping")

    database_url = os.getenv("OSSUSTAIN_DATABASE_URL")
    if database_url:
        values["database_url"] = database_url

    try:
        return PipelineConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError(f"Invalid pipeline configuration: {error}") from error

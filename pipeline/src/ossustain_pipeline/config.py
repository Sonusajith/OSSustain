"""Load and validate the pipeline's foundation configuration."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, PostgresDsn, SecretStr, ValidationError


class PipelineConfig(BaseModel):
    database_url: PostgresDsn
    github_token: SecretStr | None = None
    hash_secret: SecretStr | None = None


def _load_local_env(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except OSError as error:
        raise ValueError(f"Could not read local environment file: {path}") from error

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, value = entry.partition("=")
        if not separator or not key.strip():
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not os.environ.get(key) and value:
            os.environ[key] = value


def load_config(path: Path, env_path: Path | None = None) -> PipelineConfig:
    """Load YAML configuration and apply the environment URL override."""
    local_env_path = env_path or Path(__file__).resolve().parents[3] / ".env"
    _load_local_env(local_env_path)

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
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        values["github_token"] = github_token
    hash_secret = os.getenv("OSSUSTAIN_HASH_SECRET")
    if hash_secret:
        values["hash_secret"] = hash_secret

    try:
        return PipelineConfig.model_validate(values)
    except ValidationError as error:
        raise ValueError(f"Invalid pipeline configuration: {error}") from error

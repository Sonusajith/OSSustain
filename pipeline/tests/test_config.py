from pathlib import Path

import pytest

from ossustain_pipeline.config import load_config


def test_load_config_reads_database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        "database_url: postgresql://user:password@localhost:5432/testdb\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OSSUSTAIN_DATABASE_URL", raising=False)

    config = load_config(config_path, env_path=tmp_path / ".env")

    assert str(config.database_url) == "postgresql://user:password@localhost:5432/testdb"


def test_environment_database_url_overrides_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        "database_url: postgresql://yaml:password@localhost:5432/yaml\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OSSUSTAIN_DATABASE_URL", "postgresql://env:password@localhost:5432/env")

    config = load_config(config_path, env_path=tmp_path / ".env")

    assert str(config.database_url) == "postgresql://env:password@localhost:5432/env"


def test_load_config_rejects_missing_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.delenv("OSSUSTAIN_DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="Invalid pipeline configuration"):
        load_config(config_path, env_path=tmp_path / ".env")


def test_local_env_supplies_collection_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "pipeline.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        "database_url: postgresql://user:password@localhost:5432/testdb\n",
        encoding="utf-8",
    )
    env_path.write_text(
        "GITHUB_TOKEN=local-token\nOSSUSTAIN_HASH_SECRET=local-hash-secret-value\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("OSSUSTAIN_HASH_SECRET", raising=False)
    monkeypatch.delenv("OSSUSTAIN_DATABASE_URL", raising=False)

    config = load_config(config_path, env_path=env_path)

    assert config.github_token.get_secret_value() == "local-token"
    assert config.hash_secret.get_secret_value() == "local-hash-secret-value"

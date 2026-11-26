import subprocess
from io import BytesIO
from pathlib import Path

import psycopg
import pytest
from pydantic import SecretStr

from ossustain_pipeline import preflight
from ossustain_pipeline.config import PipelineConfig


def _config() -> PipelineConfig:
    return PipelineConfig(
        database_url="postgresql://operator:private-pass@localhost:5432/ossustain",
        github_token=SecretStr("private-github-token"),
        hash_secret=SecretStr("h" * 40),
    )


def _environment() -> dict[str, str]:
    return {
        "OSSUSTAIN_ANALYSIS_IP_HASH_SECRET": "i" * 40,
        "OSSUSTAIN_ADMIN_USERNAME": "ossustain-admin",
        "OSSUSTAIN_ADMIN_PASSWORD": "p" * 20,
    }


def test_environment_check_passes_without_disclosing_secret_values() -> None:
    checks = preflight.check_environment(_config(), _environment())

    assert all(check.passed for check in checks)
    output = " ".join(check.message for check in checks)
    assert "private-github-token" not in output
    assert "h" * 40 not in output
    assert "p" * 20 not in output


def test_environment_check_reports_each_missing_or_placeholder_setting() -> None:
    environment = {
        "OSSUSTAIN_ANALYSIS_IP_HASH_SECRET": "change-this-local-rate-limit-salt",
        "OSSUSTAIN_ADMIN_USERNAME": "",
        "OSSUSTAIN_ADMIN_PASSWORD": "short",
    }
    config = PipelineConfig(database_url="postgresql://operator:pass@localhost/db")

    checks = preflight.check_environment(config, environment)

    failures = {check.name: check.message for check in checks if not check.passed}
    assert set(failures) == {
        "GitHub token",
        "Contributor hash secret",
        "Analysis IP hash secret",
        "First administrator",
        "Administrator password",
    }
    assert all("change-this-local-rate-limit-salt" not in message for message in failures.values())


def test_database_failure_is_actionable_and_does_not_echo_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()

    def fail_connect(_config: PipelineConfig):
        raise psycopg.OperationalError("failed for private-pass")

    monkeypatch.setattr(preflight, "connect", fail_connect)
    check = preflight.check_database_and_model(config)

    assert not check.passed
    assert "PostgreSQL" in check.message
    assert "private-pass" not in check.message


def test_missing_selected_artifact_fails_with_safe_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(preflight, "connect", lambda _config: Connection())
    monkeypatch.setattr(
        preflight,
        "_choose_model",
        lambda _connection, _dataset: (1, 1, 1, "extended", "random_forest", "secret/path.joblib"),
    )
    monkeypatch.setattr(
        preflight, "_load_artifact", lambda _path: (_ for _ in ()).throw(FileNotFoundError())
    )

    check = preflight.check_database_and_model(_config())

    assert not check.passed
    assert "artifact is missing or unreadable" in check.message
    assert "secret/path.joblib" not in check.message


def test_selected_threshold_model_passes_without_a_model_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(preflight, "connect", lambda _config: Connection())
    monkeypatch.setattr(
        preflight,
        "_choose_model",
        lambda _connection, _dataset: (1, 1, 1, "activity_only", "threshold_baseline", None),
    )

    check = preflight.check_database_and_model(_config())

    assert check.passed
    assert "does not require a model file" in check.message


def test_worker_check_reports_missing_container_and_passes_when_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def run_compose(arguments: list[str], _root: Path):
        calls.append(arguments)
        if arguments[0] == "ps":
            return subprocess.CompletedProcess([], 0, "postgres\n", "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(
        preflight,
        "_run_compose",
        run_compose,
    )
    missing = preflight.check_worker(tmp_path)
    assert not missing.passed
    assert "docker compose up -d --build analysis-worker" in missing.message
    assert len(calls) == 1

    calls.clear()

    def worker_running(arguments: list[str], _root: Path):
        calls.append(arguments)
        if arguments[0] == "ps":
            return subprocess.CompletedProcess([], 0, "postgres\nanalysis-worker\n", "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(preflight, "_run_compose", worker_running)
    running = preflight.check_worker(tmp_path)
    assert running.passed
    assert calls[1][0:4] == ["exec", "-T", "analysis-worker", "python"]

    monkeypatch.setattr(
        preflight,
        "_run_compose",
        lambda arguments, _root: subprocess.CompletedProcess([], 1, "", "private database error")
        if arguments[0] == "exec"
        else subprocess.CompletedProcess([], 0, "analysis-worker\n", ""),
    )
    disconnected = preflight.check_worker(tmp_path)
    assert not disconnected.passed
    assert "cannot connect" in disconnected.message
    assert "private database error" not in disconnected.message


def test_api_health_check_accepts_healthy_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()
            return False

    monkeypatch.setattr(preflight, "urlopen", lambda _url, timeout: Response(b'{"status":"UP"}'))

    check = preflight.check_api_health("http://localhost:8080/actuator/health")

    assert check.passed
    assert check.message == "Spring health endpoint reports UP."


def test_api_health_check_rejects_unexpected_json_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()
            return False

    monkeypatch.setattr(preflight, "urlopen", lambda _url, timeout: Response(b"[]"))

    check = preflight.check_api_health("http://localhost:8080/actuator/health")

    assert not check.passed
    assert "not ready" in check.message

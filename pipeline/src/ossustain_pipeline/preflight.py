"""Safe operator checks for the bounded on-demand analysis stack."""

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

import psycopg

from ossustain_pipeline.config import PipelineConfig, load_config
from ossustain_pipeline.db import connect
from ossustain_pipeline.predictions.runner import _choose_model, _load_artifact


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.passed for check in self.checks)


def _configured(value: str | None) -> bool:
    if not value or not value.strip():
        return False
    lowered = value.strip().lower()
    return not lowered.startswith(("replace-with", "change-this", "your-"))


def check_environment(
    config: PipelineConfig, environment: Mapping[str, str]
) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    token = config.github_token.get_secret_value() if config.github_token else ""
    hash_secret = config.hash_secret.get_secret_value() if config.hash_secret else ""
    if _configured(token):
        checks.append(ReadinessCheck("GitHub token", True, "Worker credential is configured."))
    else:
        checks.append(
            ReadinessCheck(
                "GitHub token", False, "Set GITHUB_TOKEN in the private operator environment."
            )
        )

    if _configured(hash_secret) and len(hash_secret) >= 32:
        checks.append(
            ReadinessCheck("Contributor hash secret", True, "Worker hash secret is configured.")
        )
    else:
        checks.append(
            ReadinessCheck(
                "Contributor hash secret",
                False,
                "Set OSSUSTAIN_HASH_SECRET to a private random value of at least 32 characters.",
            )
        )

    ip_secret = environment.get("OSSUSTAIN_ANALYSIS_IP_HASH_SECRET")
    if _configured(ip_secret) and len(ip_secret.strip()) >= 32:
        checks.append(
            ReadinessCheck(
                "Analysis IP hash secret", True, "Stable API rate-limit secret is configured."
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "Analysis IP hash secret",
                False,
                "Set OSSUSTAIN_ANALYSIS_IP_HASH_SECRET to a private random value "
                "of at least 32 characters.",
            )
        )

    username = environment.get("OSSUSTAIN_ADMIN_USERNAME")
    if _configured(username):
        checks.append(
            ReadinessCheck("First administrator", True, "Bootstrap username is configured.")
        )
    else:
        checks.append(
            ReadinessCheck(
                "First administrator",
                False,
                "Set OSSUSTAIN_ADMIN_USERNAME and OSSUSTAIN_ADMIN_PASSWORD in "
                "the private operator environment.",
            )
        )
    password = environment.get("OSSUSTAIN_ADMIN_PASSWORD")
    if _configured(password) and len(password) >= 16:
        checks.append(
            ReadinessCheck(
                "Administrator password", True, "Bootstrap password meets the minimum length."
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                "Administrator password",
                False,
                "Set OSSUSTAIN_ADMIN_PASSWORD to a private password of at least 16 characters.",
            )
        )
    return checks


def check_database_and_model(config: PipelineConfig) -> ReadinessCheck:
    try:
        with connect(config) as connection:
            selected = _choose_model(connection, None)
            algorithm = selected[4]
            artifact_path = selected[5]
    except psycopg.Error:
        return ReadinessCheck(
            "Database and selected model",
            False,
            "Cannot reach the database or find a selected model; check PostgreSQL "
            "and run the research training setup.",
        )
    except ValueError as error:
        message = str(error)
        if "model" in message.lower() or "dataset" in message.lower():
            return ReadinessCheck("Database and selected model", False, message)
        return ReadinessCheck(
            "Database and selected model",
            False,
            "Database readiness check failed; verify migrations and selected model records.",
        )

    if algorithm == "threshold_baseline":
        return ReadinessCheck(
            "Database and selected model",
            True,
            "Database is reachable; the selected threshold baseline does not require a model file.",
        )
    if not artifact_path:
        return ReadinessCheck(
            "Database and selected model",
            False,
            "The selected fitted model has no artifact path; rerun training and "
            "verify the artifact mount.",
        )
    try:
        _load_artifact(artifact_path)
    except Exception:
        return ReadinessCheck(
            "Database and selected model",
            False,
            "The selected model artifact is missing or unreadable; verify training "
            "output and the read-only artifact mount.",
        )
    return ReadinessCheck(
        "Database and selected model", True, "Database and selected model artifact are ready."
    )


def _run_compose(arguments: list[str], root: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["docker", "compose", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_compose_configuration(root: Path) -> ReadinessCheck:
    local = _run_compose(["config", "--quiet"], root)
    production = _run_compose(
        [
            "--env-file",
            "deploy/production.env.example",
            "-f",
            "compose.production.yaml",
            "config",
            "--quiet",
        ],
        root,
    )
    if local is None or local.returncode != 0 or production is None or production.returncode != 0:
        return ReadinessCheck(
            "Docker Compose configuration",
            False,
            "Compose validation failed; review docker-compose.yml, "
            "compose.production.yaml, and the environment examples.",
        )
    return ReadinessCheck(
        "Docker Compose configuration", True, "Local and production Compose files validate."
    )


def check_api_health(url: str) -> ReadinessCheck:
    try:
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read())
    except (OSError, TimeoutError, URLError, ValueError):
        return ReadinessCheck(
            "Spring API",
            False,
            "Spring health check did not respond; start the backend and pass its "
            "/actuator/health URL if it uses a different address.",
        )
    if not isinstance(payload, dict) or payload.get("status") != "UP":
        return ReadinessCheck(
            "Spring API",
            False,
            "Spring reported that it is not ready; inspect the backend health endpoint.",
        )
    return ReadinessCheck("Spring API", True, "Spring health endpoint reports UP.")


def check_worker(root: Path) -> ReadinessCheck:
    result = _run_compose(["ps", "--status", "running", "--services"], root)
    if result is None or result.returncode != 0:
        return ReadinessCheck(
            "Analysis worker",
            False,
            "Docker Compose could not inspect services; start Docker Desktop and "
            "run the worker setup command.",
        )
    if "analysis-worker" not in result.stdout.splitlines():
        return ReadinessCheck(
            "Analysis worker",
            False,
            "The analysis-worker container is not running; start it with "
            "docker compose up -d --build analysis-worker.",
        )
    connectivity = _run_compose(
        [
            "exec",
            "-T",
            "analysis-worker",
            "python",
            "-c",
            "import os, psycopg; c=psycopg.connect(host=os.environ['PGHOST'], "
            "port=os.environ['PGPORT'], user=os.environ['PGUSER'], "
            "password=os.environ['PGPASSWORD'], dbname=os.environ['PGDATABASE'], "
            "connect_timeout=5); c.execute('SELECT 1 FROM analysis_jobs LIMIT 0'); c.close()",
        ],
        root,
    )
    if connectivity is None or connectivity.returncode != 0:
        return ReadinessCheck(
            "Analysis worker",
            False,
            "The worker cannot connect to its database or find the analysis-job table; "
            "check PostgreSQL readiness and apply backend migrations.",
        )
    return ReadinessCheck(
        "Analysis worker", True, "Worker is running and can reach the analysis database."
    )


def _default_api_health_url() -> str:
    explicit = os.environ.get("OSSUSTAIN_API_HEALTH_URL")
    if explicit:
        return explicit
    frontend_api = os.environ.get("VITE_API_BASE_URL", "http://localhost:8080/api/v1")
    parsed = urlsplit(frontend_api)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/actuator/health"
    return "http://localhost:8080/actuator/health"


def run_preflight(
    config_path: Path,
    *,
    api_health_url: str | None = None,
    env_path: Path | None = None,
    root: Path | None = None,
) -> ReadinessReport:
    project_root = (root or Path(__file__).resolve().parents[3]).resolve()
    selected_env = env_path
    if selected_env is not None and not selected_env.is_absolute():
        selected_env = project_root / selected_env

    try:
        config = load_config(config_path, env_path=selected_env)
    except ValueError:
        return ReadinessReport(
            (
                ReadinessCheck(
                    "Pipeline configuration",
                    False,
                    "Configuration is missing or invalid; check the database URL "
                    "in pipeline/config.yaml and private .env.",
                ),
            )
        )

    checks = check_environment(config, os.environ)
    checks.append(check_database_and_model(config))
    checks.append(check_compose_configuration(project_root))
    checks.append(check_api_health(api_health_url or _default_api_health_url()))
    checks.append(check_worker(project_root))
    return ReadinessReport(tuple(checks))

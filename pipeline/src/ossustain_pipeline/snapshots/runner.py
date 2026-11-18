"""Build an atomic, reproducible snapshot dataset from collected PostgreSQL events."""

import hashlib
import json
import subprocess
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ossustain_pipeline.collect.models import CohortSelection
from ossustain_pipeline.experiment import ExperimentConfig
from ossustain_pipeline.snapshots.core import (
    Commit,
    build_repository_snapshots,
    midnight,
    snapshot_values,
    summarize,
)


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_inputs(
    cohort: CohortSelection,
    config: ExperimentConfig,
    quality: dict[str, Any],
) -> None:
    if quality.get("cohort_config_hash") != cohort.config_hash:
        raise ValueError("Run validate for the current cohort before building snapshots")
    for key in ("observation_start", "observation_end"):
        if str(cohort.criteria.get(key)) != str(getattr(config, key)):
            raise ValueError(f"Experiment {key} differs from the collected cohort")
        if quality.get(key) != str(getattr(config, key)):
            raise ValueError(f"Quality report {key} differs from the experiment")
    reported = {r["github_id"]: r for r in quality.get("repositories", [])}
    if set(reported) != {r.github_id for r in cohort.repositories}:
        raise ValueError("Quality report must cover exactly the selected cohort")
    for row in reported.values():
        if any(
            row.get("stages_complete", {}).get(stage) is not True
            for stage in ("pull_requests", "reviews", "issues")
        ):
            raise ValueError("Complete Phase 4 collection and validation before snapshots")
    if (
        not config.identity.exclude_github_type_bot
        or config.identity.exclude_login_suffix != "[bot]"
    ):
        raise ValueError("Snapshot identity policy must match the recorded collector bot policy")


def code_identity() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[4]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    sources = [*Path(__file__).parent.glob("*.py"), Path(__file__).parents[1] / "experiment.py"]
    source_hash = digest({p.name: p.read_text(encoding="utf-8") for p in sorted(sources)})
    dirty = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "pipeline/src/ossustain_pipeline/snapshots",
            "pipeline/src/ossustain_pipeline/experiment.py",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return revision + ("+dirty" if dirty else ""), source_hash


def build_snapshots(
    connection: psycopg.Connection[Any],
    cohort: CohortSelection,
    config: ExperimentConfig,
    *,
    quality_report: Path,
    report_path: Path,
) -> dict[str, Any]:
    try:
        quality = json.loads(quality_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            "A readable Phase 4 validation report is required; run validate first"
        ) from error
    validate_inputs(cohort, config, quality)
    revision, implementation_hash = code_identity()
    definition = {
        "experiment": config.model_dump(mode="json"),
        "cohort_config_hash": cohort.config_hash,
        "implementation_hash": implementation_hash,
        "unknown_author_activity": "included_unless_known_bot",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    # All reads see one consistent database state; failed builds leave no partial version.
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        repository_rows = []
        inputs = []
        snapshot_rows = []
        summary_inputs = []
        for selected in sorted(cohort.repositories, key=lambda r: r.github_id):
            row = connection.execute(
                """
                SELECT r.id, p.status, p.updated_at
                FROM repositories r
                LEFT JOIN collection_progress p ON p.repo_id = r.id AND p.resource_type = 'commits'
                WHERE r.github_id = %s
                """,
                (selected.github_id,),
            ).fetchone()
            if (
                row is None
                or row[1] != "done"
                or row[2] < midnight(config.observation_end + timedelta(days=1))
            ):
                raise ValueError(f"Complete commit collection required for {selected.full_name}")
            repo_id = int(row[0])
            events = connection.execute(
                """
                SELECT c.sha, c.committed_at, author.is_bot
                FROM commits c LEFT JOIN contributors author ON author.id = c.contributor_id
                WHERE c.repo_id = %s AND c.committed_at >= %s
                  AND c.committed_at < %s::timestamptz + interval '1 day'
                ORDER BY c.committed_at, c.sha
                """,
                (repo_id, midnight(config.observation_start), midnight(config.observation_end)),
            ).fetchall()
            commits = [
                Commit(sha, timestamp.astimezone(UTC), is_bot) for sha, timestamp, is_bot in events
            ]
            snapshots = build_repository_snapshots(commits, config)
            summary_inputs.append((selected.size_group, snapshots))
            snapshot_rows.extend((repo_id, *snapshot_values(s)) for s in snapshots)
            inputs.append(
                {
                    "github_id": selected.github_id,
                    "events": [[c.sha, c.timestamp.isoformat(), c.is_bot] for c in commits],
                }
            )
            repository_rows.append(
                {
                    "github_id": selected.github_id,
                    "full_name": selected.full_name,
                    "size_group": selected.size_group,
                    "snapshots": len(snapshots),
                    "commits_in_observation": len(commits),
                    "known_bot_commits": sum(c.is_bot is True for c in commits),
                    "unknown_author_commits": sum(c.is_bot is None for c in commits),
                }
            )
        source_hash = digest(inputs)
        version_hash = digest(
            {
                "definition": definition,
                "source_hash": source_hash,
                "quality_report_hash": digest(quality),
            }
        )
        summary = summarize(summary_inputs, config)
        summary["repositories"] = repository_rows
        summary["quality_flags"] = [
            {"github_id": r["github_id"], "full_name": r["full_name"], "flags": r["quality_flags"]}
            for r in quality["repositories"]
            if r["quality_flags"]
        ]
        connection.execute(
            """
            INSERT INTO dataset_versions
                (version_hash, cohort_name, config, source_hash, code_revision, summary)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (version_hash) DO NOTHING
            """,
            (
                version_hash,
                cohort.cohort_name,
                Jsonb(definition),
                source_hash,
                revision,
                Jsonb(summary),
            ),
        )
        version_id, original_revision = connection.execute(
            "SELECT id, code_revision FROM dataset_versions WHERE version_hash = %s",
            (version_hash,),
        ).fetchone()
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO snapshots
                    (dataset_version_id, repo_id, prediction_date, reference_start, future_end,
                     observed_until, reference_activity, future_activity,
                     label, label_status, split)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_version_id, repo_id, prediction_date) DO NOTHING
                """,
                [(version_id, *row) for row in snapshot_rows],
            )
        stored = connection.execute(
            """SELECT repo_id, prediction_date, reference_start, future_end, observed_until,
                      reference_activity, future_activity, label, label_status, split
               FROM snapshots WHERE dataset_version_id = %s""",
            (version_id,),
        ).fetchall()
        if set(stored) != set(snapshot_rows):
            raise ValueError(
                "Stored snapshot version differs from reproducible input; refusing overwrite"
            )
    report = {
        "dataset_version_id": version_id,
        "dataset_version_hash": version_hash,
        "source_hash": source_hash,
        "code_revision": original_revision,
        "definition": definition,
        **summary,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

"""Build a content-addressed feature set from a versioned snapshot dataset."""

import hashlib
import json
import subprocess
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ossustain_pipeline.features.core import (
    FEATURE_DEFINITIONS,
    CommitEvent,
    IssueEvent,
    PullRequestEvent,
    ReviewEvent,
    compute_features,
)

FEATURE_CONFIG = {
    "activity_windows_days": [30, 90, 180],
    "diversity_window_days": 90,
    "prior_contributor_window_days": [90, 180],
    "newcomer_window_days": [90, 180],
    "collaboration_window_days": 90,
    "knowledge_policy": "include_events_with_unknown_bot_status; exclude_known_bots",
    "attribution_policy": "identity_features_use_linked_known_non_bot_authors_only",
    "unknown_authors": "retained_in_activity; excluded_from_contributor_distribution",
    "missing_values": "null_with_per_feature_missing_flag; no imputation",
    "cutoff": "all feature event timestamps must be strictly less than prediction_date UTC",
}


def _hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _code_identity() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[4]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(Path(__file__).parent.glob("*.py"))
    }
    code_hash = _hash(sources)
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "pipeline/src/ossustain_pipeline/features"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return revision + ("+dirty" if dirty else ""), code_hash


def _missingness(rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    total = len(rows)
    return {
        name: {
            "missing": sum(row["missing_flags"][name] for row in rows),
            "total": total,
            "rate": (sum(row["missing_flags"][name] for row in rows) / total if total else None),
        }
        for name in feature_names
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    names = [row["feature_name"] for row in FEATURE_DEFINITIONS]
    labeled_splits = ("train", "validation", "test")
    eligible = [
        row for row in rows if row["label_status"] == "labeled" and row["split"] in labeled_splits
    ]
    groups = sorted({row["size_group"] for row in rows})
    return {
        "snapshots": len(rows),
        "features": len(names),
        "labeled_train_validation_test_snapshots": len(eligible),
        "missingness": _missingness(rows, names),
        "missingness_by_size_group": {
            group: _missingness([row for row in rows if row["size_group"] == group], names)
            for group in groups
        },
        "missingness_by_eligible_split": {
            split: _missingness([row for row in eligible if row["split"] == split], names)
            for split in labeled_splits
        },
    }


def _display_metrics(features: dict[str, Any]) -> dict[str, Any]:
    names = (
        "commits_30d",
        "commits_90d",
        "active_contributors_90d",
        "contributor_gini_90d",
        "new_contributors_90d",
        "newcomer_retention_rate_90d",
        "pull_requests_opened_90d",
        "pull_requests_merged_90d",
        "issues_opened_90d",
        "median_pr_first_response_hours_90d",
        "median_issue_first_response_hours_90d",
    )
    return {name: features[name] for name in names}


def build_features(
    connection: psycopg.Connection[Any],
    *,
    dataset_version_id: int | None,
    report_path: Path,
) -> dict[str, Any]:
    """Compute and store all snapshot features atomically and idempotently."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    code_revision, code_hash = _code_identity()
    feature_definition = {
        "config": FEATURE_CONFIG,
        "feature_code_hash": code_hash,
        "definitions": FEATURE_DEFINITIONS,
    }
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        if dataset_version_id is None:
            version = connection.execute(
                "SELECT id, version_hash FROM dataset_versions "
                "ORDER BY created_at DESC, id DESC LIMIT 1"
            ).fetchone()
        else:
            version = connection.execute(
                "SELECT id, version_hash FROM dataset_versions WHERE id = %s",
                (dataset_version_id,),
            ).fetchone()
        if version is None:
            raise ValueError(
                "No matching Phase 5 dataset version exists; run build-snapshots first"
            )
        version_id, dataset_hash = int(version[0]), str(version[1])
        feature_set_hash = _hash(
            {
                "dataset_hash": dataset_hash,
                "feature_definition": feature_definition,
                "feature_names": sorted(row["feature_name"] for row in FEATURE_DEFINITIONS),
            }
        )
        snapshots = connection.execute(
            """
            SELECT snapshot.id, snapshot.repo_id, snapshot.prediction_date,
                   snapshot.label_status, snapshot.split, repository.size_group
            FROM snapshots snapshot
            JOIN repositories repository ON repository.id = snapshot.repo_id
            WHERE snapshot.dataset_version_id = %s
            ORDER BY snapshot.repo_id, snapshot.prediction_date
            """,
            (version_id,),
        ).fetchall()
        if not snapshots:
            raise ValueError(f"Dataset version {version_id} has no snapshots")

        by_repository: dict[int, list[tuple[Any, ...]]] = {}
        for row in snapshots:
            by_repository.setdefault(int(row[1]), []).append(row)

        # Collection runs are authoritative for all four resource stages. The
        # resumable progress table tracks commits only.
        repo_ids = list(by_repository)
        run_rows = connection.execute(
            """SELECT repo_id, stage, status FROM collection_runs
               WHERE repo_id = ANY(%s)
                 AND stage = ANY(%s)
               ORDER BY repo_id, stage, started_at DESC, id DESC""",
            (repo_ids, ["commits", "pull_requests", "reviews", "issues"]),
        ).fetchall()
        latest_status: dict[tuple[int, str], str] = {}
        for repo_id, stage, status in run_rows:
            latest_status.setdefault((int(repo_id), stage), status)
        required_stages = ("commits", "pull_requests", "reviews", "issues")
        incomplete = [
            repo_id
            for repo_id in repo_ids
            if any(latest_status.get((repo_id, stage)) != "done" for stage in required_stages)
        ]
        if incomplete:
            raise ValueError(
                "Latest Phase 3 and 4 collection run is not complete for repository ids "
                f"{incomplete[:10]}"
            )

        computed: list[dict[str, Any]] = []
        for repo_id, repo_snapshots in by_repository.items():
            last_prediction = max(row[2] for row in repo_snapshots)
            cutoff = _midnight(last_prediction)
            commits = [
                CommitEvent(timestamp.astimezone(UTC), contributor_id, is_bot)
                for timestamp, contributor_id, is_bot in connection.execute(
                    """SELECT commit.committed_at, commit.contributor_id, contributor.is_bot
                       FROM commits commit LEFT JOIN contributors contributor
                         ON contributor.id = commit.contributor_id
                       WHERE commit.repo_id = %s AND commit.committed_at < %s
                       ORDER BY commit.committed_at, commit.sha""",
                    (repo_id, cutoff),
                ).fetchall()
            ]
            pull_requests = [
                PullRequestEvent(
                    int(pr_id),
                    created.astimezone(UTC),
                    merged.astimezone(UTC) if merged else None,
                    first_response.astimezone(UTC) if first_response else None,
                )
                for pr_id, created, merged, first_response in connection.execute(
                    """SELECT id, created_at, merged_at, first_response_at FROM pull_requests
                       WHERE repo_id = %s AND created_at < %s ORDER BY created_at, id""",
                    (repo_id, cutoff),
                ).fetchall()
            ]
            issues = [
                IssueEvent(
                    created.astimezone(UTC),
                    first_response.astimezone(UTC) if first_response else None,
                )
                for created, first_response in connection.execute(
                    """SELECT created_at, first_response_at FROM issues
                       WHERE repo_id = %s AND created_at < %s ORDER BY created_at, id""",
                    (repo_id, cutoff),
                ).fetchall()
            ]
            reviews = [
                ReviewEvent(
                    int(pr_id),
                    pr_created.astimezone(UTC),
                    submitted.astimezone(UTC) if submitted else None,
                )
                for pr_id, pr_created, submitted in connection.execute(
                    """SELECT pr.id, pr.created_at, review.submitted_at
                       FROM pull_requests pr
                       LEFT JOIN reviews review ON review.pull_request_id = pr.id
                       WHERE pr.repo_id = %s AND pr.created_at < %s
                       ORDER BY pr.created_at, pr.id, review.submitted_at""",
                    (repo_id, cutoff),
                ).fetchall()
            ]
            for snapshot_id, _, prediction_date, label_status, split, size_group in repo_snapshots:
                result = compute_features(commits, pull_requests, issues, reviews, prediction_date)
                computed.append(
                    {
                        "snapshot_id": int(snapshot_id),
                        "repo_id": repo_id,
                        "prediction_date": prediction_date,
                        "label_status": label_status,
                        "split": split,
                        "size_group": size_group,
                        "features": result.features,
                        "missing_flags": result.missing_flags,
                        "completeness": result.completeness,
                    }
                )

        summary = _summary(computed)
        summary["source_dataset_version_id"] = version_id
        summary["source_dataset_hash"] = dataset_hash
        connection.execute(
            """INSERT INTO feature_sets
                   (dataset_version_id, feature_set_hash, code_revision, config, summary)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (dataset_version_id, feature_set_hash) DO NOTHING""",
            (
                version_id,
                feature_set_hash,
                code_revision,
                Jsonb(feature_definition),
                Jsonb(summary),
            ),
        )
        feature_set_row = connection.execute(
            "SELECT id, dataset_version_id FROM feature_sets "
            "WHERE dataset_version_id = %s AND feature_set_hash = %s",
            (version_id, feature_set_hash),
        ).fetchone()
        if feature_set_row is None or int(feature_set_row[1]) != version_id:
            raise ValueError("Feature-set hash is already associated with a different dataset")
        feature_set_id = int(feature_set_row[0])
        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO feature_definitions
                       (feature_set_id, feature_name, feature_group, description,
                        time_window, missing_policy)
                   VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                [
                    (
                        feature_set_id,
                        item["feature_name"],
                        item["feature_group"],
                        item["description"],
                        item["time_window"],
                        item["missing_policy"],
                    )
                    for item in FEATURE_DEFINITIONS
                ],
            )
            cursor.executemany(
                """INSERT INTO snapshot_features
                       (snapshot_id, dataset_version_id, feature_set_id, features, missing_flags)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (snapshot_id, feature_set_id) DO NOTHING""",
                [
                    (
                        item["snapshot_id"],
                        version_id,
                        feature_set_id,
                        Jsonb(item["features"]),
                        Jsonb(item["missing_flags"]),
                    )
                    for item in computed
                ],
            )
            cursor.executemany(
                """INSERT INTO repository_metrics_monthly
                       (snapshot_id, feature_set_id, prediction_date, metrics, completeness)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (snapshot_id, feature_set_id) DO NOTHING""",
                [
                    (
                        item["snapshot_id"],
                        feature_set_id,
                        item["prediction_date"],
                        Jsonb(_display_metrics(item["features"])),
                        Jsonb(item["completeness"]),
                    )
                    for item in computed
                ],
            )
        definitions = connection.execute(
            "SELECT feature_name, feature_group, description, time_window, missing_policy "
            "FROM feature_definitions WHERE feature_set_id = %s",
            (feature_set_id,),
        ).fetchall()
        if len(definitions) != len(FEATURE_DEFINITIONS):
            raise ValueError("Registered feature dictionary does not match this feature set")
        feature_rows = connection.execute(
            """SELECT snapshot_id, features, missing_flags FROM snapshot_features
               WHERE feature_set_id = %s""",
            (feature_set_id,),
        ).fetchall()
        expected = {
            item["snapshot_id"]: (item["features"], item["missing_flags"]) for item in computed
        }
        actual = {
            int(snapshot_id): (features, missing) for snapshot_id, features, missing in feature_rows
        }
        if actual != expected:
            raise ValueError(
                "Stored features differ from their content-addressed input; refusing overwrite"
            )
        monthly_rows = connection.execute(
            """SELECT snapshot_id, prediction_date, metrics, completeness
               FROM repository_metrics_monthly WHERE feature_set_id = %s""",
            (feature_set_id,),
        ).fetchall()
        expected_monthly = {
            item["snapshot_id"]: (
                item["prediction_date"],
                _display_metrics(item["features"]),
                item["completeness"],
            )
            for item in computed
        }
        actual_monthly = {
            int(snapshot_id): (prediction_date, metrics, completeness)
            for snapshot_id, prediction_date, metrics, completeness in monthly_rows
        }
        if actual_monthly != expected_monthly:
            raise ValueError(
                "Stored display metrics differ from their feature set; refusing overwrite"
            )

    report = {
        "feature_set_id": feature_set_id,
        "feature_set_hash": feature_set_hash,
        "code_revision": code_revision,
        "config": feature_definition,
        **summary,
        "feature_dictionary": [
            dict(
                zip(
                    (
                        "feature_name",
                        "feature_group",
                        "description",
                        "time_window",
                        "missing_policy",
                    ),
                    row,
                    strict=True,
                )
            )
            for row in definitions
        ],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

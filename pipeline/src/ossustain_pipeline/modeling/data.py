"""Read only labeled, assigned snapshots and their registered feature values."""

from dataclasses import dataclass
from datetime import date
from math import isfinite, nan
from typing import Any

import psycopg

ALLOWED_SPLITS = ("train", "validation", "test")
ACTIVITY_FEATURES = ("commits_30d", "commits_90d", "commits_180d")


@dataclass(frozen=True)
class ModelRow:
    snapshot_id: int
    repo_id: int
    prediction_date: date
    split: str
    size_group: str
    label: int
    features: dict[str, float]


@dataclass(frozen=True)
class ModelDataset:
    dataset_version_id: int
    dataset_hash: str
    feature_set_id: int
    feature_set_hash: str
    label_config: dict[str, Any]
    rows: tuple[ModelRow, ...]
    feature_names: tuple[str, ...]


@dataclass(frozen=True)
class RobustnessOutcome:
    snapshot_id: int
    repo_id: int
    reference_activity: int
    future_activity: int
    combined_reference_activity: int
    combined_future_activity: int


def load_test_robustness_outcomes(
    connection: psycopg.Connection[Any], dataset_version_id: int
) -> tuple[RobustnessOutcome, ...]:
    """Load held-out outcomes for sensitivity checks, including merged-PR activity."""
    rows = connection.execute(
        """SELECT snapshot.id, snapshot.repo_id, snapshot.reference_activity,
                  snapshot.future_activity,
                  reference_commits.activity + reference_prs.activity,
                  future_commits.activity + future_prs.activity
           FROM snapshots snapshot
           CROSS JOIN LATERAL (
               SELECT count(*)::integer AS activity
               FROM commits commit
               LEFT JOIN contributors author ON author.id = commit.contributor_id
               WHERE commit.repo_id = snapshot.repo_id
                 AND commit.committed_at >= (snapshot.reference_start::timestamp AT TIME ZONE 'UTC')
                 AND commit.committed_at < (snapshot.prediction_date::timestamp AT TIME ZONE 'UTC')
                 AND author.is_bot IS DISTINCT FROM TRUE
           ) reference_commits
           CROSS JOIN LATERAL (
               SELECT count(*)::integer AS activity
               FROM pull_requests request
               WHERE request.repo_id = snapshot.repo_id
                 AND request.merged_at >= (snapshot.reference_start::timestamp AT TIME ZONE 'UTC')
                 AND request.merged_at < (snapshot.prediction_date::timestamp AT TIME ZONE 'UTC')
           ) reference_prs
           CROSS JOIN LATERAL (
               SELECT count(*)::integer AS activity
               FROM commits commit
               LEFT JOIN contributors author ON author.id = commit.contributor_id
               WHERE commit.repo_id = snapshot.repo_id
                 AND commit.committed_at >= (snapshot.prediction_date::timestamp AT TIME ZONE 'UTC')
                 AND commit.committed_at < (snapshot.future_end::timestamp AT TIME ZONE 'UTC')
                 AND author.is_bot IS DISTINCT FROM TRUE
           ) future_commits
           CROSS JOIN LATERAL (
               SELECT count(*)::integer AS activity
               FROM pull_requests request
               WHERE request.repo_id = snapshot.repo_id
                 AND request.merged_at >= (snapshot.prediction_date::timestamp AT TIME ZONE 'UTC')
                 AND request.merged_at < (snapshot.future_end::timestamp AT TIME ZONE 'UTC')
           ) future_prs
           WHERE snapshot.dataset_version_id = %s
             AND snapshot.split = 'test'
             AND snapshot.label_status = 'labeled'
             AND snapshot.label IS NOT NULL
           ORDER BY snapshot.prediction_date, snapshot.repo_id, snapshot.id""",
        (dataset_version_id,),
    ).fetchall()
    return tuple(
        RobustnessOutcome(
            int(snapshot_id), int(repo_id), int(reference), int(future),
            int(combined_reference), int(combined_future),
        )
        for snapshot_id, repo_id, reference, future, combined_reference, combined_future in rows
    )


def validate_split_chronology(rows: list[ModelRow]) -> None:
    """Require non-empty, strictly ordered train, validation, and test periods."""
    split_dates = {
        name: [row.prediction_date for row in rows if row.split == name] for name in ALLOWED_SPLITS
    }
    if any(not split_dates[name] for name in ALLOWED_SPLITS):
        raise ValueError("Modeling requires labeled rows in train, validation, and test")
    if not (
        max(split_dates["train"]) < min(split_dates["validation"])
        and max(split_dates["validation"]) < min(split_dates["test"])
    ):
        raise ValueError("Modeling rows do not follow strict chronological split order")


def load_model_dataset(
    connection: psycopg.Connection[Any],
    *,
    dataset_version_id: int | None = None,
    feature_set_id: int | None = None,
) -> ModelDataset:
    """Load only eligible rows; future-window fields are never selected."""
    if feature_set_id is not None:
        feature_set = connection.execute(
            """SELECT feature_set.id, feature_set.dataset_version_id,
                      feature_set.feature_set_hash, dataset.version_hash, dataset.config
               FROM feature_sets feature_set
               JOIN dataset_versions dataset ON dataset.id = feature_set.dataset_version_id
               WHERE feature_set.id = %s""",
            (feature_set_id,),
        ).fetchone()
        if feature_set is None:
            raise ValueError(f"Feature set {feature_set_id} does not exist")
        if dataset_version_id is not None and int(feature_set[1]) != dataset_version_id:
            raise ValueError("Feature set does not belong to the requested dataset version")
    elif dataset_version_id is not None:
        feature_set = connection.execute(
            """SELECT feature_set.id, feature_set.dataset_version_id,
                      feature_set.feature_set_hash, dataset.version_hash, dataset.config
               FROM feature_sets feature_set
               JOIN dataset_versions dataset ON dataset.id = feature_set.dataset_version_id
               WHERE feature_set.dataset_version_id = %s
               ORDER BY feature_set.created_at DESC, feature_set.id DESC LIMIT 1""",
            (dataset_version_id,),
        ).fetchone()
        if feature_set is None:
            raise ValueError("No Phase 6 feature set exists for the requested dataset")
    else:
        feature_set = connection.execute(
            """SELECT feature_set.id, feature_set.dataset_version_id,
                      feature_set.feature_set_hash, dataset.version_hash, dataset.config
               FROM feature_sets feature_set
               JOIN dataset_versions dataset ON dataset.id = feature_set.dataset_version_id
               ORDER BY feature_set.created_at DESC, feature_set.id DESC LIMIT 1"""
        ).fetchone()
        if feature_set is None:
            raise ValueError("No Phase 6 feature set exists; run build-features first")

    selected_feature_names = connection.execute(
        "SELECT feature_name FROM feature_definitions "
        "WHERE feature_set_id = %s ORDER BY feature_name",
        (int(feature_set[0]),),
    ).fetchall()
    feature_names = tuple(row[0] for row in selected_feature_names)
    if not set(ACTIVITY_FEATURES).issubset(feature_names):
        raise ValueError("Registered feature dictionary is missing required activity features")

    stored_rows = connection.execute(
        """SELECT snapshot.id, snapshot.repo_id, snapshot.prediction_date, snapshot.split,
                  repository.size_group, snapshot.label, snapshot_features.features
           FROM snapshots snapshot
           JOIN repositories repository ON repository.id = snapshot.repo_id
           JOIN snapshot_features
             ON snapshot_features.snapshot_id = snapshot.id
            AND snapshot_features.dataset_version_id = snapshot.dataset_version_id
           WHERE snapshot.dataset_version_id = %s
             AND snapshot_features.feature_set_id = %s
             AND snapshot.label_status = 'labeled'
             AND snapshot.label IS NOT NULL
             AND snapshot.split = ANY(%s)
           ORDER BY snapshot.prediction_date, snapshot.repo_id, snapshot.id""",
        (int(feature_set[1]), int(feature_set[0]), list(ALLOWED_SPLITS)),
    ).fetchall()
    rows = []
    for (
        snapshot_id,
        repo_id,
        prediction_date,
        split,
        size_group,
        label,
        raw_features,
    ) in stored_rows:
        if label is None or split not in ALLOWED_SPLITS:
            raise ValueError("Invalid label or split returned for modeling row")
        if set(raw_features) != set(feature_names):
            raise ValueError(f"Snapshot {snapshot_id} feature values do not match the dictionary")
        values: dict[str, float] = {}
        for name in feature_names:
            value = raw_features[name]
            if value is None:
                values[name] = nan
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Feature {name} on snapshot {snapshot_id} is not numeric")
            elif not isfinite(float(value)):
                raise ValueError(f"Feature {name} on snapshot {snapshot_id} is not finite")
            else:
                values[name] = float(value)
        rows.append(
            ModelRow(
                int(snapshot_id),
                int(repo_id),
                prediction_date,
                split,
                size_group,
                int(label),
                values,
            )
        )
    if not rows:
        raise ValueError("No eligible labeled train, validation, or test rows exist")
    validate_split_chronology(rows)

    dataset_config = feature_set[4]
    label_config = dataset_config["experiment"]["label"]
    return ModelDataset(
        int(feature_set[1]),
        str(feature_set[3]),
        int(feature_set[0]),
        str(feature_set[2]),
        label_config,
        tuple(rows),
        feature_names,
    )

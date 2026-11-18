"""Opt-in acceptance against a migrated, collected local database; no GitHub requests."""

import os
from pathlib import Path

import pytest

from ossustain_pipeline.collect.models import load_cohort
from ossustain_pipeline.config import load_config
from ossustain_pipeline.db import connect
from ossustain_pipeline.experiment import load_experiment_config
from ossustain_pipeline.snapshots.runner import build_snapshots


@pytest.mark.skipif(
    os.environ.get("OSSUSTAIN_TEST_SNAPSHOTS") != "1",
    reason="Set OSSUSTAIN_TEST_SNAPSHOTS=1 for the local collected database",
)
def test_database_rerun_preserves_version_snapshot_ids_and_labels(tmp_path):
    cohort = load_cohort(Path("config/cohort.yaml"))
    experiment = load_experiment_config(Path("config/experiment.yaml"))
    with connect(load_config(Path("pipeline/config.example.yaml"))) as connection:

        def run():
            return build_snapshots(
                connection,
                cohort,
                experiment,
                quality_report=Path("pipeline/data/reports/phase4-validation.json"),
                report_path=tmp_path / "snapshots.json",
            )

        first = run()
        query = "SELECT * FROM snapshots WHERE dataset_version_id = %s ORDER BY id"
        before = connection.execute(query, (first["dataset_version_id"],)).fetchall()
        second = run()
        assert first == second
        assert connection.execute(query, (first["dataset_version_id"],)).fetchall() == before
        assert len(before) == first["overall"]["snapshots"]
        invalid = connection.execute(
            """SELECT count(*) FROM snapshots WHERE dataset_version_id = %s
               AND label IS NOT NULL
               AND (future_end > observed_until OR future_activity IS NULL)""",
            (first["dataset_version_id"],),
        ).fetchone()[0]
        assert invalid == 0

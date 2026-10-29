from datetime import date
from pathlib import Path

import pytest
import yaml

from ossustain_pipeline.experiment import ExperimentConfig, load_experiment_config


def _experiment_values() -> dict[str, object]:
    return {
        "protocol_version": "1.0.0",
        "selection_date": "2026-10-29",
        "observation_start": "2022-01-01",
        "observation_end": "2025-12-31",
        "snapshot_interval_days": 30,
        "purge_gap_days": 90,
        "random_seed": 42,
        "label": {
            "theta": 0.5,
            "sensitivity_theta": [0.3, 0.7],
            "min_reference_commits": 20,
            "reference_window_days": 90,
            "future_window_days": 90,
            "activity_definition": "non_bot_default_branch_commits",
        },
        "identity": {
            "exclude_github_type_bot": True,
            "exclude_login_suffix": "[bot]",
            "unlinked_author_policy": "retain_as_null",
            "identity_key": "github_user_id",
        },
        "splits": {
            "train": {"start": "2022-04-01", "end": "2023-06-30"},
            "validation": {"start": "2023-10-01", "end": "2024-06-30"},
            "test": {"start": "2024-10-01", "end": "2025-09-30"},
        },
    }


def test_load_experiment_config_validates_protocol(tmp_path) -> None:
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(_experiment_values()), encoding="utf-8")

    config = load_experiment_config(path)

    assert config.label.theta == 0.5
    assert config.label.min_reference_commits == 20
    assert config.splits["test"].end == date(2025, 9, 30)


def test_experiment_rejects_split_gap_shorter_than_purge_gap() -> None:
    values = _experiment_values()
    values["splits"]["validation"]["start"] = "2023-09-27"  # type: ignore[index]

    with pytest.raises(ValueError, match="train/validation split gap"):
        ExperimentConfig.model_validate(values)


def test_experiment_rejects_test_future_window_outside_observation() -> None:
    values = _experiment_values()
    values["splits"]["test"]["end"] = "2025-10-03"  # type: ignore[index]

    with pytest.raises(ValueError, match="future-label windows"):
        ExperimentConfig.model_validate(values)


def test_checked_in_experiment_config_is_valid() -> None:
    config = load_experiment_config(Path(__file__).parents[2] / "config" / "experiment.yaml")

    assert config.protocol_version == "1.0.0"
    assert config.label.sensitivity_theta == (0.3, 0.7)

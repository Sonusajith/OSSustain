from datetime import date
from pathlib import Path

import pytest
import yaml

from ossustain_pipeline.cohort import (
    CandidateFile,
    CandidateRepository,
    CohortCriteria,
    SizeBand,
    select_cohort,
    select_repositories,
)


def _candidate(github_id: int, stars: int, prs: int = 50) -> CandidateRepository:
    return CandidateRepository(
        github_id=github_id,
        full_name=f"owner/repo-{github_id}",
        default_branch="main",
        created_at=date(2018, 1, 1),
        pushed_at=date(2026, 10, 1),
        stars=stars,
        primary_language="Python",
        archived=False,
        fork=False,
        prs_in_observation_period=prs,
    )


def _candidate_file() -> CandidateFile:
    candidates = [
        *[_candidate(i + 1, 900 - i, i + 1) for i in range(17)],
        *[_candidate(i + 101, 9000 - i, i + 1) for i in range(17)],
        *[_candidate(i + 201, 40_000 - i, i + 1) for i in range(16)],
    ]
    criteria = CohortCriteria(
        selection_date=date(2026, 10, 29),
        observation_start=date(2022, 1, 1),
        observation_end=date(2025, 12, 31),
        created_before=date(2022, 1, 1),
        pushed_within_days=365,
        max_prs_in_observation_period=100,
        random_seed=42,
        size_groups={
            "small": SizeBand(min_stars=100, max_stars=999, target_size=17),
            "medium": SizeBand(min_stars=1000, max_stars=9999, target_size=17),
            "large": SizeBand(min_stars=10_000, max_stars=50_000, target_size=16),
        },
    )
    return CandidateFile(screen_id="test-screen", criteria=criteria, candidates=candidates)


def test_selection_is_deterministic_and_stratified() -> None:
    candidate_file = _candidate_file()

    first = select_repositories(candidate_file)
    reversed_file = candidate_file.model_copy(
        update={"candidates": list(reversed(candidate_file.candidates))}
    )
    second = select_repositories(reversed_file)

    assert first == second
    assert len(first) == 50
    counts = {
        group: sum(row["size_group"] == group for row in first)
        for group in ("small", "medium", "large")
    }
    assert counts == {
        "small": 17,
        "medium": 17,
        "large": 16,
    }


def test_selection_rejects_short_stratum_instead_of_returning_partial_cohort() -> None:
    candidate_file = _candidate_file()
    candidate_file.candidates = [
        candidate for candidate in candidate_file.candidates if candidate.stars >= 1000
    ]

    with pytest.raises(ValueError, match="small: need 17, found 0"):
        select_repositories(candidate_file)


def test_selection_applies_archive_fork_recency_and_pr_filters() -> None:
    candidate_file = _candidate_file()
    candidate_file.candidates[0].archived = True
    candidate_file.candidates[1].fork = True
    candidate_file.candidates[2].pushed_at = date(2025, 1, 1)
    candidate_file.candidates[3].prs_in_observation_period = 101

    with pytest.raises(ValueError, match="small: need 17, found 13"):
        select_repositories(candidate_file)


def test_select_cohort_writes_reproducible_yaml(tmp_path) -> None:
    candidate_file = _candidate_file()
    candidate_path = tmp_path / "candidates.yaml"
    output_path = tmp_path / "cohort.yaml"
    candidate_path.write_text(
        yaml.safe_dump(candidate_file.model_dump(mode="json")), encoding="utf-8"
    )

    first = select_cohort(candidate_path, output_path)
    first_output = output_path.read_text(encoding="utf-8")
    second = select_cohort(candidate_path, output_path)

    assert len(first) == 50
    assert first == second
    assert first_output == output_path.read_text(encoding="utf-8")
    assert len(yaml.safe_load(first_output)["repositories"]) == 50


def test_checked_in_cohort_is_complete_and_deterministic(tmp_path) -> None:
    project_root = Path(__file__).parents[2]
    candidate_path = project_root / "config" / "cohort-candidates.yaml"
    committed_cohort = yaml.safe_load(
        (project_root / "config" / "cohort.yaml").read_text(encoding="utf-8")
    )
    output_path = tmp_path / "cohort.yaml"

    selected = select_cohort(candidate_path, output_path)
    generated = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    groups = {group: sum(row["size_group"] == group for row in selected)
              for group in ("small", "medium", "large")}

    assert len(selected) == 50
    assert groups == {"small": 17, "medium": 17, "large": 16}
    assert generated["repositories"] == committed_cohort["repositories"]

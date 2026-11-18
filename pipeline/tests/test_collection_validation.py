import json
from pathlib import Path

from ossustain_pipeline.collect.models import CohortSelection, SelectedRepository
from ossustain_pipeline.collect.validation import build_quality_report


class FakeStore:
    def __init__(self) -> None:
        self.stages = {"pull_requests": True, "reviews": True, "issues": True}

    def repository_id_for_github_id(self, github_id):
        return 7

    def stage_completed(self, repository_id, stage):
        return self.stages[stage]

    def collaboration_counts(self, repository_id, start, end):
        return {
            "pull_requests": 2,
            "pr_responses": 1,
            "reviews": 3,
            "issues": 4,
            "issue_responses": 2,
        }

    def count_repository_commits(self, repository_id):
        return 55


def test_quality_report_flags_screen_count_mismatch_and_reports_missingness(tmp_path: Path) -> None:
    cohort = CohortSelection(
        cohort_name="fixture",
        screen_id="fixture-screen",
        criteria={
            "selection_date": "2026-10-29",
            "observation_start": "2022-01-01",
            "observation_end": "2025-12-31",
        },
        repositories=[
            SelectedRepository(
                github_id=50,
                full_name="sample/project",
                default_branch="main",
                created_at="2020-01-01",
                stars=500,
                primary_language="Python",
                archived=False,
                fork=False,
                size_group="small",
                prs_in_observation_period=3,
            )
        ],
    )
    screen_path = tmp_path / "issues.json"
    screen_path.write_text(
        json.dumps({"repositories": [{"github_id": 50, "issue_count": 4}]}),
        encoding="utf-8",
    )

    report = build_quality_report(
        cohort,
        FakeStore(),
        report_path=tmp_path / "quality.json",
        issue_screen_path=screen_path,
    )

    row = report["repositories"][0]
    assert row["commits"] == 55
    assert row["pr_first_response_missing_rate"] == 0.5
    assert row["issue_first_response_missing_rate"] == 0.5
    assert "pull_request_count_differs_from_screen" in row["quality_flags"]
    assert row["issue_count_matches_screen"] is True
    assert report["repositories_flagged"] == 1

"""Build a per-repository Phase 4 completeness and missingness report."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from ossustain_pipeline.collect.models import CohortSelection
from ossustain_pipeline.collect.store import PostgresCollectionStore


def _expected_issue_counts(path: Path | None) -> dict[int, int]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(row["github_id"]): int(row["issue_count"])
        for row in data.get("repositories", [])
        if isinstance(row.get("github_id"), int) and isinstance(row.get("issue_count"), int)
    }


def build_quality_report(
    cohort: CohortSelection,
    store: PostgresCollectionStore,
    *,
    report_path: Path,
    issue_screen_path: Path | None = None,
) -> dict[str, Any]:
    observation_start = date.fromisoformat(str(cohort.criteria["observation_start"]))
    observation_end = date.fromisoformat(str(cohort.criteria["observation_end"]))
    expected_issues = _expected_issue_counts(issue_screen_path)
    repositories: list[dict[str, Any]] = []

    for selected in cohort.repositories:
        repository_id = store.repository_id_for_github_id(selected.github_id)
        stages = {
            "pull_requests": False,
            "reviews": False,
            "issues": False,
        }
        counts = {
            "pull_requests": 0,
            "pr_responses": 0,
            "reviews": 0,
            "issues": 0,
            "issue_responses": 0,
        }
        commits = 0
        if repository_id is not None:
            stages = {
                stage: store.stage_completed(repository_id, stage)
                for stage in stages
            }
            counts = store.collaboration_counts(repository_id, observation_start, observation_end)
            commits = store.count_repository_commits(repository_id)

        expected_issue_count = expected_issues.get(selected.github_id)
        flags: list[str] = []
        if repository_id is None:
            flags.append("repository_not_registered")
        for stage, complete in stages.items():
            if not complete:
                flags.append(f"{stage}_collection_incomplete")
        if (
            selected.prs_in_observation_period is not None
            and counts["pull_requests"] != selected.prs_in_observation_period
        ):
            flags.append("pull_request_count_differs_from_screen")
        if expected_issue_count is not None and counts["issues"] != expected_issue_count:
            flags.append("issue_count_differs_from_screen")
        if counts["pull_requests"] == 0 and counts["issues"] == 0:
            flags.append("no_collaboration_events")

        pr_missing = counts["pull_requests"] - counts["pr_responses"]
        issue_missing = counts["issues"] - counts["issue_responses"]
        repositories.append(
            {
                "github_id": selected.github_id,
                "full_name": selected.full_name,
                "size_group": selected.size_group,
                "commits": commits,
                "stages_complete": stages,
                "pull_requests": counts["pull_requests"],
                "expected_pull_requests": selected.prs_in_observation_period,
                "pr_count_matches_screen": (
                    None
                    if selected.prs_in_observation_period is None
                    else counts["pull_requests"] == selected.prs_in_observation_period
                ),
                "reviews": counts["reviews"],
                "issues": counts["issues"],
                "expected_issues": expected_issue_count,
                "issue_count_matches_screen": (
                    None
                    if expected_issue_count is None
                    else counts["issues"] == expected_issue_count
                ),
                "pr_first_response_missing": pr_missing,
                "pr_first_response_missing_rate": (
                    pr_missing / counts["pull_requests"]
                    if counts["pull_requests"]
                    else None
                ),
                "issue_first_response_missing": issue_missing,
                "issue_first_response_missing_rate": (
                    issue_missing / counts["issues"] if counts["issues"] else None
                ),
                "quality_flags": flags,
                "insufficient_collaboration_data": bool(flags),
            }
        )

    report = {
        "cohort_name": cohort.cohort_name,
        "cohort_config_hash": cohort.config_hash,
        "observation_start": observation_start.isoformat(),
        "observation_end": observation_end.isoformat(),
        "repositories_expected": len(cohort.repositories),
        "repositories_complete": sum(
            all(row["stages_complete"].values()) and not row["quality_flags"]
            for row in repositories
        ),
        "repositories_flagged": sum(bool(row["quality_flags"]) for row in repositories),
        "total_commits": sum(row["commits"] for row in repositories),
        "total_pull_requests": sum(row["pull_requests"] for row in repositories),
        "total_reviews": sum(row["reviews"] for row in repositories),
        "total_issues": sum(row["issues"] for row in repositories),
        "total_pr_first_responses_missing": sum(
            row["pr_first_response_missing"] for row in repositories
        ),
        "total_issue_first_responses_missing": sum(
            row["issue_first_response_missing"] for row in repositories
        ),
        "repositories": repositories,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from ossustain_pipeline.collect.models import CohortSelection, SelectedRepository
from ossustain_pipeline.collect.runner import run_collection
from ossustain_pipeline.github.client import ApiPage


class FakeClient:
    def __init__(self) -> None:
        self.requests_made = 0
        self.commit_page_calls: list[int] = []
        self.fail_page_two_once = True

    def get_json(self, url, *, transform=None):
        self.requests_made += 1
        if "/commits?" not in url:
            metadata = {
                "id": 50,
                "full_name": "sample/project",
                "name": "project",
                "default_branch": "main",
                "created_at": "2020-01-01T00:00:00Z",
                "stargazers_count": 500,
                "language": "Python",
                "archived": False,
                "fork": False,
            }
            return ApiPage(body=transform(metadata), next_url=None)

        page_number = int(parse_qs(urlparse(url).query)["page"][0])
        self.commit_page_calls.append(page_number)
        if page_number == 2 and self.fail_page_two_once:
            self.fail_page_two_once = False
            raise RuntimeError("simulated interruption")
        raw_commit = {
            "sha": f"sha-{page_number}",
            "author": {"id": 900 + page_number, "login": f"user-{page_number}", "type": "User"},
            "commit": {"author": {"date": f"2024-01-0{page_number}T00:00:00Z"}},
        }
        next_url = None
        if page_number == 1:
            parts = urlparse(url)
            query = parse_qs(parts.query)
            query["page"] = ["2"]
            next_url = urlunparse(parts._replace(query=urlencode(query, doseq=True)))
        return ApiPage(body=transform([raw_commit]), next_url=next_url)


class FakeStore:
    def __init__(self) -> None:
        self.progress = None
        self.saved_commits = {}
        self.run_statuses = []

    def ensure_cohort(self, cohort):
        return 1

    def upsert_selected_repository(self, *args):
        return 20

    def update_repository_metadata(self, *args):
        return None

    def start_run(self, repository_id, stage):
        return len(self.run_statuses) + 1

    def finish_run(self, run_id, *, status, requests_used, records_processed, error_summary):
        self.run_statuses.append((status, requests_used, records_processed, error_summary))

    def begin_commit_progress(self, repository_id, initial_cursor, *, refresh):
        if self.progress and self.progress["status"] == "done" and not refresh:
            return None
        if self.progress and self.progress["cursor"] and not refresh:
            self.progress["status"] = "running"
            return dict(self.progress)
        self.progress = {
            "cursor": initial_cursor,
            "last_page": 0,
            "status": "running",
            "requests_used": 0,
        }
        return dict(self.progress)

    def save_commit_page(
        self,
        repository_id,
        commits,
        *,
        next_cursor,
        page_number,
        requests_used,
    ):
        for commit in commits:
            self.saved_commits[commit["sha"]] = commit
        self.progress.update(
            cursor=next_cursor,
            last_page=page_number,
            status="done" if next_cursor is None else "running",
            requests_used=self.progress["requests_used"] + requests_used,
        )

    def fail_commit_progress(self, repository_id, requests_used):
        self.progress["status"] = "failed"
        self.progress["requests_used"] += requests_used

    def finish_empty_commit_collection(self, repository_id, requests_used):
        self.progress.update(cursor=None, last_page=0, status="done")
        self.progress["requests_used"] += requests_used


def _cohort() -> CohortSelection:
    return CohortSelection(
        cohort_name="test-cohort",
        screen_id="fixture-screen",
        criteria={"selection_date": "2026-10-29"},
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
            )
        ],
    )


def test_interrupted_collection_resumes_from_last_saved_page_and_is_idempotent(
    tmp_path: Path,
) -> None:
    cohort = _cohort()
    client = FakeClient()
    store = FakeStore()
    started = datetime(2026, 11, 1, tzinfo=UTC)

    first_report = run_collection(
        cohort,
        client,
        store,
        hash_secret="a-stable-secret-with-at-least-32-characters",
        report_path=tmp_path / "first.json",
        now=started,
    )

    assert first_report["repositories_failed"] == 1
    assert store.progress["status"] == "failed"
    assert "page=2" in store.progress["cursor"]
    assert set(store.saved_commits) == {"sha-1"}

    second_report = run_collection(
        cohort,
        client,
        store,
        hash_secret="a-stable-secret-with-at-least-32-characters",
        report_path=tmp_path / "second.json",
        now=started,
    )

    assert second_report["repositories_succeeded"] == 1
    assert store.progress["status"] == "done"
    assert client.commit_page_calls == [1, 2, 2]
    assert set(store.saved_commits) == {"sha-1", "sha-2"}

    third_report = run_collection(
        cohort,
        client,
        store,
        hash_secret="a-stable-secret-with-at-least-32-characters",
        report_path=tmp_path / "third.json",
        now=started,
    )

    assert third_report["repositories_succeeded"] == 1
    assert third_report["repositories"][0]["commit_status"] == "already_done"
    assert client.commit_page_calls == [1, 2, 2]
    assert len(store.saved_commits) == 2

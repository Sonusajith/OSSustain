import json

from ossustain_pipeline.collect.models import (
    contributor_identity,
    redact_commit_page,
    redact_repository_metadata,
)


def test_contributor_key_is_stable_hashed_and_marks_bots() -> None:
    user = {"id": 10001, "login": "octocat", "type": "User"}

    first = contributor_identity(user, "a-stable-secret-with-at-least-32-characters")
    second = contributor_identity(user, "a-stable-secret-with-at-least-32-characters")
    bot = contributor_identity(
        {"id": 10002, "login": "build[bot]", "type": "Bot"},
        "a-stable-secret-with-at-least-32-characters",
    )

    assert first == second
    assert len(first["contributor_key"]) == 64
    assert first["contributor_key"] != "10001"
    assert first["is_bot"] is False
    assert bot["is_bot"] is True
    assert contributor_identity(None, "secret") is None
    assert contributor_identity({"id": None, "login": "ghost"}, "secret") is None


def test_commit_cache_redacts_names_logins_and_emails() -> None:
    payload = [
        {
            "sha": "a1b2c3",
            "author": {"id": 10001, "login": "private-login", "type": "User"},
            "committer": {"id": 20002, "login": "other-login", "type": "User"},
            "commit": {
                "author": {
                    "name": "Private Person",
                    "email": "person@example.com",
                    "date": "2024-01-01T00:00:00Z",
                },
                "committer": {
                    "name": "Commit Bot",
                    "email": "bot@example.com",
                    "date": "2024-01-01T00:00:00Z",
                },
                "message": "Private Person made a commit",
            },
        },
        {
            "sha": "d4e5f6",
            "author": None,
            "commit": {"author": {"date": "2024-01-02T00:00:00Z"}},
        },
    ]

    redacted = redact_commit_page(payload, "a-stable-secret-with-at-least-32-characters")
    serialized = json.dumps(redacted)

    assert redacted[0]["author"]["contributor_key"]
    assert redacted[1]["author"] is None
    assert "Private Person" not in serialized
    assert "person@example.com" not in serialized
    assert "private-login" not in serialized
    assert "other-login" not in serialized
    assert "10001" not in serialized


def test_repository_cache_keeps_only_collection_metadata() -> None:
    metadata = redact_repository_metadata(
        {
            "id": 42,
            "full_name": "owner/repository",
            "name": "repository",
            "default_branch": "main",
            "created_at": "2020-01-01T00:00:00Z",
            "stargazers_count": 100,
            "language": "Python",
            "archived": False,
            "fork": False,
            "owner": {"id": 9001, "login": "owner-login"},
        }
    )

    assert metadata["full_name"] == "owner/repository"
    assert "owner" not in metadata

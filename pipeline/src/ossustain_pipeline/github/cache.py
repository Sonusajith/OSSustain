"""Atomic disk cache for privacy-filtered GitHub JSON responses."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CachedResponse:
    body: Any
    etag: str | None
    link: str | None


class JsonResponseCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path_for(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.directory / f"{key}.json"

    def read(self, url: str) -> CachedResponse | None:
        path = self._path_for(url)
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read GitHub response cache entry: {path}") from error
        return CachedResponse(
            body=content["body"],
            etag=content.get("etag"),
            link=content.get("link"),
        )

    def write(self, url: str, response: CachedResponse) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path_for(url)
        content = json.dumps(
            {"body": response.body, "etag": response.etag, "link": response.link},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f"{path.stem}.", suffix=".tmp", dir=self.directory
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            Path(temporary_path).replace(path)
        except OSError:
            Path(temporary_path).unlink(missing_ok=True)
            raise

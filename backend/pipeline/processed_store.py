"""
Persistent store of processed Qualtrics response IDs for duplicate detection.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_processed_ids(path: Path) -> set[str]:
    """Load set of processed response IDs from file. Missing/corrupt file => empty set."""
    if not path.exists():
        return set()
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict) and "ids" in data:
            return set(data["ids"])
        return set()
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Processed IDs store unreadable (%s), treating as empty: %s", path, e)
        return set()


def save_processed_ids(path: Path, ids: set[str]) -> None:
    """Write set of response IDs to file as JSON list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(ids), f, indent=0)


class ProcessedStore:
    """In-memory set of processed response IDs with load/save from a file."""

    def __init__(self, path: Path):
        self.path = path
        self._ids: set[str] = load_processed_ids(path)

    def contains(self, response_id: str) -> bool:
        return response_id in self._ids

    def add(self, response_id: str) -> None:
        self._ids.add(response_id)

    def save(self) -> None:
        save_processed_ids(self.path, self._ids)

    def __len__(self) -> int:
        return len(self._ids)

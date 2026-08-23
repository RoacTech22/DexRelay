from __future__ import annotations

import json
from pathlib import Path


class BadgesStorage:
    """Persists the current badge state to disk."""

    def __init__(self, path: str | Path = "data/badges.json") -> None:
        self.path = Path(path)

    def save(self, badges: dict) -> None:
        """Save the current badge state as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            json.dump(
                badges,
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")

from __future__ import annotations

import json
from pathlib import Path

from app.core import paths


class BadgesStorage:
    """Persists the current badge state to disk."""

    def __init__(self, path: str | Path | None = None) -> None:
        # Sin path explícito, resuelve data/badges.json relativo a
        # la carpeta del proyecto o del .exe empaquetado -- ver
        # app/core/paths.py.
        self.path = (
            Path(path) if path is not None else paths.path("data", "badges.json")
        )

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

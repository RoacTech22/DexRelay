from __future__ import annotations

import json
from pathlib import Path


class NuzlockeStorage:
    """Persists the current Nuzlocke run (roster + graveyard) to disk."""

    def __init__(self, path: str | Path = "data/nuzlocke.json") -> None:
        self.path = Path(path)

    def load(self) -> dict:
        """
        Load the current Nuzlocke run, or an empty one if no file
        exists yet (first run).
        """

        if not self.path.exists():
            return {
                "roster": [],
                "graveyard": [],
                "encounters": [],
                "pending_encounters": [],
            }

        with self.path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        data.setdefault("roster", [])
        data.setdefault("graveyard", [])
        data.setdefault("encounters", [])
        data.setdefault("pending_encounters", [])

        return data

    def save(self, data: dict) -> None:
        """Save the current Nuzlocke run as JSON."""

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")

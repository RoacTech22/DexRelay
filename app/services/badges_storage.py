from __future__ import annotations

from pathlib import Path

from app.core import paths
from app.core.atomic_write import write_json_atomic


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

        # Bloque 4.1 (23/09/2026): escritura atómica -- ver
        # app/core/atomic_write.py. Antes: open("w") + json.dump()
        # directo sobre el archivo final.
        write_json_atomic(self.path, badges)

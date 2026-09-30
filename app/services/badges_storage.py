from __future__ import annotations

from pathlib import Path

from app.core import paths
from app.core.atomic_write import write_json_atomic
from app.services.nuzlocke_storage import _GAME_STORAGE_SLUGS


class BadgesStorage:
    """Persists the current badge state to disk."""

    def __init__(self, path: str | Path | None = None) -> None:
        # Sin path explícito, resuelve data/badges.json relativo a
        # la carpeta del proyecto o del .exe empaquetado -- ver
        # app/core/paths.py.
        self.path = (
            Path(path) if path is not None else paths.path("data", "badges.json")
        )

    @classmethod
    def for_identity(
        cls,
        process_name: str,
        tid: int,
        sid: int,
        data_dir: str | Path | None = None,
    ) -> "BadgesStorage":
        """
        Bloque 5 (24/09/2026): un archivo de medallas por PARTIDA --
        `data/badges_<juego>_<tid>_<sid>.json`, mismo criterio que
        NuzlockeStorage.for_identity(). Antes había un solo
        `badges.json`, y con dos partidas se pisaban entre sí. No hay
        adopción del `badges.json` viejo: es una foto que se
        reescribe entera en cada cambio y nada lo lee de vuelta (las
        medallas se leen en vivo de memoria), así que no hay nada que
        rescatar; queda sin tocar.
        """

        slug = _GAME_STORAGE_SLUGS.get(process_name, process_name)

        base = (
            Path(data_dir)
            if data_dir is not None
            else paths.path("data")
        )

        return cls(base / f"badges_{slug}_{tid}_{sid}.json")

    def save(self, badges: dict) -> None:
        """Save the current badge state as JSON."""

        # Bloque 4.1 (23/09/2026): escritura atómica -- ver
        # app/core/atomic_write.py. Antes: open("w") + json.dump()
        # directo sobre el archivo final.
        write_json_atomic(self.path, badges)

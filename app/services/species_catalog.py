from __future__ import annotations

import json
from pathlib import Path

from app.services.pkhex.bridge import PKHeXBridge


class SpeciesCatalog:
    """
    Lista completa {id, name} de especies conocidas por PKHeX,
    para el buscador del panel de encuentros
    (panels/nuzlocke/app.js).

    Se resuelve UNA vez vía el bridge (acción 'species_list') y
    se cachea en memoria y en disco
    (data/species_cache.json) -- no tiene sentido volver a
    pedirle la lista completa al bridge en cada arranque de
    DexRelay, los nombres de especie no cambian.
    """

    def __init__(
        self,
        bridge=None,
        cache_path="data/species_cache.json",
    ):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        self.cache_path = Path(cache_path)
        self._species = None

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...]. Vacía si el
        bridge no está disponible y tampoco hay caché en disco
        -- nunca lanza, el buscador simplemente queda vacío en
        vez de romper el panel.
        """

        if self._species is not None:
            return self._species

        cached = self._load_from_disk()

        if cached is not None:
            self._species = cached
            return self._species

        try:
            result = self.bridge.species_list()
            species = result.get("species", [])

        except Exception:
            species = []

        self._species = species

        if species:
            self._save_to_disk(species)

        return self._species

    def _load_from_disk(self):

        if not self.cache_path.exists():
            return None

        try:

            with self.cache_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except Exception:
            return None

    def _save_to_disk(self, species):

        try:

            self.cache_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self.cache_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as file:

                json.dump(
                    species,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write("\n")

        except Exception:
            pass

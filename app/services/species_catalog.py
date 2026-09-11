from __future__ import annotations

import json
from pathlib import Path

from app.core import paths
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
        cache_path=None,
    ):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        # Sin cache_path explícito, resuelve data/species_cache.json
        # relativo a la carpeta del proyecto o del .exe empaquetado
        # -- ver app/core/paths.py.
        self.cache_path = (
            Path(cache_path)
            if cache_path is not None
            else paths.path("data", "species_cache.json")
        )
        self._species = None
        self._by_id = None

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...]. Vacía si el
        bridge no está disponible y tampoco hay caché en disco
        -- nunca lanza, el buscador simplemente queda vacío en
        vez de romper el panel.

        Un resultado vacío NO se cachea en memoria a propósito:
        si el bridge falló porque todavía estaba arrancando (el
        proceso .NET puede tardar unos segundos la primera vez),
        la próxima petición a /api/species vuelve a intentarlo en
        vez de quedar vacía para siempre hasta reiniciar DexRelay.
        """

        if self._species:
            return self._species

        cached = self._load_from_disk()

        if cached:
            self._species = cached
            return self._species

        try:
            result = self.bridge.species_list()
            species = result.get("species", [])

        except Exception:
            species = []

        if species:
            self._species = species
            self._save_to_disk(species)

        return species

    def get_name(self, species_id):
        """
        Nombre en español de una especie puntual, o None si no se
        pudo resolver (07/09/2026, agregado para el modal
        Pokédex de especie: la evolución `LevelUpWithTeammate`
        necesita mostrar el nombre de la especie compañera
        requerida, no solo su id). Reusa list_all() -- no vuelve a
        golpear el bridge si ya está cacheada.
        """

        if self._by_id is None:
            self._by_id = {
                entry["id"]: entry["name"]
                for entry in self.list_all()
            }

        return self._by_id.get(species_id)

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

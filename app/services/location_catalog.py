from __future__ import annotations

import json
from pathlib import Path

from app.services.pkhex.bridge import PKHeXBridge


class LocationCatalog:
    """
    Lista completa {id, name} de ubicaciones conocidas por PKHeX
    para Alpha Sapphire, para precargar las filas del panel de
    encuentros (panels/nuzlocke/app.js).

    Es la MISMA fuente que usa LocationResolver (acción
    'met_location' del bridge) para resolver el lugar de encuentro
    real de una captura -- por diseño, para que los nombres
    coincidan textualmente siempre y una captura nueva encuentre
    su fila existente en vez de crear una duplicada.

    Se resuelve UNA vez y se cachea en memoria y en disco
    (data/location_cache.json), mismo patrón que SpeciesCatalog.
    """

    def __init__(
        self,
        bridge=None,
        cache_path="data/location_cache.json",
    ):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        self.cache_path = Path(cache_path)
        self._locations = None

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...]. Vacía si el
        bridge no está disponible y tampoco hay caché en disco --
        nunca lanza. Un resultado vacío no se cachea en memoria,
        para poder reintentar en la próxima petición (ver
        SpeciesCatalog, mismo motivo).
        """

        if self._locations:
            return self._locations

        cached = self._load_from_disk()

        if cached:
            self._locations = cached
            return self._locations

        try:
            result = self.bridge.location_list()
            locations = result.get("locations", [])

        except Exception:
            locations = []

        if locations:
            self._locations = locations
            self._save_to_disk(locations)

        return locations

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

    def _save_to_disk(self, locations):

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
                    locations,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write("\n")

        except Exception:
            pass

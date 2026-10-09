from __future__ import annotations

import json
from pathlib import Path

from app.core import paths
# Reexportado por compatibilidad (la fuente es el perfil ORAS, Bloque 13).
from app.games.oras.locations import EXCLUDED_LOCATION_IDS  # noqa: F401
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

    La lista cruda de PKHeX trae CIENTOS de ubicaciones que no
    tienen nada que ver con un recorrido de Hoenn (Kalos entero,
    eventos, transferencias, regalos especiales) -- se filtra por
    rango de ID (ver _HOENN_ID_MIN/_HOENN_ID_MAX) y se ordena por
    progresión de historia (_STORY_ORDER_IDS), no por el orden
    crudo que devuelve PKHeX.

    Se resuelve UNA vez y se cachea en memoria y en disco
    (data/location_cache.json), mismo patrón que SpeciesCatalog.
    """

    def __init__(
        self,
        bridge=None,
        cache_path=None,
        profile_provider=None,
    ):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge.shared()
        )

        # Sin cache_path explícito, la caché cruda es data/<cache_file
        # del juego> relativo a la carpeta del proyecto o del .exe
        # empaquetado -- ver app/core/paths.py.
        self._explicit_cache_path = (
            Path(cache_path) if cache_path is not None else None
        )

        # Bloque 13: qué juego está conectado. Sin juego soportado, o
        # con un juego sin catálogo de ubicaciones, la lista es vacía
        # (nunca la de Hoenn para otro juego). Sin provider (probes y
        # tests antiguos) se usa el perfil de Alpha Sapphire.
        self.profile_provider = profile_provider
        self._locations_by_cache = {}

    def _spec(self):
        if self.profile_provider is None:
            from app.games.oras.profile import ALPHA_SAPPHIRE

            return ALPHA_SAPPHIRE.content.locations

        profile = self.profile_provider()

        if profile is None:
            return None

        return profile.content.locations

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...], filtrada a solo
        ubicaciones de Hoenn y ordenada por progresión de historia.
        Vacía si el bridge no está disponible y tampoco hay caché
        en disco -- nunca lanza.

        Importante: lo que se cachea en disco es la lista CRUDA que
        devuelve PKHeX (sin filtrar ni traducir). El filtro, el
        orden de historia y la traducción al español se aplican
        SIEMPRE frescos, tanto si los datos vienen del bridge como
        si vienen del caché. Si en vez de esto se cacheara el
        resultado ya procesado, cualquier mejora futura al filtro o
        a la tabla de traducción (hoenn_locations_es.py) quedaría
        "atrapada" en el caché viejo hasta borrarlo a mano -- ya
        pasó una vez (el caché tenía los nombres en inglés de antes
        de agregar la traducción, y seguía sirviéndolos tal cual).
        """

        spec = self._spec()

        if spec is None:
            return []

        memo = self._locations_by_cache.get(spec.cache_file)

        if memo:
            return memo

        raw_locations = self._load_from_disk(spec)

        if not raw_locations:

            try:
                result = self.bridge.location_list(spec.bridge_game)
                raw_locations = result.get(
                    "locations", []
                )

            except Exception:
                raw_locations = []

            if raw_locations:
                self._save_to_disk(raw_locations, spec)

        if not raw_locations:
            return []

        locations = self._filter_and_order(
            raw_locations, spec
        )

        if locations:
            self._locations_by_cache[spec.cache_file] = locations

        return locations

    def _filter_and_order(self, raw_locations, spec):

        hoenn_locations = {
            entry["id"]: {
                "id": entry["id"],
                "name": spec.translate(
                    entry["id"],
                    entry.get("name", ""),
                ),
            }
            for entry in raw_locations
            if spec.id_min
            <= entry.get("id", -1)
            <= spec.id_max
            and entry.get("id") not in spec.excluded_ids
        }

        ordered = []
        seen_ids = set()

        for location_id in spec.story_order_ids:

            entry = hoenn_locations.get(
                location_id
            )

            if entry is None:
                continue

            ordered.append(entry)
            seen_ids.add(location_id)

        # Cualquier ubicación de Hoenn que no esté en el orden de
        # historia (áreas post-juego / DexNav: mirages, cuevas
        # secretas, Battle Resort, etc.) se agrega al final por ID,
        # para no perder ninguna ubicación real capturable.
        remaining = sorted(
            (
                entry
                for location_id, entry in hoenn_locations.items()
                if location_id not in seen_ids
            ),
            key=lambda entry: entry["id"],
        )

        ordered.extend(remaining)

        return ordered

    def _cache_file(self, spec):
        if self._explicit_cache_path is not None:
            return self._explicit_cache_path

        return paths.path("data", spec.cache_file)

    def _load_from_disk(self, spec):

        cache_path = self._cache_file(spec)

        if not cache_path.exists():
            return None

        try:

            with cache_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except Exception:
            return None

    def _save_to_disk(self, locations, spec):

        cache_path = self._cache_file(spec)

        try:

            cache_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with cache_path.open(
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

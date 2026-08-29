from __future__ import annotations

import json
from pathlib import Path

from app.services.hoenn_locations_es import translate_location_name
from app.services.pkhex.bridge import PKHeXBridge


# Rango de IDs de ubicaciones de Hoenn (ORAS) confirmado con datos
# reales de /api/locations (24/08/2026): todo lo de Hoenn cae entre
# 170 ("Littleroot Town") y 354 ("Secret Base"), sin excepciones.
# Fuera de ese rango queda todo lo que NO es parte del recorrido:
# Kalos/X-Y (IDs 2-168), eventos y torneos (40000+), transferencias
# entre juegos/regiones (30000+), y regalos especiales (60000+).
_HOENN_ID_MIN = 170
_HOENN_ID_MAX = 354

# Ubicaciones de Hoenn excluidas a propósito del catálogo
# (29/08/2026, decisión explícita del usuario) -- no son
# relevantes para un Nuzlocke normal: mirage spots de DexNav que
# aparecen al azar (nunca forman parte de un recorrido real),
# las cuevas de los Regis (post-juego, muy raras), y la base
# secreta del propio jugador (no es un lugar de encuentro
# salvaje). Esto SOLO afecta la lista precargada del panel (no
# aparecen como fila esperando captura) -- si por algún motivo
# rarísimo una captura real reportara uno de estos IDs, igual se
# registraría normal (LocationResolver es un módulo aparte, no
# consulta esta exclusión); el panel simplemente le crearía una
# fila nueva sobre la marcha, como con cualquier ubicación no
# precargada.
EXCLUDED_LOCATION_IDS = {
    276,  # "???" -- ID interno sin uso real, no una ubicación
          # jugable (nombre crudo de PKHeX, nunca se pudo
          # confirmar qué es)
    278,  # Desert Ruins
    306,  # Island Cave
    308,  # Ancient Tomb
    310,  # Sealed Chamber
    334,  # Trackless Forest
    336,  # Pathless Plain
    338,  # Nameless Cavern
    340,  # Fabled Cave
    342,  # Gnarled Den
    344,  # Crescent Isle
    354,  # Secret Base
    350,  # Secret Shore / "Costa Secreta"
    352,  # Secret Meadow / "Prado Secreto"
}

# Orden narrativo aproximado (progresión de historia de ORAS), por
# ID -- no por nombre, para que funcione sin importar en qué idioma
# termine devolviendo el texto PKHeX. Lo que no está en este mapa
# (áreas post-juego/DexNav: mirages, cuevas secretas, etc.) se
# agrega al final, ordenado por ID, para no perder ninguna
# ubicación real aunque no tenga un lugar fijo asignado acá.
_STORY_ORDER_IDS = [
    170,  # Littleroot Town
    204,  # Route 101
    172,  # Oldale Town
    206,  # Route 102
    208,  # Route 103
    184,  # Petalburg City
    210,  # Route 104
    282,  # Petalburg Woods
    190,  # Rustboro City
    234,  # Route 116
    274,  # Rusturf Tunnel
    212,  # Route 105
    174,  # Dewford Town
    280,  # Granite Cave
    214,  # Route 106
    216,  # Route 107
    218,  # Route 108
    220,  # Route 109
    186,  # Slateport City
    222,  # Route 110
    224,  # Route 111
    226,  # Route 112
    284,  # Mt. Chimney
    286,  # Jagged Pass
    178,  # Fallarbor Town
    228,  # Route 113
    230,  # Route 114
    272,  # Meteor Falls
    232,  # Route 115
    176,  # Lavaridge Town
    288,  # Fiery Path
    188,  # Mauville City
    236,  # Route 117
    180,  # Verdanturf Town
    302,  # New Mauville
    238,  # Route 118
    240,  # Route 119
    192,  # Fortree City
    242,  # Route 120
    244,  # Route 121
    324,  # Safari Zone
    246,  # Route 122
    290,  # Mt. Pyre
    248,  # Route 123
    194,  # Lilycove City
    292,  # Team Aqua Hideout
    314,  # Team Magma Hideout
    250,  # Route 124
    304,  # Sea Mauville
    252,  # Route 125
    254,  # Route 126
    256,  # Route 127
    258,  # Route 128
    294,  # Seafloor Cavern
    196,  # Mossdeep City
    260,  # Route 129
    262,  # Route 130
    264,  # Route 131
    182,  # Pacifidlog Town
    266,  # Route 132
    268,  # Route 133
    270,  # Route 134
    198,  # Sootopolis City
    296,  # Cave of Origin
    300,  # Shoal Cave
    316,  # Sky Pillar
    200,  # Ever Grande City
    202,  # Pokémon League (OR/AS)
    298,  # Victory Road (OR/AS)
]


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

        if self._locations:
            return self._locations

        raw_locations = self._load_from_disk()

        if not raw_locations:

            try:
                result = self.bridge.location_list()
                raw_locations = result.get(
                    "locations", []
                )

            except Exception:
                raw_locations = []

            if raw_locations:
                self._save_to_disk(raw_locations)

        if not raw_locations:
            return []

        locations = self._filter_and_order(
            raw_locations
        )

        if locations:
            self._locations = locations

        return locations

    def _filter_and_order(self, raw_locations):

        hoenn_locations = {
            entry["id"]: {
                "id": entry["id"],
                "name": translate_location_name(
                    entry["id"],
                    entry.get("name", ""),
                ),
            }
            for entry in raw_locations
            if _HOENN_ID_MIN
            <= entry.get("id", -1)
            <= _HOENN_ID_MAX
            and entry.get("id") not in EXCLUDED_LOCATION_IDS
        }

        ordered = []
        seen_ids = set()

        for location_id in _STORY_ORDER_IDS:

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

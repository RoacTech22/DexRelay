"""
Carga el dataset estático de descripciones de ítem (curado por
tools/data_curation/build_item_descriptions.py) -- mismo patrón
que MoveDescriptionCatalog/AbilityDescriptionCatalog.

get_id_by_name() (Fase E, 09/09/2026, soporte hackroom) -- MISMA
necesidad que la de movimientos/habilidades (equipos de líder solo
tienen el nombre en inglés del ítem, sin id), pero con una vuelta
extra que los otros dos no tienen:

data/item_descriptions.json usa el id PROPIO de PokéAPI para cada
ítem, NO el índice real del ítem en el juego (el que espera
ItemCatalog/RARE_CANDY_ITEM_ID) -- son DOS numeraciones distintas
que coinciden para muchos ítems tempranos pero divergen para otros
(bug real encontrado y corregido el 09/09/2026, ver el comentario
largo en app/server/http_server.py junto a self.item_sprites_directory
-- ahí mismo se armó data/item_sprite_id_map.json, {índice real:
id de PokéAPI} para los casos que NO coinciden).

Por eso get_id_by_name() acá hace un paso más que sus equivalentes:
resuelve primero el id de PokéAPI (identifier en inglés), y si ese
id de PokéAPI aparece como VALOR en item_sprite_id_map.json (osea,
es un caso conocido donde las dos numeraciones difieren), devuelve
la CLAVE (el índice real) en vez del id de PokéAPI directo.
"""

import json

from app.core import paths


class ItemDescriptionCatalog:

    def __init__(self):
        self._by_item_id = None
        self._id_by_identifier = None
        self._real_index_by_pokeapi_id = None

    def _ensure_loaded(self):

        if self._by_item_id is not None:
            return

        data_path = paths.path("data", "item_descriptions.json")

        if not data_path.exists():
            self._by_item_id = {}
            self._id_by_identifier = {}
        else:
            with open(data_path, "r", encoding="utf-8") as file:
                raw = json.load(file)

            self._by_item_id = {
                int(item_id): entry for item_id, entry in raw.items()
            }

            self._id_by_identifier = {
                entry["name"]: int(item_id)
                for item_id, entry in raw.items()
            }

        # item_sprite_id_map.json: {índice_real (str): id_pokeapi
        # (int)} -- solo para los mismatches. Se invierte acá
        # (pokeapi -> real) porque get_id_by_name() parte de un
        # nombre en inglés y llega primero al id de PokéAPI. Puede
        # no existir todavía (necesita red para generarse, ver
        # build_item_sprite_id_map.py) -- degradación con gracia:
        # sin el mapa, se asume que las dos numeraciones coinciden
        # (cierto para la mayoría de los ítems).
        map_path = paths.path("data", "item_sprite_id_map.json")

        self._real_index_by_pokeapi_id = {}

        if map_path.exists():
            try:
                with open(map_path, "r", encoding="utf-8") as file:
                    sprite_map = json.load(file)

                self._real_index_by_pokeapi_id = {
                    pokeapi_id: int(real_index)
                    for real_index, pokeapi_id in sprite_map.items()
                }
            except Exception:
                self._real_index_by_pokeapi_id = {}

    def get(self, item_id):
        """
        Devuelve {"descriptionEs": str|None, "source": str|None}
        para el ítem pedido (id de PokéAPI, no índice real -- este
        método es solo para el modal de descripción, que ya recibe
        el id correcto por otro lado). Valores vacíos si no está en
        el dataset.
        """

        self._ensure_loaded()

        return self._by_item_id.get(
            item_id,
            {"descriptionEs": None, "source": None},
        )

    def get_id_by_name(self, display_name):
        """
        Resuelve el ÍNDICE REAL del ítem en el juego (no el id de
        PokéAPI) a partir de un nombre en inglés legible (ej.
        "Sharp Beak", tal como vienen los ítems en
        gym_leaders_rrss.json). Ver el docstring del módulo para el
        porqué del paso extra de cruce.

        Devuelve None si no se encuentra -- mismo criterio que
        MoveDescriptionCatalog.get_id_by_name().
        """

        self._ensure_loaded()

        identifier = display_name.strip().lower().replace(" ", "-")

        pokeapi_id = self._id_by_identifier.get(identifier)

        if pokeapi_id is None:
            return None

        return self._real_index_by_pokeapi_id.get(pokeapi_id, pokeapi_id)

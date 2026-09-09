"""
Carga el dataset estático de descripciones de movimiento (curado
por tools/data_curation/build_move_descriptions.py) para el modal
de movimiento (roadmap 06/09/2026, sección 4.1).

Mismo patrón exacto que MoveDataCatalog (app/services/move_data.py)
-- instancia única, cacheada en memoria después de la primera
lectura, degradación con gracia si el archivo no existe o el
movimiento puntual no tiene descripción en español (nunca inventa
texto ni cae al inglés en silencio, ver build_move_descriptions.py).

get_id_by_name() (07/09/2026, a pedido del usuario: "en donde haya
una habilidad o movimiento se debería poder acceder a su
información") -- la página Pokémon ya tiene el id real (viene del
bridge PKHeX), pero otras partes de la app (ej. la ventana de
detalle de líder de gimnasio, data/gym_leaders.json) solo tienen el
NOMBRE en inglés curado a mano, sin id. Esto resuelve nombre -> id
reusando el mismo dataset ya cargado, sin necesitar re-curar
gym_leaders.json con ids.
"""

import json

from app.core import paths


class MoveDescriptionCatalog:

    def __init__(self):
        self._by_move_id = None
        self._id_by_identifier = None

    def _ensure_loaded(self):

        if self._by_move_id is not None:
            return

        data_path = paths.path("data", "move_descriptions.json")

        if not data_path.exists():
            self._by_move_id = {}
            self._id_by_identifier = {}
            return

        with open(data_path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        self._by_move_id = {
            int(move_id): entry for move_id, entry in raw.items()
        }

        self._id_by_identifier = {
            entry["name"]: int(move_id)
            for move_id, entry in raw.items()
        }

    def get(self, move_id):
        """
        Devuelve {"descriptionEs": str|None, "source": str|None}
        para el movimiento pedido, o valores vacíos si no está en
        el dataset.
        """

        self._ensure_loaded()

        return self._by_move_id.get(
            move_id,
            {"descriptionEs": None, "source": None},
        )

    def get_id_by_name(self, display_name):
        """
        Resuelve el id de PokéAPI a partir de un nombre en inglés
        "legible" (ej. "Rock Tomb", tal como vienen los movimientos
        en data/gym_leaders.json) -- lo normaliza al formato
        identifier de PokéAPI (minúsculas, espacios a guiones, ej.
        "rock-tomb") y lo busca contra el índice ya armado en
        _ensure_loaded().

        Devuelve None si no se encuentra -- movimientos con
        puntuación rara en el nombre (apóstrofes, etc.) podrían no
        normalizar exacto; no es un caso esperado para los ~937
        movimientos reales de este proyecto, pero se documenta acá
        por si algún día aparece uno.
        """

        self._ensure_loaded()

        identifier = display_name.strip().lower().replace(" ", "-")

        return self._id_by_identifier.get(identifier)

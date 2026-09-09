"""
Carga el dataset estático de descripciones de habilidad (curado por
tools/data_curation/build_ability_descriptions.py) para el modal de
habilidad (roadmap 06/09/2026, sección 4.1).

Mismo patrón exacto que MoveDescriptionCatalog -- instancia única,
cacheada en memoria, degradación con gracia si el archivo no existe
o la habilidad puntual no tiene descripción en español.

get_id_by_name() (07/09/2026): mismo motivo que
MoveDescriptionCatalog.get_id_by_name() -- data/gym_leaders.json
solo tiene el nombre en inglés de la habilidad, sin id.
"""

import json

from app.core import paths


class AbilityDescriptionCatalog:

    def __init__(self):
        self._by_ability_id = None
        self._id_by_identifier = None

    def _ensure_loaded(self):

        if self._by_ability_id is not None:
            return

        data_path = paths.path("data", "ability_descriptions.json")

        if not data_path.exists():
            self._by_ability_id = {}
            self._id_by_identifier = {}
            return

        with open(data_path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        self._by_ability_id = {
            int(ability_id): entry
            for ability_id, entry in raw.items()
        }

        self._id_by_identifier = {
            entry["name"]: int(ability_id)
            for ability_id, entry in raw.items()
        }

    def get(self, ability_id):
        """
        Devuelve {"descriptionEs": str|None, "source": str|None}
        para la habilidad pedida, o valores vacíos si no está en
        el dataset.
        """

        self._ensure_loaded()

        return self._by_ability_id.get(
            ability_id,
            {"descriptionEs": None, "source": None},
        )

    def get_id_by_name(self, display_name):
        """
        Resuelve el id de PokéAPI a partir de un nombre en inglés
        legible (ej. "Magnet Pull") -- ver el docstring equivalente
        en MoveDescriptionCatalog.get_id_by_name() para el porqué
        completo.
        """

        self._ensure_loaded()

        identifier = display_name.strip().lower().replace(" ", "-")

        return self._id_by_identifier.get(identifier)

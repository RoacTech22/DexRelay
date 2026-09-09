"""
Carga el índice inverso de evolución (curado por
tools/data_curation/build_pre_evolution_index.py) -- para el modal
Pokédex de especie (roadmap 07/09/2026), que necesita mostrar la
cadena completa (pre-evolución -> especie actual -> evolución
siguiente), no solo hacia adelante.
"""

import json

from app.core import paths


class PreEvolutionCatalog:

    def __init__(self):
        self._by_species_id = None

    def _ensure_loaded(self):

        if self._by_species_id is not None:
            return

        data_path = paths.path("data", "pre_evolution_index.json")

        if not data_path.exists():
            self._by_species_id = {}
            return

        with open(data_path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        self._by_species_id = {
            int(species_id): entry
            for species_id, entry in raw.items()
        }

    def get(self, species_id):
        """
        Devuelve {"speciesId", "name"} de la pre-evolución, o
        `None` si esta especie no evoluciona de ninguna otra
        (ej. Nidoran, un inicial, o cualquier primera etapa).
        """

        self._ensure_loaded()

        return self._by_species_id.get(species_id)

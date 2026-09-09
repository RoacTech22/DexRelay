"""
Carga el dataset estático de altura/peso/categoría/descripción de
especie (curado por tools/data_curation/build_species_extra.py)
para el modal Pokédex de especie (roadmap 07/09/2026).

Mismo patrón exacto que MoveDescriptionCatalog/AbilityDescriptionCatalog
-- instancia única, cacheada en memoria, degradación con gracia si
el archivo no existe o la especie puntual no tiene alguno de los
datos (nunca inventa un valor de respaldo).
"""

import json

from app.core import paths


class SpeciesExtraCatalog:

    def __init__(self):
        self._by_species_id = None

    def _ensure_loaded(self):

        if self._by_species_id is not None:
            return

        data_path = paths.path("data", "species_extra.json")

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
        Devuelve {"heightM", "weightKg", "genus", "description"}
        para la especie pedida -- cualquier campo puede ser `None`
        si no se pudo resolver, nunca un valor inventado.
        """

        self._ensure_loaded()

        return self._by_species_id.get(
            species_id,
            {
                "heightM": None,
                "weightKg": None,
                "genus": None,
                "description": None,
            },
        )

class SpeciesResolver:
    """
    Resuelve el nombre de una especie a partir
    de los datos de especies disponibles.
    """

    def __init__(self, species_data=None):
        self.species_data = (
            species_data
            if isinstance(species_data, list)
            else []
        )

    def resolve(self, species_id):
        """
        Busca una especie por speciesId.

        Devuelve el nombre de la especie.
        Si no existe, devuelve una cadena vacía.
        """

        for info in self.species_data:

            if not isinstance(info, dict):
                continue

            if info.get("speciesId", 0) == species_id:
                return info.get(
                    "species",
                    ""
                )

        return ""

    def set_species_data(self, species_data):
        """
        Reemplaza los datos disponibles
        para resolver especies.
        """

        if isinstance(species_data, list):
            self.species_data = species_data
        else:
            self.species_data = []
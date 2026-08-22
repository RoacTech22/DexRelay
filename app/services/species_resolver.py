from app.services.pkhex.bridge import PKHeXBridge


class SpeciesResolver:
    """
    Resuelve el nombre de una especie.

    Puede utilizar datos estáticos para pruebas y
    PKHeX como fuente dinámica para el runtime.
    """

    def __init__(
        self,
        species_data=None,
        bridge=None,
    ):
        self.species_data = (
            species_data
            if isinstance(species_data, list)
            else []
        )

        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        self.cache = {}

    def resolve(self, species_id):
        """
        Resuelve una especie por su ID.

        Primero consulta los datos estáticos,
        después la caché y finalmente PKHeX.
        """

        for info in self.species_data:

            if not isinstance(info, dict):
                continue

            if info.get("speciesId", 0) == species_id:
                return info.get(
                    "species",
                    "",
                )

        if species_id in self.cache:
            return self.cache[species_id]

        try:
            result = self.bridge.species(
                species_id
            )

            name = result.get(
                "name",
                "",
            )

            if name:
                self.cache[species_id] = name

            return name

        except Exception:
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

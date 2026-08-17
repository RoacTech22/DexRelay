from app.readers.citra import Citra
from app.memory.memory_reader import MemoryReader
from app.memory.pointers import (
    PARTY_ORDER_ADDRESS,
    ORDER_ENTRY_SIZE,
    POKEMON_POINTER_OFFSET,
    SLOT_DATA_SIZE,
    STAT_DATA_OFFSET,
    STAT_DATA_SIZE,
)
from app.memory.structures import Pokemon6
from app.services.species_resolver import SpeciesResolver


class AzaharReader:
    """
    Reader responsable exclusivamente de obtener
    los datos actuales de la party desde Azahar.
    """

    def __init__(
        self,
        citra=None,
        species_resolver=None
    ):
        self.citra = citra or Citra()

        self.memory = MemoryReader(
            self.citra
        )

        self.species_resolver = (
            species_resolver
            or SpeciesResolver()
        )

    def find_game_process(self):
        """
        Busca el proceso del juego dentro de Azahar.
        """

        processes = (
            self.citra.process_list()
        )

        for process_id, data in processes.items():

            title_id, process_name = data

            if process_name == "sango-2":
                return process_id

        return None

    def connect(self):
        """
        Busca sango-2 y lo selecciona
        como proceso activo.
        """

        process_id = (
            self.find_game_process()
        )

        if process_id is None:
            return False

        self.citra.set_process(
            process_id
        )

        return True

    def is_connected(self):
        """
        Comprueba si existe un proceso activo.
        """

        try:
            process_id = (
                self.citra.get_process()
            )

            return process_id is not None

        except Exception:
            return False

    def read_party_order(self):
        """
        Lee la tabla que determina el orden
        actual de los seis Pokémon.
        """

        data = self.memory.read(
            PARTY_ORDER_ADDRESS,
            ORDER_ENTRY_SIZE * 6
        )

        if not data:
            return []

        if len(data) != ORDER_ENTRY_SIZE * 6:
            return []

        pointers = []

        for slot in range(6):

            pointer = int.from_bytes(
                data[
                    slot * ORDER_ENTRY_SIZE:
                    (slot + 1) * ORDER_ENTRY_SIZE
                ],
                byteorder="little"
            )

            pointers.append(
                pointer
            )

        return pointers

    def read_pokemon(self, pointer):
        """
        Lee y descifra un Pokémon a partir
        del puntero de la tabla de party.
        """

        if pointer == 0:
            return None

        address = (
            pointer
            + POKEMON_POINTER_OFFSET
        )

        party_data = self.memory.read(
            address,
            SLOT_DATA_SIZE
        )

        if not party_data:
            return None

        if len(party_data) != SLOT_DATA_SIZE:
            return None

        stats_address = (
            address
            + SLOT_DATA_SIZE
            + STAT_DATA_OFFSET
        )

        stats_data = self.memory.read(
            stats_address,
            STAT_DATA_SIZE
        )

        if not stats_data:
            return None

        if len(stats_data) != STAT_DATA_SIZE:
            return None

        encrypted_data = (
            party_data
            + stats_data
        )

        pokemon = Pokemon6(
            encrypted_data
        )

        if not pokemon.raw_data:
            return None

        return pokemon

    def build_pokemon_data(
        self,
        slot,
        pokemon
    ):
        """
        Convierte Pokemon6 en el formato
        de datos utilizado por DexRelay.
        """

        if pokemon is None:

            return {
                "slot": slot,
                "empty": True,
                "nickname": "",
                "species": "",
                "speciesId": 0,
                "level": 0,
                "hp": 0,
                "maxHp": 0,
            }

        species_id = (
            pokemon.species_id()
        )

        species = (
            self.species_resolver.resolve(
                species_id
            )
        )

        return {
            "slot": slot,
            "empty": species_id == 0,
            "nickname": pokemon.nickname(),
            "species": species,
            "speciesId": species_id,
            "level": pokemon.level(),
            "hp": pokemon.hp(),
            "maxHp": pokemon.max_hp(),
        }

    def read_party(self):
        """
        Lee los seis slots actuales de la party.
        """

        pointers = (
            self.read_party_order()
        )

        if len(pointers) != 6:
            return []

        party = []

        for slot_index, pointer in enumerate(
            pointers
        ):

            slot = slot_index + 1

            pokemon = (
                self.read_pokemon(
                    pointer
                )
            )

            data = (
                self.build_pokemon_data(
                    slot,
                    pokemon
                )
            )

            party.append(
                data
            )

        return party
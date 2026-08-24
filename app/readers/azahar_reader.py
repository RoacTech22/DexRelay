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


class ReadFailure:
    """
    Sentinela para distinguir un slot genuinamente
    vacío (pointer == 0) de una lectura de memoria
    que falló de forma transitoria (paquete UDP
    perdido, lectura incompleta, etc).

    Son casos distintos y no deben tratarse igual:
    un slot vacío es información válida, una lectura
    fallida no lo es.
    """


READ_FAILED = ReadFailure()


class AzaharReader:
    """
    Reader responsable exclusivamente de obtener
    los datos actuales de la party desde Azahar.
    """

    def __init__(
        self,
        citra=None,
        species_resolver=None,
        process_name="sango-2"
    ):
        self.citra = citra or Citra()

        self.memory = MemoryReader(
            self.citra
        )

        self.species_resolver = (
            species_resolver
            or SpeciesResolver()
        )

        # Nombre del proceso de juego dentro de Azahar.
        # Configurable via config.json (azahar.process_name);
        # "sango-2" queda como valor por defecto para no
        # romper usos existentes (probes, tests) que crean
        # AzaharReader() sin pasar este argumento.
        self.process_name = process_name

        # Último dato válido conocido por slot (1 a 6).
        # Se usa como fallback cuando una lectura de
        # memoria falla de forma transitoria, en vez
        # de reportar el slot como vacío.
        self._last_known_party = [None] * 6

    def find_game_process(self):
        """
        Busca el proceso del juego dentro de Azahar.
        """

        processes = (
            self.citra.process_list()
        )

        for process_id, data in processes.items():

            title_id, process_name = data

            if process_name == self.process_name:
                return process_id

        return None

    def connect(self):
        """
        Busca sango-2 y lo selecciona
        como proceso activo.

        Si Azahar no está disponible o la comunicación
        falla durante la búsqueda, se considera
        desconectado y se reintentará en la siguiente
        actualización.
        """

        try:
            process_id = (
                self.find_game_process()
            )

            if process_id is None:
                return False

            self.citra.set_process(
                process_id
            )

            return True

        except Exception:
            return False

    def is_connected(self):
        """
        Comprueba si existe un proceso de juego válido seleccionado.
        """

        try:
            process_id = (
                self.citra.get_process()
            )

            return (
                process_id is not None
                and process_id != 0xFFFFFFFF
            )

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

        Devuelve:
        - None si el slot está genuinamente vacío
          (pointer == 0).
        - READ_FAILED si el slot debería tener un
          Pokémon pero la lectura de memoria falló
          de forma transitoria (paquete UDP perdido,
          lectura incompleta, descifrado inválido).
        - Un Pokemon6 si la lectura fue exitosa.
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
            return READ_FAILED

        if len(party_data) != SLOT_DATA_SIZE:
            return READ_FAILED

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
            return READ_FAILED

        if len(stats_data) != STAT_DATA_SIZE:
            return READ_FAILED

        encrypted_data = (
            party_data
            + stats_data
        )

        pokemon = Pokemon6(
            encrypted_data
        )

        if not pokemon.raw_data:
            # La estructura no pasó la validación de
            # Pokemon6 (por ejemplo, una lectura a medio
            # escribir por el juego). Esto es una falla
            # de lectura, no un slot vacío: el pointer
            # ya nos dijo que debería haber un Pokémon.
            return READ_FAILED

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

        Si un slot falla la lectura de forma transitoria,
        se reutiliza el último dato válido conocido para
        ese slot en vez de reportarlo como vacío. Esto
        evita que un Pokémon "desaparezca" del overlay
        por una sola lectura UDP perdida.
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

            if pokemon is READ_FAILED:

                cached = (
                    self._last_known_party[
                        slot_index
                    ]
                )

                if cached is not None:
                    data = cached
                else:
                    # No hay dato previo para este slot
                    # (por ejemplo, falló ya en la primera
                    # lectura). No queda otra que reportarlo
                    # vacío por esta vez.
                    data = self.build_pokemon_data(
                        slot,
                        None
                    )

            else:

                data = (
                    self.build_pokemon_data(
                        slot,
                        pokemon
                    )
                )

                self._last_known_party[
                    slot_index
                ] = data

            party.append(
                data
            )

        return party

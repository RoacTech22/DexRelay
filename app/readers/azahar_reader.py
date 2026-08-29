import struct

from app.readers.citra import Citra
from app.memory.memory_reader import MemoryReader
from app.memory.pointers import (
    PARTY_ORDER_ADDRESS,
    PARTY_COUNT_ADDRESS,
    get_party_order_address,
    get_party_count_address,
    ORDER_ENTRY_SIZE,
    POKEMON_POINTER_OFFSET,
    SLOT_DATA_SIZE,
    STAT_DATA_OFFSET,
    STAT_DATA_SIZE,
    LAST_CAUGHT_ADDRESS,
    TOTAL_CAUGHT_ADDRESS,
    BOX_BASE_ADDRESS,
    BOX_SLOT_STRIDE,
    BOX_SLOT_COUNT,
    CURRENT_ZONE_ID_ADDRESS,
)
from app.memory.structures import Pokemon6
from app.services.location_resolver import LocationResolver
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
        location_resolver=None,
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

        # Resuelve lugar de encuentro y shiny vía PKHeX,
        # cacheado por nickname (ver location_resolver.py).
        self.location_resolver = (
            location_resolver
            or LocationResolver()
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

        Corrección (29/08/2026, bug real CONFIRMADO con Cheat
        Engine -- ver PARTY_COUNT_ADDRESS en pointers.py): al
        depositar un Pokémon en la Caja PC, el puntero que le
        correspondía NO se limpia -- PARTY_ORDER_ADDRESS son 6
        casilleros fijos que el juego siempre mantiene reservados,
        y el puntero "sobrante" queda apuntando a datos viejos
        pero todavía válidos (por eso decodificaba bien y el
        overlay lo mostraba como si siguiera en el equipo).

        Se lee PARTY_COUNT_ADDRESS (la cantidad real, confirmada
        en vivo: bajó de 6 a 2 exactamente en cada depósito, ver
        tools/probes/party/observar_candidato_party_count.py) y
        cualquier slot en una posición >= esa cantidad se fuerza a
        0 (vacío), sin importar qué basura tenga el puntero ahí.

        Multi-versión (29/08/2026): PARTY_ORDER_ADDRESS y
        PARTY_COUNT_ADDRESS NO son las mismas entre Alpha Sapphire
        y Omega Ruby (confirmado -- la dirección de AS da 0x0 en
        los 6 slots probando en OR). Se elige el par correcto según
        `self.process_name` (ver get_party_order_address()/
        get_party_count_address() en pointers.py) -- mismo criterio
        que ya usa el proyecto para encontrar el proceso del juego.
        """

        party_order_address = get_party_order_address(
            self.process_name
        )

        party_count_address = get_party_count_address(
            self.process_name
        )

        data = self.memory.read(
            party_order_address,
            ORDER_ENTRY_SIZE * 6
        )

        if not data:
            return []

        if len(data) != ORDER_ENTRY_SIZE * 6:
            return []

        count_byte = self.memory.read(
            party_count_address,
            1
        )

        # Si por algún motivo transitorio esta lectura falla, no
        # hay forma segura de saber cuántos slots son reales --
        # se prefiere devolver los 6 punteros tal cual (mismo
        # comportamiento que antes de este fix) a arriesgarse a
        # vaciar de más por una lectura perdida.
        party_count = (
            count_byte[0]
            if len(count_byte) == 1
            else 6
        )

        pointers = []

        for slot in range(6):

            pointer = int.from_bytes(
                data[
                    slot * ORDER_ENTRY_SIZE:
                    (slot + 1) * ORDER_ENTRY_SIZE
                ],
                byteorder="little"
            )

            if slot >= party_count:
                # Slot "sobrante" -- el puntero puede tener datos
                # viejos pero válidos ahí, se fuerza a vacío.
                pointer = 0

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

        return self._read_pokemon_at_address(
            address
        )

    def _read_pokemon_at_address(self, address):
        """
        Lee y descifra un Pokémon en una dirección absoluta
        (ya resuelta, sin sumarle POKEMON_POINTER_OFFSET).
        Reutilizada por read_pokemon() (party) y
        read_last_caught() (LAST_CAUGHT_ADDRESS).

        Devuelve READ_FAILED si la lectura o el descifrado
        fallan; un Pokemon6 si fue exitosa.
        """

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
                "shiny": False,
                "metLocation": "",
                "metLocationId": 0,
                "eggLocation": "",
                "isEgg": False,
            }

        species_id = (
            pokemon.species_id()
        )

        species = (
            self.species_resolver.resolve(
                species_id
            )
        )

        nickname = pokemon.nickname()

        # Lugar de encuentro + shiny vía PKHeX. Se le pasan los
        # primeros 232 bytes de raw_data (la estructura PK6 "box
        # format" ya descifrada) -- la misma fuente que ya usan
        # species_id()/nickname()/level()/hp() arriba, no memoria
        # nueva. Cacheado por nickname en LocationResolver, así
        # que esto solo golpea el bridge PKHeX la primera vez que
        # se ve cada Pokémon puntual.
        location_info = (
            self.location_resolver.resolve(
                nickname,
                pokemon.raw_data[:232],
            )
        )

        return {
            "slot": slot,
            "empty": species_id == 0,
            "nickname": nickname,
            "species": species,
            "speciesId": species_id,
            "level": pokemon.level(),
            "hp": pokemon.hp(),
            "maxHp": pokemon.max_hp(),
            "shiny": location_info["shiny"],
            "metLocation": location_info["metLocation"],
            # 29/08/2026, a pedido del usuario (detección de
            # fósiles poco confiable dependiendo solo del
            # placeholder "Egg"): se propaga también el ID crudo,
            # no solo el texto ya traducido -- permite comparar
            # contra ubicaciones puntuales (ej. Devon Corp) sin
            # depender de que la traducción exista/coincida.
            "metLocationId": location_info["metLocationId"],
            "eggLocation": location_info["eggLocation"],
            # 29/08/2026, a pedido del usuario: para que el Team
            # Overlay pueda mostrar el sprite genérico de huevo en
            # vez de la especie real de un huevo sin nacer todavía
            # (spoiler) -- ver LocationResolver.resolve().
            "isEgg": location_info["isEgg"],
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

    def read_last_caught(self):
        """
        Lee LAST_CAUGHT_ADDRESS (ver pointers.py): la dirección fija
        que contiene el Pokémon capturado más recientemente, incluso
        si fue directo a la Caja PC porque la party estaba llena
        (en ese caso nunca aparece en read_party()).

        Devuelve el mismo formato que build_pokemon_data(), o None
        si la lectura falló (transitoriamente, o si nunca hubo
        ninguna captura todavía en esta partida -- la estructura
        vacía se descarta igual que un slot de party vacío).
        """

        pokemon = self._read_pokemon_at_address(
            LAST_CAUGHT_ADDRESS
        )

        if pokemon is READ_FAILED:
            return None

        if pokemon is None:
            return None

        return self.build_pokemon_data(
            0,
            pokemon
        )

    def read_total_caught_count(self):
        """
        Lee TOTAL_CAUGHT_ADDRESS (ver pointers.py): sube en
        exactamente 1 cada vez que se captura un Pokémon real
        (equipo o Caja PC). Se usa como confirmación de que
        read_last_caught() refleja una captura de verdad, y no
        solo un encuentro salvaje sin capturar (ver Documento
        Maestro, investigación del 25/08/2026).

        Devuelve el valor entero, o None si la lectura falló.
        """

        data = self.memory.read(
            TOTAL_CAUGHT_ADDRESS,
            4
        )

        if len(data) != 4:
            return None

        return struct.unpack(
            "<I",
            data
        )[0]

    def read_current_zone_id(self):
        """
        Lee CURRENT_ZONE_ID_ADDRESS (ver pointers.py): 1 byte con
        el ID crudo de la zona/ruta donde está parado el jugador
        ahora mismo. Usado por la detección automática del estado
        "perdido" del Nuzlocke Tracker (ver Runtime.update() y
        app/services/zone_names.py) -- es un dato distinto de
        `metLocation` (que solo existe dentro de un Pokémon ya
        capturado).

        Devuelve el entero crudo (0-255), o None si la lectura
        falló.
        """

        data = self.memory.read(
            CURRENT_ZONE_ID_ADDRESS,
            1
        )

        if len(data) != 1:
            return None

        return data[0]

    def read_box(self):
        """
        Escanea la Caja PC (Caja 1) completa: BOX_SLOT_COUNT slots
        de BOX_SLOT_STRIDE bytes cada uno, a partir de
        BOX_BASE_ADDRESS (ver pointers.py -- confirmado
        empíricamente el 26-27/08/2026 escaneando por checksum
        válido, estable entre reinicios de Azahar).

        A diferencia de la party, la Caja PC es un array compacto
        y persistente -- no hay tabla de punteros ni buffer
        reciclado, así que no hace falta el manejo de
        READ_FAILED/último-valor-conocido de read_party(): si una
        lectura falla de forma transitoria, el dato sigue estando
        ahí en el siguiente ciclo (no "desaparece" como podía pasar
        con el viejo LAST_CAUGHT_ADDRESS).

        El formato de la Caja PC son los 232 bytes crudos del PK6
        SIN los datos extra que sí tiene la party (nivel/HP actual
        no existen en el formato de caja -- el juego los recalcula
        al retirar el Pokémon). Por eso acá se construye Pokemon6
        directo con el chunk de SLOT_DATA_SIZE, sin leer STAT_DATA
        como hace read_pokemon()/_read_pokemon_at_address().
        build_pokemon_data() sigue funcionando igual sobre este
        resultado, solo que level/hp/maxHp quedan en 0 para estas
        entradas -- no afecta al Nuzlocke Tracker, que de una
        captura en la caja solo necesita nickname/especie/
        ubicación/shiny.

        Devuelve una lista con SOLO los slots ocupados (checksum
        válido) en el mismo formato que build_pokemon_data(). Los
        slots vacíos o con lectura fallida se omiten directamente
        -- a diferencia de read_party(), nada en el proyecto
        necesita ver los 30 slots completos, solo cuáles hay.
        Lista vacía si la lectura de memoria falló por completo.
        """

        window_size = (
            BOX_SLOT_COUNT
            * BOX_SLOT_STRIDE
        )

        data = self.memory.read(
            BOX_BASE_ADDRESS,
            window_size
        )

        if not data:
            return []

        if len(data) != window_size:
            return []

        occupied = []

        for slot_index in range(BOX_SLOT_COUNT):

            start = (
                slot_index
                * BOX_SLOT_STRIDE
            )

            chunk = data[
                start:
                start + SLOT_DATA_SIZE
            ]

            if len(chunk) != SLOT_DATA_SIZE:
                continue

            pokemon = Pokemon6(chunk)

            if not pokemon.raw_data:
                # Slot vacío o checksum inválido -- se omite.
                continue

            occupied.append(
                self.build_pokemon_data(
                    slot_index + 1,
                    pokemon
                )
            )

        return occupied

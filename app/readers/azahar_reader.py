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
    get_box_base_address,
    CURRENT_ZONE_ID_ADDRESS,
    get_current_zone_id_address,
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)
from app.memory.structures import Pokemon6
from app.services.location_resolver import LocationResolver
from app.services.species_resolver import SpeciesResolver


# Todos los juegos que DexRelay sabe leer hoy. Usado para el modo
# "automático" (self.process_name = None -- ver find_game_process())
# y para detect_process_name(), que solo mira sin conectarse (GUI
# v2, 02/09/2026: Bienvenida sin selección manual + botón
# "Reiniciar" del Reader que detecta un cambio de juego).
KNOWN_PROCESS_NAMES = (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


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

        # PID del proceso de juego dentro de Azahar, guardado la
        # última vez que connect() lo encontró. Ver GUI v2
        # (30/08/2026 en adelante, app/gui_web/), pantalla
        # "Conectado" -- no se usaba antes de eso, no afecta nada
        # de la lectura de memoria en sí.
        self.process_id = None

        # Title ID del juego cargado (8 bytes que Nintendo asigna
        # por versión -- Alpha Sapphire y Omega Ruby tienen uno
        # cada uno, confirmado en la instancia real del usuario el
        # 31/08/2026). A diferencia de process_id, no hace falta
        # refrescarlo cada ciclo: no cambia mientras siga
        # seleccionado el mismo proceso, así que _refresh_title_id()
        # se llama desde is_connected() solo mientras siga en
        # `None`, para no gastar una llamada UDP de más (process_list(),
        # más pesada que get_process()) en cada ciclo de 200ms sin
        # necesidad real.
        self.title_id = None

    def find_game_process(self):
        """
        Busca el proceso del juego dentro de Azahar.

        Si `self.process_name` es `None` (modo automático -- ver
        Api.start_auto(), GUI v2, 02/09/2026: Bienvenida ya no
        pide elegir versión, se detecta sola), busca CUALQUIERA de
        los juegos conocidos (KNOWN_PROCESS_NAMES) en vez de uno
        fijo. Al encontrar uno, fija `self.process_name` a ese --
        de ahí en adelante la sesión queda atada a ese juego (los
        offsets de pointers.py se eligen por process_name, "seguir
        en automático" después de conectar no tendría sentido).
        """

        processes = (
            self.citra.process_list()
        )

        candidates = (
            (self.process_name,)
            if self.process_name is not None
            else KNOWN_PROCESS_NAMES
        )

        for process_id, data in processes.items():

            title_id, process_name = data

            if process_name in candidates:
                # Ya que estamos leyendo esto acá (mismo dato que
                # _refresh_title_id() buscaría de nuevo con otra
                # llamada UDP), lo guardamos directo -- cubre el
                # camino normal de connect(). is_connected() sigue
                # llamando _refresh_title_id() como respaldo para
                # el caso en que connect() nunca se ejecuta (ver
                # su docstring).
                self.title_id = title_id
                self.process_name = process_name
                return process_id

        return None

    def detect_process_name(self):
        """
        Recorre process_list() y devuelve el primer process_name
        conocido (KNOWN_PROCESS_NAMES) que encuentre entre los
        procesos que reporta Azahar en este momento, o `None` si
        no hay ninguno corriendo. A diferencia de
        find_game_process(), NO selecciona nada ni toca
        `self.process_name`/`self.title_id` -- solo mira.

        Usado por Application.restart_reader() (detectar que el
        usuario abrió un juego distinto al configurado) y por la
        GUI (sugerir "hacé clic en Reiniciar" cuando corresponde,
        sin conectarse todavía).
        """

        try:
            processes = self.citra.process_list()
        except Exception:
            return None

        for _process_id, data in processes.items():
            _title_id, process_name = data

            if process_name in KNOWN_PROCESS_NAMES:
                return process_name

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

            self.process_id = process_id

            return True

        except Exception:
            return False

    def _refresh_title_id(self):
        """
        Busca el Title ID del proceso actualmente seleccionado
        (self.process_id) recorriendo process_list() -- la misma
        llamada que ya usa find_game_process(), reutilizada acá.
        Silenciosa ante cualquier error: si falla, simplemente
        self.title_id sigue en None y se reintenta en el próximo
        ciclo (mismo criterio que el resto de la clase).
        """

        if self.process_id is None:
            return

        try:
            processes = self.citra.process_list()
        except Exception:
            return

        data = processes.get(self.process_id)

        if data is not None:
            title_id, _process_name = data
            self.title_id = title_id

    def is_connected(self):
        """
        Comprueba si existe un proceso de juego válido seleccionado.

        También actualiza `self.process_id` acá (no solo en
        connect()) -- si Azahar ya tenía el proceso seleccionado
        de una sesión anterior, `Runtime.update()` nunca llega a
        llamar `connect()` (is_connected() ya da True de entrada),
        y `self.process_id` se quedaba en `None` para siempre.
        Bug real detectado el 31/08/2026: el panel "Conectado" de
        la GUI v2 mostraba el ID de proceso vacío en ese escenario.
        Mismo motivo por el que acá también se intenta resolver
        `self.title_id` mientras siga sin conocerse.

        Bug real relacionado, encontrado el 02/09/2026: en modo
        automático (`self.process_name is None`, ver
        find_game_process()) esto NO alcanza -- Azahar puede seguir
        reportando un proceso "válido" de una sesión anterior (por
        ejemplo, después de "Salir" y volver a entrar) sin que
        DexRelay sepa todavía a qué JUEGO corresponde. Sin este
        chequeo, is_connected() daba `True` de una, sin pasar nunca
        por find_game_process(), y `process_name` se quedaba en
        `None` para siempre -- el juego nunca se detectaba.
        """

        try:
            process_id = (
                self.citra.get_process()
            )

            connected = (
                process_id is not None
                and process_id != 0xFFFFFFFF
            )

            if connected and self.process_name is None:
                # Hay un proceso seleccionado, pero en modo
                # automático todavía no sabemos si es un juego
                # conocido -- forzar el camino normal de connect()
                # -> find_game_process(), que sí busca por nombre.
                connected = False

            if connected:
                self.process_id = process_id

                if self.title_id is None:
                    self._refresh_title_id()

            return connected

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

        # Bug real (03/09/2026, confirmado con traceback real:
        # TypeError al cambiar de juego con la app corriendo): la
        # intención de este fallback ya estaba (ver comentario de
        # abajo) pero la implementación solo contemplaba que
        # count_byte viniera con la longitud equivocada -- no que
        # self.memory.read() directamente devuelva None (pasa
        # cuando el socket UDP falla de forma transitoria, típico
        # al cerrar/cambiar de emulador). len(None) tira TypeError
        # en vez de simplemente "no es válido", así que hacía
        # falta el chequeo explícito de None antes.
        #
        # Si por algún motivo transitorio esta lectura falla, no
        # hay forma segura de saber cuántos slots son reales --
        # se prefiere devolver los 6 punteros tal cual (mismo
        # comportamiento que antes de este fix) a arriesgarse a
        # vaciar de más por una lectura perdida.
        party_count = (
            count_byte[0]
            if count_byte is not None and len(count_byte) == 1
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

    def read_pokemon_raw_for_slot(self, slot):
        """
        Lee y descifra el Pokemon6 COMPLETO (no el dict de
        build_pokemon_data()) del slot indicado (1-6) de la party
        actual -- usado por la página Pokémon de la GUI (Bloque 3)
        para pedirle al bridge PKHeX detalles que no forman parte
        del ciclo realtime normal (tipos, habilidad, stats de
        combate, naturaleza, movimientos): ningún overlay ni el
        Dashboard los necesitan, así que golpear el bridge por
        esto en cada ciclo de 200ms de Runtime.update() sería
        innecesario -- se piden bajo demanda, solo cuando la
        página Pokémon está abierta (ver
        Api.get_pokemon_page_data() en app/gui_web/api.py).

        Vuelve a leer memoria en el momento (no usa
        _last_known_party) -- para esta página, sí importa que el
        dato esté fresco (por ejemplo, un Pokémon que acaba de
        subir de nivel). Devuelve None si el slot está vacío o la
        lectura falla.

        Bug real (03/09/2026, confirmado con traceback real del
        usuario cambiando de juego): a diferencia de read_party()
        (usado por Runtime, que solo llama a esto cuando ya sabe
        que hay conexión activa), esta página lo pide bajo demanda
        desde la GUI sin ese chequeo previo -- si el socket UDP se
        resetea justo en ese momento (típico al cerrar un
        emulador o cambiar de juego), read_party_order() deja
        pasar la excepción sin capturarla, y como esto se llama
        una vez POR CADA uno de los 6 slots, page_data() entero
        fallaba y la página quedaba vacía. Se captura acá (no en
        read_party_order() en sí, para no tocar código ya
        estable que usa el Runtime) y se trata como una lectura
        fallida más, igual que READ_FAILED.
        """

        try:
            pointers = self.read_party_order()
        except OSError as error:
            print(
                f"[AzaharReader] read_pokemon_raw_for_slot: "
                f"lectura UDP fallida (conexion probablemente "
                f"reiniciandose): {error}"
            )
            return None

        if len(pointers) != 6 or not (1 <= slot <= 6):
            return None

        pointer = pointers[slot - 1]

        try:
            pokemon = self.read_pokemon(pointer)
        except OSError as error:
            print(
                f"[AzaharReader] read_pokemon_raw_for_slot: "
                f"lectura UDP fallida (conexion probablemente "
                f"reiniciandose): {error}"
            )
            return None

        if pokemon is READ_FAILED or pokemon is None:
            return None

        return pokemon

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

        # Mismo bug real que ya se encontró en read_party_order()
        # (03/09/2026) y el mismo fix: self.memory.read() puede
        # devolver None (no solo lanzar una excepción), y
        # len(None) tira TypeError en vez de "no es válido".
        if data is None or len(data) != 4:
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

        # Multi-version (30/08/2026): CURRENT_ZONE_ID_ADDRESS
        # NO es la misma entre Alpha Sapphire y Omega Ruby
        # (confirmado -- ver get_current_zone_id_address() en
        # pointers.py). Se elige segun self.process_name, mismo
        # criterio que ya usa read_party_order()/read_box().
        zone_address = get_current_zone_id_address(
            self.process_name
        )

        data = self.memory.read(
            zone_address,
            1
        )

        # Ídem read_total_caught_count()/read_party_order(): data
        # puede ser None, no solo tener la longitud equivocada.
        if data is None or len(data) != 1:
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

        # Multi-version (30/08/2026): BOX_BASE_ADDRESS NO es la
        # misma entre Alpha Sapphire y Omega Ruby (confirmado --
        # ver get_box_base_address() en pointers.py). Se elige
        # segun self.process_name, mismo criterio que ya usa
        # read_party_order().
        box_base_address = get_box_base_address(
            self.process_name
        )

        window_size = (
            BOX_SLOT_COUNT
            * BOX_SLOT_STRIDE
        )

        # Bug real (03/09/2026, confirmado con traceback real del
        # usuario: TimeoutError que tiró abajo el hilo entero del
        # Runtime): esta lectura, a diferencia de las demás del
        # ciclo realtime, no tenía ninguna protección contra un
        # fallo transitorio del socket UDP (timeout/reset típico
        # al cerrar o cambiar de emulador) -- read_box() se llama
        # directo desde Runtime.update(), sin ningún try/except
        # alrededor en ese nivel tampoco, así que la excepción
        # mataba el thread de background completo (medallas,
        # party, combate, Nuzlocke: todo dejaba de actualizarse en
        # silencio hasta reiniciar la app entera). Se trata igual
        # que cualquier otra lectura fallida: lista vacía por este
        # ciclo, se reintenta solo en el próximo.
        try:
            data = self.memory.read(
                box_base_address,
                window_size
            )
        except OSError as error:
            print(
                f"[AzaharReader] read_box: lectura UDP fallida "
                f"(conexion probablemente reiniciandose): {error}"
            )
            return []

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

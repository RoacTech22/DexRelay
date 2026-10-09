import socket
import struct

from app.readers.citra import Citra
from app.readers.base import EmulatorTransport  # noqa: F401 -- tipo del transporte
from app.memory.memory_reader import MemoryReader
from app.memory.structures import (
    SLOT_DATA_SIZE,
    STAT_DATA_OFFSET,
    STAT_DATA_SIZE,
)

# Tabla de orden del equipo: 6 punteros u32; cada puntero apunta al
# Pokémon menos 0x40. Igual en ORAS y X/Y (confirmado en vivo).
ORDER_ENTRY_SIZE = 4
POKEMON_POINTER_OFFSET = 0x40
from app.games.registry import (
    get_profile,
    process_names,
    recognized_title_name,
)
from app.memory.structures import Pokemon6, decrypt_data
from app.services.location_resolver import LocationResolver
from app.services.species_resolver import SpeciesResolver


# Todos los juegos que DexRelay sabe leer hoy. Usado para el modo
# "automático" (self.process_name = None -- ver find_game_process())
# y para detect_process_name(), que solo mira sin conectarse (GUI
# v2, 02/09/2026: Bienvenida sin selección manual + botón
# "Reiniciar" del Reader que detecta un cambio de juego).
#
# Bloque 11 (ruta multijuego): sale del registro de perfiles (los
# juegos de Azahar con perfil), en vez de listarse a mano acá.
KNOWN_PROCESS_NAMES = process_names(reader_kind="azahar")


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
        citra: "EmulatorTransport | None" = None,
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

        # True solo después de que connect() eligió (set_process) el
        # proceso del juego en ESTA conexión con Azahar. Bug real
        # (18/09/2026, reportado por el usuario): cerrar Azahar por
        # completo con DexRelay abierto y volver a abrirlo con el
        # juego dejaba a DexRelay sin detectarlo hasta reiniciarlo.
        # Causa: en modo automático `process_name` queda fijado tras
        # la primera detección, y un Azahar nuevo puede reportar
        # cualquier proceso como "seleccionado" en get_process() --
        # is_connected() daba True sin que connect() volviera a
        # hacer set_process() del juego, y toda lectura iba a un
        # proceso equivocado. Ahora una conexión solo cuenta como
        # válida si la seleccionó connect() y sigue siendo la misma.
        self._process_selected = False

    # ------------------------------------------------------------
    # Perfil del juego (Bloque 12, ruta multijuego, 04/10/2026)
    # ------------------------------------------------------------
    #
    # Antes, cada lectura elegía su dirección con un getter de
    # pointers.py que, ante un juego desconocido, caía en SILENCIO a
    # las direcciones de Alpha Sapphire. Ahora todas salen del perfil
    # del juego conectado (app/games/): si el juego no tiene perfil, o
    # ese campo del mapa no está confirmado (None), la lectura se
    # trata como fallida -- nunca se lee memoria con direcciones de
    # otro juego (regla 4 del Documento Maestro).

    @property
    def profile(self):
        """Perfil del juego actual, o None si no hay uno soportado."""
        return get_profile(self.process_name)

    def _field(self, name):
        """Campo del MemoryMap del juego actual, o None si no existe."""
        profile = self.profile

        if profile is None:
            return None

        return getattr(profile.memory_map, name)

    def _box_geometry(self):
        """(base, stride, slots_por_caja) o None si falta alguno."""
        base = self._field("box_base_address")
        stride = self._field("box_slot_stride")
        slots = self._field("box_slot_count")

        if base is None or stride is None or slots is None:
            return None

        return base, stride, slots

    def _box_address(self, box_index):
        """Dirección de la caja `box_index` (1-based), o None."""
        geometry = self._box_geometry()

        if geometry is None:
            return None

        base, stride, slots = geometry

        return base + (box_index - 1) * slots * stride

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

    # Estados que devuelve diagnose_connection() -- constantes para
    # que Api/GUI/tests no dependan de strings sueltos.
    DIAG_NO_LISTENER = "no_listener"
    DIAG_TIMEOUT = "timeout"
    DIAG_ERROR = "error"
    DIAG_NO_GAME = "no_game"
    # Azahar tiene cargado un Pokémon que DexRelay reconoce (por Title
    # ID) pero que todavía no tiene perfil de lectura.
    DIAG_UNSUPPORTED_GAME = "unsupported_game"
    DIAG_GAME_FOUND = "game_found"

    def diagnose_connection(self):
        """
        Bloque 6.2 (guía siguiente versión, 23/09/2026): distingue,
        con lo que Azahar REALMENTE contesta, por qué DexRelay no
        conecta -- para la pantalla de Espera, que hasta ahora solo
        decía "buscando" sin importar la causa. Solo mira
        (process_list()), no selecciona ni cambia nada de la
        conexión.

        Devuelve un dict con "state":

        - DIAG_NO_LISTENER: nadie escucha en el puerto UDP (en
          Windows el sistema devuelve un reset de conexión al
          instante). Azahar cerrado o su interfaz de depuración
          por UDP deshabilitada -- desde acá NO se pueden
          distinguir esas dos, y la GUI no debe fingir que sí.
        - DIAG_TIMEOUT: se mandó el pedido y nadie contestó en el
          plazo del socket (2s).
        - DIAG_ERROR: cualquier otro fallo de comunicación
          ("detail" trae el texto real).
        - DIAG_NO_GAME: Azahar contestó pero no hay ningún juego
          conocido; "processes" lista los nombres que SÍ reportó
          (dato real, puede venir vacío).
        - DIAG_UNSUPPORTED_GAME: Azahar contestó y hay un Pokémon
          reconocido por Title ID ("game_name") pero sin perfil de
          lectura todavía (Bloque 12, ruta multijuego).
        - DIAG_GAME_FOUND: Azahar contestó y hay un juego conocido
          ("process_name").

        Nunca lanza excepciones hacia el llamador.
        """

        try:
            processes = self.citra.process_list()
        except (ConnectionResetError, ConnectionRefusedError):
            return {"state": self.DIAG_NO_LISTENER}
        except (socket.timeout, TimeoutError):
            return {"state": self.DIAG_TIMEOUT}
        except OSError as error:
            return {"state": self.DIAG_ERROR, "detail": str(error)}
        except Exception as error:
            return {"state": self.DIAG_ERROR, "detail": str(error)}

        names = sorted(
            {name for _title_id, name in processes.values()}
        )

        for name in names:
            if name in KNOWN_PROCESS_NAMES:
                return {
                    "state": self.DIAG_GAME_FOUND,
                    "process_name": name,
                    "processes": names,
                }

        for title_id, name in processes.values():
            game_name = recognized_title_name(title_id)

            if game_name is not None:
                return {
                    "state": self.DIAG_UNSUPPORTED_GAME,
                    "process_name": name,
                    "game_name": game_name,
                    "processes": names,
                }

        return {"state": self.DIAG_NO_GAME, "processes": names}

    def connect(self):
        """
        Busca sango-2 y lo selecciona
        como proceso activo.

        Si Azahar no está disponible o la comunicación
        falla durante la búsqueda, se considera
        desconectado y se reintentará en la siguiente
        actualización.
        """

        self._process_selected = False

        try:
            process_id = (
                self.find_game_process()
            )

            if process_id is None and self.process_name is not None:
                # Sesión nueva de Azahar con OTRO juego conocido
                # (ej. estaba Alpha Sapphire y se abrió Omega Ruby
                # después de cerrar todo): no quedarse esperando
                # para siempre el nombre de la sesión anterior.
                # Application._sync_nuzlocke_storage() re-sincroniza
                # el Nuzlocke Tracker solo al ver el cambio.
                other_name = self.detect_process_name()

                if (
                    other_name is not None
                    and other_name != self.process_name
                ):
                    self.process_name = other_name
                    self.title_id = None
                    process_id = self.find_game_process()

            if process_id is None:
                return False

            self.citra.set_process(
                process_id
            )

            self.process_id = process_id
            self._process_selected = True

            return True

        except Exception:
            return False

    def invalidate_connection(self):
        """
        Olvida la conexión actual para que el próximo
        is_connected() dé False y Runtime vuelva a pasar por
        connect() (find_game_process + set_process). Usado por
        Runtime cuando la conexión "parece" activa pero no llega
        ningún dato (proceso seleccionado equivocado).
        """

        self._process_selected = False
        self.process_id = None
        self.title_id = None

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

            if connected and not self._process_selected:
                # Azahar reporta un proceso, pero NO lo eligió
                # connect() en esta conexión (Azahar recién
                # reabierto, o reconexión tras un corte) -- puede
                # ser cualquier proceso, no necesariamente el juego.
                connected = False

            if (
                connected
                and self.process_id is not None
                and process_id != self.process_id
            ):
                # El proceso seleccionado cambió por debajo
                # (juego relanzado dentro del mismo Azahar).
                connected = False

            if connected:
                self.process_id = process_id

                if self.title_id is None:
                    self._refresh_title_id()

            return connected

        except Exception:
            # Azahar cerrado / sin respuesta: la conexión anterior
            # ya no vale, hay que volver a seleccionar el juego.
            self._process_selected = False
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

        party_order_address = self._field("party_order_address")

        party_count_address = self._field("party_count_address")

        if party_order_address is None or party_count_address is None:
            return []

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
        read_wild_rival_copy() (copia del rival salvaje).

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
        pokemon,
        box_index=None
    ):
        """
        Convierte Pokemon6 en el formato
        de datos utilizado por DexRelay.

        `box_index` (08/09/2026, roadmap 5.2/5.3) es opcional --
        `None` para los slots de party (llamado desde
        read_party()/read_pokemon_raw_for_slot(), donde no hay
        concepto de "caja"), o el número de caja 1-based cuando el
        origen es una Caja PC (ver _parse_box_slots() más abajo).
        Se propaga en el dict de salida para que la pestaña
        "General"/"Caja" de la página Pokémon (Api.get_boxes_
        overview()/get_box_page_data() en api.py) pueda agrupar
        los slots devueltos por lote (ej. read_boxes_range()) sin
        tener que adivinar de qué caja salió cada uno.
        """

        if pokemon is None:

            return {
                "slot": slot,
                "boxIndex": box_index,
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
                "genderId": None,
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

        # Bug real corregido (05/09/2026, reformulado 07/09/2026):
        # pokemon.level() lee un offset que solo existe en el
        # bloque extra de stats que agrega read_pokemon() para la
        # party -- read_box() no lo tiene (ver su docstring), así
        # que para una captura que va directo a la Caja PC
        # pokemon.level() siempre da 0.
        #
        # El respaldo (PKHeX, CurrentLevel calculado a partir de
        # la experiencia) YA NO sale de location_info -- ver el
        # docstring de LocationResolver.resolve_current_level()
        # para el bug real que corrigió sacarlo de ahí (nivel
        # congelado para siempre en cuanto se cacheaba la
        # resolución de lugar de encuentro). Se pide fresco, sin
        # caché, cada vez que hace falta -- solo pasa para slots
        # de Caja PC, la party siempre tiene el nivel real directo.
        level = pokemon.level()

        if not level:
            level = self.location_resolver.resolve_current_level(
                pokemon.raw_data[:232]
            )

        return {
            "slot": slot,
            "boxIndex": box_index,
            "empty": species_id == 0,
            "nickname": nickname,
            "species": species,
            "speciesId": species_id,
            "level": level,
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
            # Ícono de género en el Nuzlocke Tracker (05/09/2026, a
            # pedido del usuario) -- mismo campo que location_info
            # ya trae de PKHeX (sin golpear el bridge de nuevo), se
            # propaga para que _register_new_capture() lo guarde
            # en roster/graveyard/pending_encounters.
            "genderId": location_info.get("genderId"),
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
        Api.get_pokemon_page_data() en app/gui_web/api_pokemon.py).

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

    def read_wild_rival_copy(self):
        """
        Lee la copia del Pokémon rival salvaje (wild_rival_copy_address del perfil): la dirección fija
        que contiene el Pokémon capturado más recientemente, incluso
        si fue directo a la Caja PC porque la party estaba llena
        (en ese caso nunca aparece en read_party()).

        Devuelve el mismo formato que build_pokemon_data(), o None
        si la lectura falló (transitoriamente, o si nunca hubo
        ninguna captura todavía en esta partida -- la estructura
        vacía se descarta igual que un slot de party vacío).
        """

        wild_rival_copy_address = self._field("wild_rival_copy_address")

        if wild_rival_copy_address is None:
            return None

        pokemon = self._read_pokemon_at_address(
            wild_rival_copy_address
        )

        if pokemon is READ_FAILED:
            return None

        if pokemon is None:
            return None

        return self.build_pokemon_data(
            0,
            pokemon
        )

    def read_wild_rival_species(self):
        """
        Especie (nombre) del Pokémon rival de un combate salvaje, o
        None si ninguna dirección candidata tiene un PK6 válido
        (ver _WILD_RIVAL_ADDRESSES_BY_PROCESS en pointers.py).

        Lectura liviana a propósito (se llama cada ciclo mientras
        dura un combate salvaje): solo lee los 232 bytes, valida el
        checksum PK6 y resuelve el nombre -- sin pasar por PKHeX ni
        armar el dict completo de build_pokemon_data().

        Maneja los dos fallos de siempre: excepción de UDP Y valor
        None devuelto sin lanzar nada.
        """

        for address in (self._field("wild_rival_addresses") or ()):

            try:
                data = self.memory.read(address, SLOT_DATA_SIZE)
            except OSError:
                continue

            if data is None or len(data) != SLOT_DATA_SIZE:
                continue

            if all(byte == 0 for byte in data[:8]):
                continue

            decrypted = decrypt_data(data)

            if not decrypted:
                continue

            species_id = struct.unpack("<H", decrypted[0x08:0x0A])[0]

            if not 1 <= species_id <= 721:
                continue

            species = self.species_resolver.resolve(species_id)

            if species:
                return species

        return None

    def read_total_caught_count(self):
        """
        Lee TOTAL_CAUGHT_ADDRESS (ver get_total_caught_address() en
        pointers.py -- por proceso desde el 10/09/2026, bug real:
        el valor viejo, único para las dos versiones, había quedado
        sin migrar a Alpha Sapphire 1.4 y siempre leía 0): sube en
        exactamente 1 cada vez que se captura un Pokémon real
        (equipo o Caja PC, sin contar al inicial). Se usa como
        confirmación de que read_wild_rival_copy() refleja una captura
        de verdad, y no solo un encuentro salvaje sin capturar (ver
        Documento Maestro, investigación del 25/08/2026).

        Devuelve el valor entero, o None si la lectura falló.
        """

        total_caught_address = self._field("total_caught_address")

        if total_caught_address is None:
            return None

        data = self.memory.read(
            total_caught_address,
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
        zone_address = self._field("current_zone_id_address")

        if zone_address is None:
            return None

        # Bloque 15: el ancho sale del perfil (ORAS: 1 byte; X/Y: u16).
        width = self._field("current_zone_id_width") or 1

        data = self.memory.read(
            zone_address,
            width
        )

        # Ídem read_total_caught_count()/read_party_order(): data
        # puede ser None, no solo tener la longitud equivocada.
        if data is None or len(data) != width:
            return None

        return int.from_bytes(data, "little")

    def read_has_pokeballs(self):
        """
        Bloque 4.4 (guía siguiente versión, 23/09/2026): ¿tiene el
        jugador al menos una Poké Ball de cualquier tipo en la
        bolsa ahora mismo? Usado para detectar el inicio real de un
        Nuzlocke -- antes de conseguir las primeras Poké Balls, los
        encuentros/muertes no deberían contar para el tracker (ver
        NuzlockeService, flag `nuzlocke_started`).

        Escanea el bolsillo de Objetos completo (confirmado en vivo
        que las Poké Balls viven mezcladas ahí, NO en un bolsillo
        propio -- ver get_items_pocket_start_address() en
        pointers.py) buscando cualquier casillero cuyo item_id esté
        en POKEBALL_ITEM_IDS con cantidad > 0. Solo lectura, una
        sola lectura UDP para las 400 casilleros.

        Devuelve True/False, o None si la lectura falló (mismo
        criterio que el resto de los read_* -- nunca asumir "no
        tiene" ante una lectura fallida, para no marcar
        nuzlocke_started en falso por un problema transitorio de
        conexión).
        """

        pocket_start = self._field("items_pocket_start_address")
        slot_count = self._field("items_pocket_slot_count")
        pokeball_ids = self._field("pokeball_item_ids")

        if pocket_start is None or slot_count is None or pokeball_ids is None:
            return None

        slot_size = 4
        size = slot_count * slot_size

        data = self.memory.read(pocket_start, size)

        if data is None or len(data) != size:
            return None

        for offset in range(0, size, slot_size):
            item_id, quantity = struct.unpack(
                "<HH", data[offset:offset + slot_size]
            )

            if item_id in pokeball_ids and quantity > 0:
                return True

        return False

    def read_fossil_item_count(self):
        """
        P3 (paridad X/Y, 06/10/2026): cuántos fósiles hay en total en
        el bolsillo de Objetos (suma de las cantidades de los objetos
        de `special_rules.fossil_item_ids` del perfil). El servicio
        del Nuzlocke detecta un fósil revivido cuando esta cantidad
        baja y poco después aparece un Pokémon nuevo del lugar del
        laboratorio. Solo lectura, una UDP para los 400 casilleros.

        None si el juego no usa esta señal (ORAS), si falta el
        bolsillo en el perfil o si la lectura falló (nunca se asume 0
        ante una lectura fallida: una "baja" falsa marcaría fósil a
        la siguiente captura).
        """

        profile = getattr(self, "profile", None)

        if profile is None:
            return None

        fossil_ids = profile.content.special_rules.fossil_item_ids

        if not fossil_ids:
            return None

        pocket_start = self._field("items_pocket_start_address")
        slot_count = self._field("items_pocket_slot_count")

        if pocket_start is None or slot_count is None:
            return None

        size = slot_count * 4

        data = self.memory.read(pocket_start, size)

        if data is None or len(data) != size:
            return None

        total = 0

        for offset in range(0, size, 4):
            item_id, quantity = struct.unpack("<HH", data[offset:offset + 4])

            if item_id in fossil_ids:
                total += quantity

        return total

    def read_trainer_identity(self):
        """
        Bloque 5 (guía siguiente versión, 24/09/2026): identifica QUÉ
        partida está cargada leyendo la tarjeta de entrenador en RAM
        (ver TRAINER_CARD_ADDRESS en pointers.py, confirmada en vivo
        con dos partidas de dos juegos distintos). Solo lectura, una
        UDP de TRAINER_CARD_READ_SIZE bytes.

        Devuelve {"tid": int, "sid": int, "ot": str} o `None` si la
        lectura falló o el contenido no parece una tarjeta real
        (nombre vacío o con caracteres no imprimibles, o TID y SID
        ambos en 0) -- por ejemplo con el juego todavía en el menú
        antes de cargar una partida. Nunca inventa una identidad ante
        una lectura dudosa; el llamador decide qué hacer con `None`.
        """

        address = self._field("trainer_card_address")
        read_size = self._field("trainer_card_read_size")
        id_offset = self._field("trainer_card_id_offset")
        name_offset = self._field("trainer_card_name_offset")
        name_bytes = self._field("trainer_card_name_bytes")

        if None in (address, read_size, id_offset, name_offset, name_bytes):
            return None

        try:
            data = self.memory.read(address, read_size)
        except OSError:
            return None

        if data is None or len(data) != read_size:
            return None

        tid, sid = struct.unpack_from(
            "<HH", data, id_offset
        )

        raw_name = data[
            name_offset:
            name_offset + name_bytes
        ]

        try:
            name = raw_name.decode("utf-16le").split("\x00", 1)[0]
        except UnicodeDecodeError:
            return None

        if not name or not name.isprintable():
            return None

        if tid == 0 and sid == 0:
            return None

        return {"tid": tid, "sid": sid, "ot": name}

    def read_box(self, box_index=1):
        """
        Escanea UNA caja PC completa (por defecto la Caja 1):
        BOX_SLOT_COUNT slots de BOX_SLOT_STRIDE bytes cada uno, a
        partir de get_box_address(process_name, box_index) -- ver
        pointers.py para el detalle de qué cajas están confirmadas
        empíricamente hoy (1-7, ver Documento Maestro 07/09/2026).

        `box_index` es 1-based, igual que get_box_address() y que la
        numeración que ve el usuario en el juego (07/09/2026,
        extendido desde la versión original que solo leía la Caja 1
        -- pensado para que la futura pestaña "Caja" de la página
        Pokémon pueda pedir cualquiera de las 7 sueltas, una por
        vez, sin cargar las demás).

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
        resultado -- el nivel real se resuelve aparte vía
        LocationResolver.resolve_current_level() cuando hace falta
        (ver su docstring).

        Devuelve una lista con SOLO los slots ocupados (checksum
        válido) en el mismo formato que build_pokemon_data(). Los
        slots vacíos o con lectura fallida se omiten directamente
        -- a diferencia de read_party(), nada en el proyecto
        necesita ver los 30 slots completos, solo cuáles hay.
        Lista vacía si la lectura de memoria falló por completo.
        """

        data = self.read_box_raw(box_index)

        if data is None:
            return []

        return self._parse_box_slots(data, box_index)

    def read_box_raw(self, box_index=1):
        """
        Lee el bloque crudo COMPLETO de una caja (BOX_SLOT_COUNT
        slots de BOX_SLOT_STRIDE bytes cada uno) SIN parsear --
        extraído de read_box() (08/09/2026, roadmap 5.2/5.3) para
        reusar la misma lectura de memoria en read_box_slot_raw(),
        sin duplicar el manejo de dirección/tamaño/errores.

        Devuelve los bytes crudos (aún sin descifrar -- eso lo hace
        Pokemon6 más adelante) o `None` si la lectura falló o vino
        incompleta.
        """

        box_base_address = self._box_address(box_index)
        geometry = self._box_geometry()

        if box_base_address is None or geometry is None:
            return None

        _base, box_slot_stride, box_slot_count = geometry

        window_size = (
            box_slot_count
            * box_slot_stride
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
                f"[AzaharReader] read_box_raw: lectura UDP fallida "
                f"(conexion probablemente reiniciandose): {error}"
            )
            return None

        if not data:
            return None

        if len(data) != window_size:
            return None

        return data

    def read_box_slot_raw(self, box_index, slot):
        """
        Lee y descifra el Pokemon6 completo de UN slot puntual de
        UNA caja (232 bytes "box format") -- roadmap 5.3, pestaña
        "Caja" de la página Pokémon: mismo motivo que
        read_pokemon_raw_for_slot() para la party (golpear el
        bridge PKHeX para tipos/habilidad/naturaleza/stats de
        combate/movimientos es demasiado para pedirlo de las 30
        cajas x 31 en cada poll de fondo -- se pide bajo demanda,
        solo del slot puntual que el usuario abre).

        A diferencia de read_box()/read_box_raw() (que traen la
        caja ENTERA), esto solo golpea la memoria por el slot que
        hace falta -- no tiene sentido traer los 30 slots para
        resolver el detalle de uno solo.

        `box_index`/`slot` son 1-based, igual que get_box_address()
        y el "slot" que devuelve build_pokemon_data(). Devuelve los
        232 bytes ya descifrados, o `None` si la lectura falló, el
        slot está fuera de rango, o el slot está vacío/con checksum
        inválido.
        """

        geometry = self._box_geometry()

        if geometry is None:
            return None

        _base, box_slot_stride, box_slot_count = geometry

        if not (1 <= slot <= box_slot_count):
            return None

        box_base_address = self._box_address(box_index)

        slot_address = (
            box_base_address
            + (slot - 1) * box_slot_stride
        )

        try:
            chunk = self.memory.read(
                slot_address,
                SLOT_DATA_SIZE
            )
        except OSError as error:
            print(
                f"[AzaharReader] read_box_slot_raw: lectura UDP "
                f"fallida (conexion probablemente "
                f"reiniciandose): {error}"
            )
            return None

        if not chunk or len(chunk) != SLOT_DATA_SIZE:
            return None

        pokemon = Pokemon6(chunk)

        if not pokemon.raw_data:
            return None

        return pokemon.raw_data[:232]

    def read_boxes_range(self, start_box_index=1, box_count=7):
        """
        Escanea VARIAS cajas PC contiguas de una sola vez -- una
        sola lectura UDP en vez de `box_count` llamadas separadas
        (07/09/2026, agregado para el Nuzlocke Tracker: antes solo
        se escaneaba la Caja 1 para detectar capturas nuevas, así
        que una captura depositada directo en la Caja 2+ -- algo
        que pasa apenas se llena la Caja 1 -- nunca se registraba).

        Aprovecha que las cajas están confirmadas contiguas sin
        padding (ver get_box_address() en pointers.py): pedir de
        una sola vez el bloque completo de `box_count` cajas es
        exactamente tan válido como leerlas una por una, pero con
        una sola ida y vuelta UDP en vez de varias por ciclo.

        `start_box_index`/`box_count` son 1-based, igual que
        get_box_address() -- el default (1, 7) cubre las 7 cajas
        que trae el juego habilitadas de fábrica (ver Documento
        Maestro 07/09/2026: comprar más es opcional, no todos los
        Nuzlocke lo necesitan, así que no tiene sentido escanear
        más allá de esto por defecto).

        Devuelve una lista combinada de SOLO los slots ocupados de
        TODAS las cajas leídas, mismo formato que read_box() --
        quien la use no necesita saber de qué caja puntual salió
        cada Pokémon (el Nuzlocke Tracker identifica por nickname,
        no por ubicación de caja). Lista vacía si la lectura falló
        por completo.
        """

        box_base_address = self._box_address(start_box_index)
        geometry = self._box_geometry()

        if box_base_address is None or geometry is None:
            return []

        _base, box_slot_stride, box_slot_count = geometry
        box_block_size = box_slot_count * box_slot_stride

        window_size = (
            box_count
            * box_block_size
        )

        try:
            data = self.memory.read(
                box_base_address,
                window_size
            )
        except OSError as error:
            print(
                f"[AzaharReader] read_boxes_range: lectura UDP "
                f"fallida (conexion probablemente "
                f"reiniciandose): {error}"
            )
            return []

        if not data:
            return []

        if len(data) != window_size:
            return []

        occupied = []

        for box_offset in range(box_count):

            box_start = box_offset * box_block_size

            box_chunk = data[
                box_start:
                box_start + box_block_size
            ]

            occupied.extend(
                self._parse_box_slots(
                    box_chunk,
                    start_box_index + box_offset,
                )
            )

        return occupied

    def _parse_box_slots(self, data, box_index):
        """
        Parsea el bloque crudo de UNA caja (BOX_SLOT_COUNT slots de
        BOX_SLOT_STRIDE bytes) ya leído de memoria, y devuelve solo
        los slots ocupados en formato build_pokemon_data() (07/09/2026,
        extraído de read_box() para compartirlo también con
        read_boxes_range() -- misma lógica de parseo, no reimplementada
        aparte).

        `box_index` solo se usa para loguear/depurar si hiciera
        falta a futuro -- el "slot" que lleva build_pokemon_data()
        sigue siendo el número de slot DENTRO de la caja (1-30), no
        un índice global, mismo criterio que ya usaba read_box().
        """

        occupied = []

        geometry = self._box_geometry()

        if geometry is None:
            return occupied

        _base, box_slot_stride, box_slot_count = geometry

        for slot_index in range(box_slot_count):

            start = (
                slot_index
                * box_slot_stride
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
                    pokemon,
                    box_index
                )
            )

        return occupied


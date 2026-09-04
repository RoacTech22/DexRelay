import time
from threading import Thread

from app.core.config import Config
from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.server.http_server import HTTPServer
from app.services.location_catalog import LocationCatalog
from app.services.nuzlocke_service import NuzlockeService
from app.services.nuzlocke_storage import NuzlockeStorage
from app.services.species_catalog import SpeciesCatalog


class Application:
    def __init__(self):
        self.config = Config()
        self.state = ApplicationState()

        process_name = self.config.get(
            "azahar",
            "process_name",
            default="sango-2",
        )

        self.reader = AzaharReader(
            process_name=process_name,
        )

        # Instancia única, compartida entre Runtime (que lee/escribe
        # roster y graveyard cada ciclo realtime) y HTTPServer (que
        # necesita escribir encuentros desde el panel de control) --
        # ambos deben trabajar sobre los mismos datos en memoria,
        # no sobre copias independientes que se pisarían entre sí.
        #
        # NuzlockeStorage.for_game() (02/09/2026): antes había un
        # solo data/nuzlocke.json sin importar qué juego estuviera
        # corriendo -- bug real reportado por el usuario,
        # /overlay/nuzlocke mostraba la partida de Omega Ruby con
        # Alpha Sapphire abierto. Ahora cada juego tiene su propio
        # archivo. `_nuzlocke_game` guarda a qué juego está
        # sincronizado ahora mismo -- update() lo revisa cada ciclo
        # (ver _sync_nuzlocke_storage()) para mantenerlo al día
        # incluso en una conexión normal/automática, no solo cuando
        # se toca "Reiniciar" a mano.
        self._nuzlocke_game = process_name

        self.nuzlocke_service = NuzlockeService(
            NuzlockeStorage.for_game(process_name)
        )

        self.runtime = Runtime(
            self.reader,
            self.state,
            nuzlocke_service=self.nuzlocke_service,
        )

        refresh_ms = self.config.get(
            "realtime",
            "refresh_ms",
            default=200,
        )

        self.refresh_seconds = max(
            0.001,
            float(refresh_ms) / 1000.0,
        )

        server_host = self.config.get(
            "server",
            "host",
            default="127.0.0.1",
        )

        server_port = self.config.get(
            "server",
            "port",
            default=8080,
        )

        self.http_server = HTTPServer(
            state=self.state,
            host=server_host,
            port=int(server_port),
            nuzlocke_service=self.nuzlocke_service,
            species_catalog=SpeciesCatalog(),
            location_catalog=LocationCatalog(),
        )

        # Runtime (Runtime.update() en su propio hilo) y HTTPServer
        # ahora se controlan por separado -- pedido del usuario
        # (01/09/2026) para poder detener/iniciar cada uno desde el
        # Dashboard (GUI v2) sin afectar al otro. Antes había un
        # solo `self.running` que gobernaba los dos juntos; ese
        # nombre se mantiene como propiedad de solo lectura (ver
        # más abajo) para no romper todo el código que ya lo lee
        # (Api, app.js, window.py) -- ahora es `True` si CUALQUIERA
        # de los dos está activo, no los dos a la vez.
        self._runtime_active = False
        self._http_active = False

        # Marca de tiempo (time.monotonic()) de cuando arrancó el
        # Runtime -- usado para el "Uptime" de la tarjeta RUNTIME
        # del Dashboard. monotonic() en vez de time.time() porque
        # no importa la hora de reloj, solo cuánto tiempo pasó.
        self._runtime_started_at = None

        # Hilo del loop realtime (Runtime.update()). Corre
        # separado del hilo principal, igual que HTTPServer ya
        # corre en el suyo, para que el hilo principal quede
        # libre para la GUI (pywebview espera correr su propio
        # mainloop bloqueante en el hilo principal).
        #
        # Modelo de concurrencia elegido: threads, no asyncio.
        # Motivo: HTTPServer ya usa threads (es continuar el
        # patron existente, no uno nuevo), y las GUI de escritorio
        # en Python se integran mucho mas naturalmente con threads
        # + estado compartido que con asyncio. Documentado en el
        # Documento Maestro, seccion 18.
        self._runtime_thread = None

    @property
    def running(self):
        """
        `True` si CUALQUIERA de los dos subsistemas (Runtime o
        HTTPServer) está activo -- mantenido como propiedad de
        solo lectura porque `Api`, `app.js` y `window.py` ya lo
        leen así (sección "RUNNING"/"DETENIDO" del sidebar, cierre
        de ventana, etc.). Para saber el estado de cada uno por
        separado, usar `runtime_running`/`http_running`.
        """

        return self._runtime_active or self._http_active

    @property
    def runtime_running(self):
        return self._runtime_active

    @property
    def http_running(self):
        return self._http_active

    def start(self):
        """
        Arranca los dos subsistemas juntos -- lo que hace la
        pantalla de Espera al elegir versión y conectar. Para
        control independiente desde el Dashboard, ver
        `start_runtime()`/`start_http_server()`.
        """

        print("Iniciando DexRelay...")
        print("Configuración cargada correctamente.")

        self.start_http_server()
        self.start_runtime()

    def stop(self):
        """Detiene los dos subsistemas juntos (ver start())."""

        self.stop_runtime()
        self.stop_http_server()

        print("Deteniendo DexRelay.")

    # -----------------------------------------------------------
    # Control independiente -- Dashboard (GUI v2, 01/09/2026)
    # -----------------------------------------------------------

    def start_runtime(self):
        if self._runtime_active:
            return

        print(
            f"Runtime realtime iniciado "
            f"(refresh: {self.refresh_seconds * 1000:.0f} ms)."
        )

        self._runtime_active = True
        self._runtime_started_at = time.monotonic()

        self._runtime_thread = Thread(
            target=self._run_realtime_loop,
            name="DexRelayRuntime",
            daemon=True,
        )

        self._runtime_thread.start()

    def stop_runtime(self):
        if not self._runtime_active:
            return

        self._runtime_active = False
        self._runtime_started_at = None

        if self._runtime_thread is not None:
            self._runtime_thread.join(timeout=2.0)

        # Sin esto, `state.azahar_connected`/`reader_active`
        # quedan "pegados" en su último valor (True si estaba
        # conectado al frenar) -- nadie más los actualiza una vez
        # que el hilo del Runtime dejó de correr. Afecta tanto a
        # la GUI como a /api/status por igual, porque ambos leen
        # del mismo ApplicationState.
        self.state.azahar_connected = False
        self.state.reader_active = False

        print("Runtime detenido.")

    def start_http_server(self):
        if self._http_active:
            return

        self.http_server.start()
        self._http_active = True

    def stop_http_server(self):
        if not self._http_active:
            return

        self.http_server.stop()
        self._http_active = False

    def restart_reader(self):
        """
        "Reiniciar" del Reader (tarjeta READER del Dashboard).

        Dos cosas, en orden:

        1. Detecta si hay un juego CONOCIDO corriendo en Azahar
           distinto al configurado (`reader.process_name`) -- caso
           real reportado por el usuario (02/09/2026): cambiás de
           Alpha Sapphire a Omega Ruby sin cerrar DexRelay, y se
           queda "colgado" esperando el juego viejo para siempre,
           porque antes esto solo limpiaba process_id/title_id sin
           tocar qué nombre de proceso buscar. Si detecta un juego
           distinto, actualiza `process_name` (y lo guarda en
           config.json) y re-sincroniza el Nuzlocke Tracker al
           archivo de ESE juego (NuzlockeStorage.for_game()) -- sin
           esto, el Tracker seguiría mostrando la partida del juego
           anterior aunque la memoria ya se lea del nuevo.
        2. Limpia `process_id`/`title_id` cacheados para forzar una
           búsqueda nueva del proceso en el próximo ciclo, sea el
           mismo juego o uno distinto.

        No hace falta que el Runtime esté corriendo para llamar
        esto -- si está detenido, el reset queda listo para cuando
        se vuelva a iniciar.
        """

        detected_name = self.reader.detect_process_name()

        if (
            detected_name is not None
            and detected_name != self.reader.process_name
        ):
            self.reader.process_name = detected_name

            self.config.set(
                "azahar", "process_name", value=detected_name
            )
            self.config.save()

            self.nuzlocke_service.switch_storage(
                NuzlockeStorage.for_game(detected_name)
            )

        self.reader.process_id = None
        self.reader.title_id = None
        self.state.reader_active = False
        self.state.azahar_connected = False

    def update(self):
        self.runtime.update()
        self._sync_nuzlocke_storage()

    def _sync_nuzlocke_storage(self):
        """
        Mantiene el Nuzlocke Tracker apuntando al archivo del juego
        REALMENTE conectado -- se llama después de cada
        Runtime.update() (que es quien resuelve `reader.process_name`
        vía find_game_process() al conectar, incluso en modo
        automático).

        Bug real reportado el 02/09/2026: restart_reader() ya
        re-sincronizaba el storage, pero solo cuando el usuario
        tocaba el botón "Reiniciar" a mano -- en una conexión
        normal/automática (por ejemplo, "Salir" y volver a
        "Comenzar", que detecta el juego solo), nada re-sincronizaba
        el Nuzlocke Tracker, así que /overlay/nuzlocke seguía
        mostrando los datos del juego de la sesión anterior. Este
        chequeo corre cada ciclo (~200ms) pero es barato -- una
        comparación de strings; solo toca disco cuando el juego
        conectado realmente cambió.
        """

        current = self.reader.process_name

        if current is not None and current != self._nuzlocke_game:
            self._nuzlocke_game = current
            self.nuzlocke_service.switch_storage(
                NuzlockeStorage.for_game(current)
            )

    def _run_realtime_loop(self):
        """
        Ciclo realtime de DexRelay (Runtime.update() cada
        refresh_ms). Corre en su propio hilo -- ver nota en
        __init__ sobre el modelo de concurrencia elegido.

        Bug real y grave (03/09/2026, confirmado con traceback
        real: un TimeoutError sin capturar en read_box() mató el
        hilo completo -- "Exception in thread DexRelayRuntime" en
        la consola, y a partir de ahí TODO el ciclo realtime
        (party, medallas, combate, caja PC, Nuzlocke) dejaba de
        actualizarse en silencio, sin ningún aviso en la GUI, hasta
        reiniciar la aplicación entera). Cada método de lectura
        individual va ganando su propia protección contra fallos
        transitorios de socket a medida que aparecen (ver
        read_box()/read_pokemon_raw_for_slot() en azahar_reader.py
        para el mismo criterio) -- pero además de eso, ACÁ, en la
        raíz del hilo, se agrega una red de seguridad: async que
        aparezca un método sin esa protección todavía (los propios
        o alguno nuevo a futuro), el hilo ya no muere -- se
        registra el error y se sigue con el próximo ciclo, ni
        distinto de perder una sola lectura UDP.
        """

        next_update = time.monotonic()

        while self._runtime_active:
            try:
                self.update()
            except Exception as error:
                print(
                    f"[Application] Error no capturado durante "
                    f"el ciclo realtime (se ignora este ciclo, "
                    f"el Runtime sigue corriendo): {error}"
                )

            next_update += self.refresh_seconds
            sleep_time = next_update - time.monotonic()

            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_update = time.monotonic()

    def run(self):
        """
        Bloquea el hilo principal hasta que la aplicación se
        detenga.

        El trabajo real (Runtime realtime loop + HTTP server) ya
        corre en hilos de fondo iniciados por start(); este método
        solo mantiene vivo el proceso principal mientras tanto. No
        lo usa la GUI v2 (pywebview tiene su propio mainloop, ver
        app/gui_web/window.py) -- se mantiene por compatibilidad
        con cualquier modo headless/futuro.
        """

        if not self.running:
            self.start()

        while self.running:
            time.sleep(0.25)


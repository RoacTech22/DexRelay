import time
from threading import Thread

from app.core.config import Config
from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.server.http_server import HTTPServer
from app.services.nuzlocke_service import NuzlockeService
from app.services.nuzlocke_storage import NuzlockeStorage


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
        self.nuzlocke_service = NuzlockeService(
            NuzlockeStorage()
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
        )

        self.running = False

        # Hilo del loop realtime (Runtime.update()). Corre
        # separado del hilo principal, igual que HTTPServer ya
        # corre en el suyo, para que el hilo principal quede
        # libre para una futura GUI (los frameworks de GUI en
        # Python -- Tkinter, PyQt/PySide -- esperan correr su
        # propio mainloop bloqueante en el hilo principal).
        #
        # Modelo de concurrencia elegido: threads, no asyncio.
        # Motivo: HTTPServer ya usa threads (es continuar el
        # patron existente, no uno nuevo), y las GUI de escritorio
        # en Python se integran mucho mas naturalmente con threads
        # + estado compartido que con asyncio. Documentado en el
        # Documento Maestro, seccion 18.
        self._runtime_thread = None

    def start(self):
        print("Iniciando DexRelay...")
        print("Configuración cargada correctamente.")
        print(
            f"Refresh realtime: "
            f"{self.refresh_seconds * 1000:.0f} ms"
        )

        self.http_server.start()

        self.running = True

        self._runtime_thread = Thread(
            target=self._run_realtime_loop,
            name="DexRelayRuntime",
            daemon=True,
        )

        self._runtime_thread.start()

    def update(self):
        self.runtime.update()

    def _run_realtime_loop(self):
        """
        Ciclo realtime de DexRelay (Runtime.update() cada
        refresh_ms). Corre en su propio hilo -- ver nota en
        __init__ sobre el modelo de concurrencia elegido.
        """

        print("Runtime realtime iniciado.")

        next_update = time.monotonic()

        while self.running:
            self.update()

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
        solo mantiene vivo el proceso principal mientras tanto.
        Cuando exista la GUI (FASE 4), su mainloop reemplazará este
        bucle de espera -- el hilo principal ya queda libre para
        eso desde este cambio.
        """

        if not self.running:
            self.start()

        while self.running:
            time.sleep(0.25)

    def stop(self):
        if self.running:
            self.running = False

            if self._runtime_thread is not None:
                self._runtime_thread.join(
                    timeout=2.0
                )

            self.http_server.stop()
            print("Deteniendo DexRelay.")

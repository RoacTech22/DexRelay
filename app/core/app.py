import time

from app.core.config import Config
from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.server.http_server import HTTPServer


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
        self.runtime = Runtime(
            self.reader,
            self.state,
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
        )

        self.running = False

    def start(self):
        print("Iniciando DexRelay...")
        print("Configuración cargada correctamente.")
        print(
            f"Refresh realtime: "
            f"{self.refresh_seconds * 1000:.0f} ms"
        )

        self.http_server.start()

        self.running = True

    def update(self):
        self.runtime.update()

    def run(self):
        """Ejecuta el ciclo realtime de DexRelay hasta que se detenga."""

        if not self.running:
            self.start()

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

    def stop(self):
        if self.running:
            self.running = False
            self.http_server.stop()
            print("Deteniendo DexRelay.")

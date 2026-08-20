import time

from app.core.config import Config
from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader


class Application:
    def __init__(self):
        self.config = Config()
        self.state = ApplicationState()
        self.reader = AzaharReader()
        self.runtime = Runtime(
            self.reader,
            self.state,
        )

        refresh_ms = self.config.get(
            "realtime",
            "refresh_ms",
            default=200,
        )

        self.refresh_seconds = max(0.001, float(refresh_ms) / 1000.0)
        self.running = False

    def start(self):
        print("Iniciando DexRelay...")
        print("Configuración cargada correctamente.")
        print(f"Refresh realtime: {self.refresh_seconds * 1000:.0f} ms")
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
                # Si una actualización tarda demasiado, no acumulamos retraso.
                next_update = time.monotonic()

    def stop(self):
        if self.running:
            self.running = False
            print("Deteniendo DexRelay.")

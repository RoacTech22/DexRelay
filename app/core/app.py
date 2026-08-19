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

    def start(self):
        print("Iniciando DexRelay...")
        print("Configuración cargada correctamente.")

    def update(self):
        self.runtime.update()

    def stop(self):
        print("Deteniendo DexRelay.")

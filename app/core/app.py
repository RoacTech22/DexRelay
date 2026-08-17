from app.core.config import Config
from app.core.state import ApplicationState


class Application:
    def __init__(self):
        self.config = Config()
        self.state = ApplicationState()

    def start(self):
        print("Iniciando DexRelay...")
        print("Configuración cargada correctamente.")

    def stop(self):
        print("Deteniendo DexRelay.")
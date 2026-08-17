import json
import subprocess
from pathlib import Path


class PKHeXBridge:
    """
    Cliente Python para comunicarse con DexRelay.PKHeX.
    """

    def __init__(self):
        self.process = None

        self.project_directory = (
            Path(__file__)
            .resolve()
            .parents[3]
            / "dotnet"
            / "DexRelay.PKHeX"
        )

    def start(self):
        """
        Inicia el proceso .NET del bridge.
        """

        if self.process is not None:
            return

        self.process = subprocess.Popen(
            [
                "dotnet",
                "run",
                "--project",
                str(self.project_directory),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def request(self, payload):
        """
        Envía una petición JSON al bridge y
        devuelve la respuesta como diccionario.
        """

        if self.process is None:
            self.start()

        message = (
            json.dumps(payload)
            + "\n"
        )

        self.process.stdin.write(
            message
        )

        self.process.stdin.flush()

        response = (
            self.process.stdout.readline()
        )

        if not response:
            raise RuntimeError(
                "El bridge PKHeX no devolvió respuesta."
            )

        return json.loads(
            response
        )

    def species(self, species_id):
        """
        Obtiene el nombre de una especie.
        """

        return self.request(
            {
                "action": "species",
                "id": species_id,
            }
        )

    def stop(self):
        """
        Detiene el proceso del bridge.
        """

        if self.process is None:
            return

        if self.process.stdin:
            self.process.stdin.close()

        self.process.terminate()

        self.process.wait(
            timeout=5
        )

        self.process = None
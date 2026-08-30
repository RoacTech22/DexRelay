import json
import subprocess
from pathlib import Path

from app.core import paths


class PKHeXBridge:
    """
    Cliente Python para comunicarse con DexRelay.PKHeX.

    Detecta automáticamente si existe una publicación
    self-contained del bridge (FASE 6, 29/08/2026 -- ver
    Documento Maestro) en `releases/pkhex-bridge/` y, si está, la
    usa directamente (no depende de tener el SDK de .NET
    instalado). Si no está publicada todavía, cae al modo de
    desarrollo de siempre (`dotnet run --project ...`), así que
    seguir trabajando sobre el código C# sin publicar en cada
    cambio sigue andando igual que antes.

    Generar la publicación self-contained (Windows x64):

        cd dotnet/DexRelay.PKHeX
        dotnet publish -c Release -r win-x64 --self-contained true ^
            -p:PublishSingleFile=true ^
            -p:IncludeNativeLibrariesForSelfExtract=true ^
            -o ../../releases/pkhex-bridge
    """

    PUBLISHED_EXE_NAME = "DexRelay.PKHeX.exe"

    def __init__(self):
        self.process = None

        # paths.base_dir() en modo desarrollo es la raiz del
        # proyecto (igual que antes); en un build empaquetado
        # es la carpeta del .exe -- ahi solo importa que exista
        # el published_exe_path de abajo, el project_directory
        # de dotnet run es de uso exclusivo en desarrollo.
        project_root = paths.base_dir()

        self.project_directory = (
            project_root
            / "dotnet"
            / "DexRelay.PKHeX"
        )

        self.published_exe_path = (
            project_root
            / "releases"
            / "pkhex-bridge"
            / self.PUBLISHED_EXE_NAME
        )

    def _build_command(self):
        """
        Devuelve el comando a lanzar: el ejecutable
        self-contained publicado si existe, o `dotnet run` en
        modo desarrollo si todavía no se publicó nada.
        """

        if self.published_exe_path.exists():
            return [str(self.published_exe_path)]

        return [
            "dotnet",
            "run",
            "--project",
            str(self.project_directory),
        ]

    def start(self):
        """
        Inicia el proceso .NET del bridge.
        """

        if self.process is not None:
            if self.process.poll() is None:
                return

            self.process = None

        self.process = subprocess.Popen(
            self._build_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def is_running(self):
        """
        Comprueba si el proceso del bridge
        continúa ejecutándose.
        """

        if self.process is None:
            return False

        return self.process.poll() is None

    def request(self, payload):
        """
        Envía una petición JSON y devuelve
        la respuesta como diccionario.
        """

        if not self.is_running():
            self.start()

        if self.process is None:
            raise RuntimeError(
                "No se pudo iniciar el bridge PKHeX."
            )

        if self.process.stdin is None:
            raise RuntimeError(
                "La entrada del bridge no está disponible."
            )

        if self.process.stdout is None:
            raise RuntimeError(
                "La salida del bridge no está disponible."
            )

        message = (
            json.dumps(payload)
            + "\n"
        )

        try:
            self.process.stdin.write(
                message
            )

            self.process.stdin.flush()

        except (BrokenPipeError, OSError) as error:

            self.stop()

            raise RuntimeError(
                "No se pudo enviar la petición "
                "al bridge PKHeX."
            ) from error

        response = (
            self.process.stdout.readline()
        )

        if not response:
            exit_code = (
                self.process.poll()
            )

            self.stop()

            raise RuntimeError(
                "El bridge PKHeX dejó de responder. "
                f"Código de salida: {exit_code}"
            )

        try:
            result = json.loads(
                response
            )

        except json.JSONDecodeError as error:

            raise RuntimeError(
                "El bridge PKHeX devolvió "
                "una respuesta JSON inválida."
            ) from error

        if "error" in result:
            raise RuntimeError(
                result["error"]
            )

        return result

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

    def species_list(self):
        """
        Obtiene la lista completa {id, name} de especies
        conocidas por PKHeX. Se llama una sola vez -- el
        resultado se cachea del lado de Python
        (species_resolver.py / el endpoint /api/species).
        """

        return self.request(
            {
                "action": "species_list",
            }
        )

    def location_list(self):
        """
        Obtiene la lista completa {id, name} de ubicaciones
        conocidas por PKHeX para Alpha Sapphire -- la misma
        fuente que met_location() usa para resolver el lugar de
        encuentro real de una captura, así que ambas siempre
        coinciden textualmente. Se llama una sola vez -- el
        resultado se cachea del lado de Python
        (location_catalog.py / el endpoint /api/locations).
        """

        return self.request(
            {
                "action": "location_list",
            }
        )

    def met_location(self, decrypted_box_data):
        """
        Resuelve el lugar de encuentro (y si es shiny) a
        partir de los 232 bytes YA DESCIFRADOS de un
        Pokémon (Pokemon6.raw_data[:232] en
        app/memory/structures.py -- la misma fuente que ya
        usamos para species_id/nickname/level/hp).
        """

        import base64

        encoded_data = base64.b64encode(
            decrypted_box_data
        ).decode("ascii")

        return self.request(
            {
                "action": "met_location",
                "data": encoded_data,
            }
        )

    def stop(self):
        """
        Detiene el proceso del bridge.
        """

        if self.process is None:
            return

        process = self.process

        self.process = None

        try:

            if process.stdin is not None:
                process.stdin.close()

        except (BrokenPipeError, OSError):
            pass

        try:

            if process.poll() is None:
                process.terminate()

                process.wait(
                    timeout=5
                )

        except subprocess.TimeoutExpired:

            process.kill()

            process.wait()

        except OSError:
            pass

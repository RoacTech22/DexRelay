import json
import subprocess
import threading
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

        # CORRECCIÓN REAL (09/09/2026, reportado por el usuario:
        # "ahora no me salen algunas evoluciones y en algunos
        # pokemon no me muestra todos los datos" -- síntoma
        # mezclado entre especies SIN relación entre sí, lo que
        # descartó un bug de lógica y apuntó a esto): request() no
        # tenía ningún lock protegiendo el par escritura+lectura
        # sobre el mismo pipe stdin/stdout del proceso -- si dos
        # llamadas se solapan (ahora más probable que antes, Fase E
        # 09/09/2026: gym_leaders.py pasó a compartir esta MISMA
        # instancia de bridge con species_details() del modal
        # Pokédex, en vez de tener cada uno la suya), la respuesta
        # de una petición se puede leer mezclada con la de otra --
        # exactamente el síntoma reportado. Mismo criterio que ya
        # usa AzaharReader para el socket UDP compartido
        # (threading.Lock envolviendo cada sendto+recv): acá
        # envuelve cada escritura+lectura sobre el proceso.
        self._lock = threading.Lock()

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

        Con lock (ver self._lock en __init__) -- una sola petición
        a la vez sobre el mismo proceso, sin importar desde qué
        hilo se llame.
        """

        with self._lock:

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

    def item_list(self):
        """
        GUI v2, roadmap 07/09/2026 -- lista completa {id, name} de
        ítems conocidos por PKHeX, en español (mismo paquete de
        GameStrings que species_list()/etc., ver el comentario
        largo en HandleItemList(), Program.cs). Se llama una sola
        vez -- el resultado se cachea del lado de Python (mismo
        patrón que species_list()/SpeciesCatalog).
        """

        return self.request(
            {
                "action": "item_list",
            }
        )

    def ability_list(self):
        """
        Fase E (09/09/2026, soporte hackroom) -- idem item_list()
        pero para habilidades ({id, name} en español, ver
        HandleAbilityList() en Program.cs). Hacía falta para
        traducir habilidades del hack que no estaban en el
        diccionario chico a mano GYM_ABILITY_NAMES_ES (pensado solo
        para las 24 combinaciones del juego base).
        """

        return self.request(
            {
                "action": "ability_list",
            }
        )

    def move_list(self):
        """
        Fase E (09/09/2026, soporte hackroom) -- idem item_list()/
        ability_list() pero para movimientos ({id, name} en
        español, ver HandleMoveList() en Program.cs). Reemplaza el
        diccionario chico a mano MOVE_NAME_ES del frontend (64
        movimientos, pensado solo para el juego base) por el mismo
        mecanismo ya confirmado 100% correcto para movimientos
        (tools/probes/verificar_nombres_movimiento_es.py,
        09/09/2026, 919/919 sin huecos reales).
        """

        return self.request(
            {
                "action": "move_list",
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

    def pokemon_details(self, decrypted_box_data, base_stats_override=None):
        """
        Resuelve tipos, habilidad, naturaleza, stats de combate y
        movimientos a partir de los 232 bytes YA DESCIFRADOS de un
        Pokémon -- misma fuente que met_location() (GUI v2,
        Bloque 3, página Pokémon).

        `base_stats_override` (Fase E, 09/09/2026, hackroom, a
        pedido del usuario: "que también se vea reflejado el
        cambio de stat base en las stats calculadas") -- dict
        opcional {"hp"?, "attack"?, "defense"?, "spAttack"?,
        "spDefense"?, "speed"?} con la stat base del hackroom para
        la especie de este Pokémon (ver data/pokemon_changes_rrss.json).
        Se manda tal cual al bridge, que la aplica TEMPORALMENTE
        antes de calcular (ver HandlePokemonDetails() en Program.cs
        para el porqué del cuidado de restaurar después). None (o
        no pasar el argumento) es el comportamiento de siempre, sin
        tocar nada -- pensado así para que ningún llamador existente
        tenga que cambiar.
        """

        import base64

        encoded_data = base64.b64encode(
            decrypted_box_data
        ).decode("ascii")

        payload = {
            "action": "pokemon_details",
            "data": encoded_data,
        }

        if base_stats_override:
            payload["baseStatsOverride"] = base_stats_override

        return self.request(payload)

    def save_info(self, save_file_path):
        """
        Tiempo de juego real (GUI v2, página Nuzlocke, 04/09/2026):
        a diferencia de species()/met_location()/pokemon_details(),
        acá no se manda ningún byte -- se manda la RUTA del archivo
        de guardado (ya resuelta por
        app/services/save_file_locator.py) y el bridge lo lee
        directo del disco, porque es la misma máquina. Devuelve
        {"ok": True, "playedHours": ..., "playedMinutes": ...,
        "playedSeconds": ...}.
        """

        return self.request(
            {
                "action": "save_info",
                "path": str(save_file_path),
            }
        )

    def species_details(self, species_id):
        """
        GUI v2, roadmap 06/09/2026 sección 4.2 -- modal "Pokédex"
        de detalle de especie. A diferencia de species() (que solo
        da el nombre), esto pide tipo/habilidades/stats
        base/evolución -- dato de la ESPECIE, no de un Pokémon
        puntual, así que se puede cachear del lado Python por
        species_id (mismo patrón que species_cache.json).

        NOTA: acción nueva del lado C# (HandleSpeciesDetails,
        Program.cs) escrita sin poder compilar en esa sesión -- ver
        el comentario largo ahí antes de asumir que ya está
        probada en vivo.
        """

        return self.request(
            {
                "action": "species_details",
                "id": species_id,
            }
        )

    def move_details(self, move_id):
        """
        GUI v2, roadmap 06/09/2026 sección 4.1 -- modal de
        movimiento. Devuelve nombre/tipo/PP base -- NO potencia/
        precisión/categoría, confirmado que PKHeX.Core no las
        expone (ver comentario largo en HandleMoveDetails(),
        Program.cs).
        """

        return self.request(
            {
                "action": "move_details",
                "id": move_id,
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

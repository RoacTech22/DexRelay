import atexit
import json
import subprocess
import sys
import threading
import weakref
from pathlib import Path

from app.core import paths


# Todas las instancias de PKHeXBridge con vida (cada servicio del
# proyecto puede crear la suya). Bug real (18/09/2026, primer build
# empaquetado): al cerrar DexRelay nadie llamaba a stop() de ningún
# bridge, así que DexRelay.PKHeX.exe seguía corriendo. Se detienen
# todos al salir (ver stop_all() y el atexit de abajo).
_LIVE_BRIDGES = weakref.WeakSet()

_kill_on_close_job = None


def _get_kill_on_close_job():
    """
    Job Object de Windows con KILL_ON_JOB_CLOSE: si DexRelay muere de
    forma abrupta (crash, "Finalizar tarea", corte de luz del proceso),
    Windows mata solo a los bridges asignados -- no queda ningún
    huérfano aunque no llegue a correr el atexit. Devuelve None si no
    es Windows o algo falla (en ese caso queda la protección normal:
    stop_all() + el fin de stdin que ahora sí termina el bridge).
    """

    global _kill_on_close_job

    if sys.platform != "win32":
        return None

    if _kill_on_close_job is not None:
        return _kill_on_close_job

    try:
        import ctypes
        from ctypes import wintypes

        class _BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            ]

        class _ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimits),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [
            wintypes.LPVOID,
            wintypes.LPCWSTR,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]

        job = kernel32.CreateJobObjectW(None, None)

        if not job:
            return None

        limits = _ExtendedLimits()
        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        limits.BasicLimitInformation.LimitFlags = 0x2000

        ok = kernel32.SetInformationJobObject(
            job,
            9,  # JobObjectExtendedLimitInformation
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )

        if not ok:
            return None

        _kill_on_close_job = (kernel32, job)

        return _kill_on_close_job

    except Exception:
        return None


def _attach_to_kill_on_close_job(process):
    job = _get_kill_on_close_job()

    if job is None:
        return

    kernel32, handle = job

    try:
        from ctypes import wintypes

        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]

        kernel32.AssignProcessToJobObject(
            handle, int(process._handle)
        )

    except Exception:
        # Sin el job igual queda stop_all() al salir -- nunca romper
        # el arranque del bridge por esto.
        pass


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

        _LIVE_BRIDGES.add(self)

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

        # Bug real (18/09/2026, primer build empaquetado v0.3.0-alpha):
        # el bridge es una app de CONSOLA, y como DexRelay.exe se
        # empaqueta con console=False, Windows le abría una ventana
        # de terminal propia cada vez que se lanzaba el proceso
        # (al navegar a una página que lo usa por primera vez, o al
        # reiniciarse). CREATE_NO_WINDOW lo evita sin afectar el
        # stdin/stdout por pipes. Solo existe en Windows.
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32"
            else 0
        )

        self.process = subprocess.Popen(
            self._build_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=creationflags,
        )

        _attach_to_kill_on_close_job(self.process)

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

    @classmethod
    def stop_all(cls):
        """
        Detiene TODOS los bridges con vida (uno por servicio que haya
        creado el suyo). Se llama al cerrar DexRelay.
        """

        for bridge in list(_LIVE_BRIDGES):
            try:
                bridge.stop()
            except Exception:
                pass

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


atexit.register(PKHeXBridge.stop_all)

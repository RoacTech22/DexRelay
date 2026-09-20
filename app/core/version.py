"""
Resolución de la versión real de DexRelay -- reemplaza a la
constante `APP_VERSION` hardcodeada a mano en `app/gui_web/api.py`
(quedó en "v0.3.0", un valor viejo/incorrecto que nadie actualizaba
en cada release real).

Criterio (mismo espíritu que `app/core/paths.py`: un solo lugar
que sabe resolver esto, consciente de si la app corre desde el
código fuente o empaquetada):

1. Build empaquetado (PyInstaller): lee un archivo `VERSION` en
   `paths.base_dir()` (junto al .exe). Ese archivo NO se escribe a
   mano -- lo genera el script de empaquetado con
   `git describe --tags --always --dirty` en el momento de armar el
   build (ver comentario en `DexRelay.spec`), así que siempre
   refleja el tag real de Git de ese build, no un número
   inventado.
2. Modo desarrollo (corriendo desde el código fuente, hay `.git`
   real disponible): corre `git describe --tags --always --dirty`
   directo -- mismo comando, mismo formato, sin depender de que
   alguien haya generado el archivo `VERSION` a mano.
3. Si ninguna de las dos funciona (Git no instalado, repo
   corrompido, `VERSION` ausente en un build viejo) -- se devuelve
   "versión desconocida" en vez de inventar un número que no
   significa nada.

Formato de `git describe --tags --always --dirty` (ejemplo real de
este repo hoy): "v0.1.0-alpha-20-g88e24b0" -- el tag más reciente,
cuántos commits pasaron desde ese tag, y el hash corto del commit
actual. Si el árbol de trabajo tiene cambios sin commitear, agrega
"-dirty" al final. Es más información que un simple "v0.1.0-alpha",
pero es TODA real -- no se recorta a mano para que "se vea más
prolijo", eso sería empezar a inventar de nuevo.
"""

from __future__ import annotations

import subprocess
import sys

from app.core import paths

_UNKNOWN_VERSION = "versión desconocida"


def get_app_version() -> str:
    version_file = paths.path("VERSION")

    if version_file.exists():
        try:
            content = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            content = ""

        if content:
            return content

    described = _git_describe()

    if described:
        return described

    return _UNKNOWN_VERSION


def _git_describe() -> str | None:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=paths.base_dir(),
            capture_output=True,
            text=True,
            timeout=3,
            # Sin esto, en el build empaquetado (console=False)
            # Windows abre una ventana de terminal por cada llamada.
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0
            ),
        )
    except (OSError, subprocess.SubprocessError):
        # Git no instalado, no está en PATH, o tardó demasiado --
        # ninguno de estos es un error que valga la pena romper la
        # GUI por él, simplemente no hay versión que mostrar así.
        return None

    if result.returncode != 0:
        # No es un repo Git real (por ejemplo, un build empaquetado
        # sin el archivo VERSION todavía) -- caso esperado, no un
        # error a reportar.
        return None

    output = result.stdout.strip()

    return output or None

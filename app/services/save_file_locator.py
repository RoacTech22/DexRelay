from __future__ import annotations

import glob
import os
from pathlib import Path

from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)

# Bajo (8 hex) del Title ID de cada juego -- son los mismos Title
# IDs públicos y conocidos que ya usa
# app/gui_web/api.py:TITLE_ID_REGIONS ("000400000011C400" /
# "000400000011C500"), no algo medido/adivinado acá. El alto
# ("00040000") es el mismo para ambos, es la categoría estándar de
# "aplicación" en 3DS.
_TITLE_ID_HIGH = "00040000"

_TITLE_ID_LOW_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: "0011c500",
    PROCESS_NAME_OMEGA_RUBY: "0011c400",
}

# Nombre real del archivo de guardado dentro de
# ".../data/00000001/" para estos dos juegos -- confirmado por el
# usuario el 04/09/2026 mirando su propia carpeta de Alpha
# Sapphire ("main"). Se prueba primero este nombre exacto; si no
# aparece (otra versión/juego con un nombre distinto el día de
# mañana), se cae a "cualquier archivo que haya en la carpeta"
# como respaldo -- ver _find_save_file_in_data_dir().
_KNOWN_SAVE_FILENAME = "main"

# Raíces candidatas del directorio de usuario de Azahar, en orden
# de probabilidad. Confirmada por el usuario (04/09/2026):
# "C:\Users\<usuario>\AppData\Roaming\Azahar\sdmc\...", carpeta
# "Azahar" con mayúscula, no "azahar-emu\azahar" (esa es la que
# usa la documentación pública genérica, pero no coincide con la
# instalación real del usuario -- se deja como candidato de
# respaldo igual, por si alguien más corre esto con una instalación
# distinta). "Citra" queda como último recurso para quien todavía
# no migró sus saves.
#
# No se hardcodea ID0/ID1 (las dos carpetas de 32 ceros) -- son
# hashes específicos de la instalación, pueden no ser todos ceros
# en otra PC. Se resuelven con glob (comodín) en vez de asumir un
# valor fijo.
def _candidate_appdata_roots() -> list[Path]:
    appdata = os.environ.get("APPDATA")

    if not appdata:
        return []

    base = Path(appdata)

    return [
        base / "Azahar" / "sdmc",
        base / "azahar-emu" / "azahar" / "sdmc",
        base / "Citra" / "sdmc",
    ]


def _candidate_linux_roots() -> list[Path]:
    home = os.environ.get("HOME")

    if not home:
        return []

    base = Path(home) / ".local" / "share"

    return [
        base / "azahar-emu" / "azahar" / "sdmc",
        base / "citra-emu" / "citra" / "sdmc",
    ]


def _find_save_file_in_data_dir(data_dir: Path) -> Path | None:
    """
    Dentro de ".../data/00000001/", prueba primero el nombre
    conocido ("main"). Si no está, cae a "el primer archivo que
    haya ahí" -- mejor un intento razonable que no encontrar nada,
    ya que esta carpeta normalmente tiene un solo archivo de
    guardado real.
    """

    known = data_dir / _KNOWN_SAVE_FILENAME

    if known.exists():
        return known

    try:
        candidates = sorted(
            entry
            for entry in data_dir.iterdir()
            if entry.is_file()
        )
    except OSError:
        return None

    return candidates[0] if candidates else None


def find_save_file(process_name: str) -> Path | None:
    """
    Busca el archivo de guardado real de Azahar en disco para el
    juego indicado (`process_name`: "sango-1"/"sango-2", ver
    pointers.py). Devuelve `None` si no se pudo encontrar nada --
    NUNCA inventa una ruta, el llamador decide cómo mostrar esa
    ausencia (ver PlaytimeService).

    No confirma nada por memoria RAM -- esto es una búsqueda en el
    sistema de archivos, con ID0/ID1 resueltos por comodín (glob)
    en vez de asumir un valor fijo, para no depender de que la
    instalación de quien sea tenga esas dos carpetas en cero como
    la del usuario que confirmó esto.
    """

    title_id_low = _TITLE_ID_LOW_BY_PROCESS.get(process_name)

    if title_id_low is None:
        return None

    roots = (
        _candidate_appdata_roots()
        + _candidate_linux_roots()
    )

    for root in roots:
        if not root.exists():
            continue

        pattern = str(
            root
            / "Nintendo 3DS"
            / "*"
            / "*"
            / "title"
            / _TITLE_ID_HIGH
            / title_id_low
            / "data"
            / "00000001"
        )

        for match in glob.glob(pattern):
            data_dir = Path(match)
            save_file = _find_save_file_in_data_dir(data_dir)

            if save_file is not None:
                return save_file

    return None

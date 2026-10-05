"""
Paso 1 del Bloque 14 (ruta multijuego, 03/10/2026): descubrir cómo
aparecen Pokémon X e Y en Azahar.

Por qué existe: los process_name de ORAS ("sango-1"/"sango-2") se
leyeron de Azahar, no se dedujeron. Los de X/Y también se tienen que
LEER -- este probe NO los asume. Con el juego cargado, lista todos los
procesos que expone Azahar (process_name + Title ID) y señala cuáles
coinciden con los Title ID ya conocidos del proyecto
(app/gui_web/api_dashboard.py:TITLE_ID_REGIONS).

Solo lectura: no selecciona ningún proceso ni lee/escribe memoria del
juego.

Uso (con Azahar abierto y el juego ya cargado, idealmente en el mapa
o en el menú de continuar, NO en el logo inicial):

    python tools/probes/xy/listar_procesos_xy.py

Corre una vez con X y otra con Y (cierra el juego entre corridas) y
pega la salida completa de cada una en el chat. También sirve con la
versión de Azahar y el parche instalado: anota si X/Y tiene la
actualización 1.5 (regla 4 del Documento Maestro: las direcciones
valen solo para una versión EXACTA del juego).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.games.registry import all_profiles  # noqa: E402
from app.readers.citra import Citra  # noqa: E402

# Title ID de 3DS que ya conoce el proyecto (los mismos de
# TITLE_ID_REGIONS). Se repiten acá a propósito: un probe no debe
# depender de que la GUI esté importable.
KNOWN_TITLE_IDS = {
    "0004000000055D00": "Pokémon X",
    "0004000000055E00": "Pokémon Y",
    "000400000011C400": "Pokémon Omega Ruby",
    "000400000011C500": "Pokémon Alpha Sapphire",
}


def main() -> int:
    citra = Citra()

    try:
        processes = citra.process_list()
    except OSError as error:
        print(f"No se pudo hablar con Azahar: {error!r}")
        print(
            "Revisa que Azahar esté abierto, con el juego cargado, y que "
            "la interfaz de depuración UDP (puerto 45987) esté activa."
        )
        return 1

    if not processes:
        print("Azahar respondió pero no lista ningún proceso.")
        return 1

    perfiles = {p.key for p in all_profiles()}

    print(f"Procesos expuestos por Azahar: {len(processes)}\n")
    print(f"{'PID':>6}  {'TITLE ID':<16}  {'PROCESS_NAME':<10}  NOTA")

    candidatos = []

    for pid, (title_id, name) in sorted(processes.items()):
        title_hex = f"{title_id:016X}"
        known = KNOWN_TITLE_IDS.get(title_hex)

        if name in perfiles:
            nota = "ya tiene perfil en DexRelay"
        elif known:
            nota = f"Title ID conocido: {known}"
            candidatos.append((pid, title_hex, name, known))
        else:
            nota = ""

        print(f"{pid:>6}  {title_hex:<16}  {name:<10}  {nota}")

    print()

    if candidatos:
        print("Candidatos X/Y (copia estas líneas al chat):")
        for pid, title_hex, name, known in candidatos:
            print(f"  {known}: process_name={name!r} title_id={title_hex}")
    else:
        print(
            "Ningún proceso coincide con los Title ID conocidos de X/Y. "
            "Puede ser otra región/edición: busca en la tabla de arriba "
            "el proceso del juego y copia su fila completa al chat."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

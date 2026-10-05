"""
Paso 4 del Bloque 14 (ruta multijuego, 04/10/2026): encontrar la tarjeta
de entrenador de Pokémon X/Y en RAM (Trainer ID, Secret ID y nombre), que
identifica QUÉ partida está cargada (Bloque 5: un archivo de progreso por
partida).

Mismo método que ya la encontró en ORAS (investigar_trainer_id.py,
Fuente B): se parte del TID/SID/nombre OT que llevan los Pokémon propios
(los datos salen de la salida de buscar_party_xy.py) y se busca en RAM el
nombre en UTF-16LE con el par TID/SID cerca, descartando las apariciones
que son parte de una estructura PK6 (nombre - TID = 0xA4).

En ORAS la tarjeta quedó en 0x08C81340: ID en +0x00, nombre en +0x48 (72
bytes de distancia). Si X/Y la guarda igual, aparecerá un candidato con
"nombre - id = +72".

Un candidato NO se confirma solo con esto: hay que repetirlo con OTRA
partida (otro TID/OT) y comprobar que el candidato se mueve con la
PARTIDA y no con un Pokémon, y que el TID/SID leído coincide con la
Tarjeta de Entrenador del juego (reglas 1, 11 y 12 del Documento Maestro).

Solo lectura. USO (X o Y cargado en una partida):

    python tools/probes/xy/investigar_trainer_xy.py --tid 58557 --sid 32925 --ot Mattia

Si no conoces el SID (el juego no lo muestra), omite --sid y usa el TID y
el nombre que ves en la Tarjeta de Entrenador: el probe te dice el SID.
(el TID/SID/OT son los de los Pokémon propios; con el save de prueba de la
primera corrida eran TID 58557, SID 32925, OT 'Mattia'). Opciones:
--start 0x08000000 --size 0x2000000 (32 MB, ~1-2 min).
Pega la salida completa en el chat.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.memory.memory_reader import MemoryReader  # noqa: E402
from app.readers.citra import Citra  # noqa: E402
from tools.probes.memory.investigar_trainer_id import (  # noqa: E402
    PK6_OT_MINUS_TID,
    find_id_and_name_pairs,
    read_window,
)

XY_TITLE_IDS = {0x0004000000055D00, 0x0004000000055E00}
DEFAULT_START = 0x08000000
DEFAULT_SIZE = 0x2000000


def parse_int(value):
    return int(value, 0)


def classify_hits(hits):
    """Separa (candidatos, cantidad_descartada_por_firma_PK6)."""
    candidates = []
    pk6_like = 0

    for id_offset, name_offset in hits:
        distance = name_offset - id_offset

        if distance == PK6_OT_MINUS_TID:
            pk6_like += 1
            continue

        candidates.append((id_offset, name_offset, distance))

    return candidates, pk6_like


def find_card_by_name_and_tid(data, tid, ot_name):
    """Busca la tarjeta sin conocer el SID (no se ve en el juego).

    Devuelve [(id_offset, name_offset, sid_leido)] donde el nombre UTF-16LE
    aparece con el TID16 exactamente 72 bytes antes (diseño de ORAS).
    """
    encoded = ot_name.encode("utf-16le")
    found = []
    start = 0

    while True:
        pos = data.find(encoded, start)

        if pos < 0:
            break

        start = pos + 1
        id_offset = pos - 72

        if id_offset < 0 or pos + len(encoded) + 2 > len(data):
            continue

        if data[pos + len(encoded):pos + len(encoded) + 2] != b"\x00\x00":
            continue

        found_tid = int.from_bytes(data[id_offset:id_offset + 2], "little")

        if found_tid == tid:
            sid = int.from_bytes(data[id_offset + 2:id_offset + 4], "little")
            found.append((id_offset, pos, sid))

    return found


def select_process(citra, wanted):
    for pid, (title_id, name) in sorted(citra.process_list().items()):
        if wanted is not None:
            if name == wanted:
                return pid, name
        elif title_id in XY_TITLE_IDS:
            return pid, name

    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tid", type=int, required=True)
    parser.add_argument("--sid", type=int, default=None)
    parser.add_argument("--ot", required=True)
    parser.add_argument("--process", default=None)
    parser.add_argument("--start", type=parse_int, default=DEFAULT_START)
    parser.add_argument("--size", type=parse_int, default=DEFAULT_SIZE)
    args = parser.parse_args()

    citra = Citra()

    try:
        selected = select_process(citra, args.process)
    except OSError as error:
        print(f"No se pudo hablar con Azahar: {error!r}")
        return 1

    if selected is None:
        print("No se encontró el proceso de X/Y. Corre antes listar_procesos_xy.py.")
        return 1

    pid, name = selected
    citra.set_process(pid)

    print(f"Proceso: {name}  (PID {pid})")
    print(f"Buscando OT={args.ot!r} TID16={args.tid} SID16={args.sid}")
    print(f"Ventana: 0x{args.start:08X} .. 0x{args.start + args.size:08X}\n")

    data, failed = read_window(MemoryReader(citra), args.start, args.size)

    if failed:
        print(f"(bloques que no se pudieron leer: {failed})")

    if args.sid is None:
        found = find_card_by_name_and_tid(data, args.tid, args.ot)
        print(f"Modo sin SID: coincidencias nombre+TID a -72: {len(found)}")

        for id_offset, name_offset, sid in found:
            print(
                f"  ID 0x{args.start + id_offset:08X}  "
                f"nombre 0x{args.start + name_offset:08X}  SID leído: {sid}"
            )

        return 0

    hits = find_id_and_name_pairs(data, args.tid, args.sid, args.ot)
    candidates, pk6_like = classify_hits(hits)

    print(
        f"Coincidencias totales: {len(hits)}  "
        f"(descartadas por firma PK6 [+0xA4]: {pk6_like})"
    )

    if not candidates:
        print(
            "Sin candidatos fuera de estructuras PK6. Prueba una ventana "
            "más grande (--size 0x4000000) o revisa que el TID/SID/OT "
            "sean los de TUS Pokémon (salida de buscar_party_xy.py)."
        )
        return 0

    print(f"\n{'Dirección ID':>12} {'Dirección nombre':>17} {'nombre - id':>12}")

    for id_offset, name_offset, distance in candidates:
        print(
            f"0x{args.start + id_offset:08X}  "
            f"0x{args.start + name_offset:>13X}  {distance:>+12}"
        )

    print(
        "\nSi aparece un candidato con nombre - id = +72, es el mismo diseño "
        "que ORAS (ID en +0x00, nombre en +0x48). Para confirmarlo: abre la "
        "Tarjeta de Entrenador del juego, compara el nombre y el ID, y repite "
        "con otra partida. NO se fija nada en el perfil hasta entonces."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

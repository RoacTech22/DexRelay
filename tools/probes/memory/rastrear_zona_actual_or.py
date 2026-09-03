"""
Busca CURRENT_ZONE_ID_ADDRESS para Omega Ruby -- mismo algoritmo
exacto que tools/probes/memory/rastrear_zona_actual.py (el que
encontro la direccion de Alpha Sapphire, 0x08C6A7B2), pero
parametrizado para conectar a "sango-1" y usar el ancla de party
correcta de Omega Ruby si se elige --centro party.

Por que un script separado y no tocar el original: mismo criterio ya
aplicado con buscar_caja_pc_or.py -- no arriesgar el script que ya
funciono para Alpha Sapphire.

Motivo (30/08/2026): confirmado que CURRENT_ZONE_ID_ADDRESS (la de
Alpha Sapphire) NO sirve en Omega Ruby -- se detecto porque la
deteccion automatica de "perdido" estaba creando encuentros fantasma
en una ruta placeholder "Zona 0" (zone_id=0, el valor que da leer
esa direccion en la memoria de Omega Ruby). La deteccion de
"perdido" quedo desactivada en runtime.py para Omega Ruby hasta
resolver esto.

BADGES_ADDRESS (el ancla por defecto) ya esta CONFIRMADO compartido
entre las dos versiones -- buen punto de partida, ya que en Alpha
Sapphire CURRENT_ZONE_ID_ADDRESS calculado quedo a poca distancia
de BADGES_ADDRESS (~0x2622 bytes), bien adentro de la ventana de
256KB que ya usa este script. Si no aparece nada con este ancla,
probar --centro party (usa la PARTY_ORDER_ADDRESS ya confirmada de
Omega Ruby).

COMO USARLO (igual que el original, ver ese archivo para el detalle
completo del metodo -- necesitas volver a un lugar ya visitado al
menos una vez en la secuencia):

    1. Confirmar config.json -> azahar.process_name = "sango-1", o
       pasar --proceso sango-1 explicito.

    2. Anota el orden de lugares por los que vas a pasar, INCLUYENDO
       al menos una repeticion. Por ejemplo:
       Ruta101 -> CiudadPetalburgo -> Ruta101 -> Ruta104

    3. Corre:

           python -m tools.probes.memory.rastrear_zona_actual_or --secuencia "Ruta101,CiudadPetalburgo,Ruta101,Ruta104"

    4. El script te va pidiendo confirmar con Enter en cada lugar
       de la secuencia (parate ahi, fuera de combate y fuera de
       cualquier menu, antes de confirmar).

    5. Al final imprime los offsets candidatos (si los hay).

Repite con otra secuencia distinta (otra sesion) para confirmar que
el mismo offset se repite -- un solo intento puede tener falsos
positivos por casualidad, sobre todo con secuencias cortas.
"""

import argparse
import struct
import time

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.services.badges_service import BADGES_ADDRESS
from app.memory.pointers import (
    PROCESS_NAME_OMEGA_RUBY,
    get_party_order_address,
)


WINDOW_BEFORE = 0x40000
WINDOW_AFTER = 0x40000

STABILITY_READS = 4
STABILITY_DELAY_SECONDS = 0.3


def get_anchors():
    return {
        "badges": BADGES_ADDRESS,
        "party": get_party_order_address(PROCESS_NAME_OMEGA_RUBY),
    }


def read_window(memory, start, size):
    data = memory.read(start, size)

    if len(data) != size:
        return None

    return data


def collect_stability_reads(memory, start, size):

    reads = []

    for _ in range(STABILITY_READS):

        snapshot = read_window(memory, start, size)

        if snapshot is None:
            return None

        reads.append(snapshot)
        time.sleep(STABILITY_DELAY_SECONDS)

    return reads


def build_stable_mask(reads):

    base = int.from_bytes(reads[0], "big")
    diff_mask = 0

    for snapshot in reads[1:]:
        diff_mask |= int.from_bytes(snapshot, "big") ^ base

    return diff_mask.to_bytes(len(reads[0]), "big")


def read_stable_step(memory, start, size):

    reads = collect_stability_reads(memory, start, size)

    if reads is None:
        return None, None

    stable_mask = build_stable_mask(reads)

    return reads[0], stable_mask


def parse_sequence(raw_value):
    labels = [
        piece.strip()
        for piece in raw_value.split(",")
        if piece.strip()
    ]

    if len(labels) < 2:
        raise argparse.ArgumentTypeError(
            "La secuencia necesita al menos 2 lugares."
        )

    if len(set(labels)) == len(labels):
        raise argparse.ArgumentTypeError(
            "La secuencia no repite ningun lugar. Hace falta "
            "volver a un lugar ya visitado al menos una vez "
            "para poder aplicar la regla 'mismo lugar = mismo "
            "valor'."
        )

    return labels


def find_candidates(steps, labels, width):

    size = len(steps[0][0])

    unpack_format = "<B" if width == 1 else "<H"

    label_to_indices = {}

    for index, label in enumerate(labels):
        label_to_indices.setdefault(
            label,
            [],
        ).append(index)

    candidates = []

    for offset in range(size - width + 1):

        stable_everywhere = all(
            stable_mask[offset:offset + width] == b"\x00" * width
            for _snapshot, stable_mask in steps
        )

        if not stable_everywhere:
            continue

        values = [
            struct.unpack(
                unpack_format,
                snapshot[offset:offset + width],
            )[0]
            for snapshot, _stable_mask in steps
        ]

        consistent = True

        for indices in label_to_indices.values():

            first_value = values[indices[0]]

            for index in indices[1:]:

                if values[index] != first_value:
                    consistent = False
                    break

            if not consistent:
                break

        if not consistent:
            continue

        distinct_values = {
            values[indices[0]]
            for indices in label_to_indices.values()
        }

        if len(distinct_values) != len(label_to_indices):
            continue

        candidates.append((offset, values))

    return candidates


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Busca CURRENT_ZONE_ID_ADDRESS para Omega Ruby, usando "
            "una secuencia de lugares con al menos una repeticion."
        )
    )

    parser.add_argument(
        "--secuencia",
        type=parse_sequence,
        required=True,
        help=(
            "Nombres de lugares en orden, separados por comas, "
            "repitiendo al menos uno. Ej: "
            "Ruta101,CiudadPetalburgo,Ruta101"
        ),
    )

    anchors = get_anchors()

    parser.add_argument(
        "--centro",
        choices=list(anchors.keys()),
        default="badges",
        help=(
            "Direccion fija alrededor de la cual escanear. "
            "'badges' (por defecto, compartida entre versiones) "
            "o 'party' (la de Omega Ruby)."
        ),
    )

    parser.add_argument(
        "--proceso",
        default=None,
        help=(
            "Nombre del proceso a buscar en Azahar. Por defecto "
            "usa config.json -> azahar.process_name, o 'sango-1' "
            "si no esta configurado."
        ),
    )

    args = parser.parse_args()
    labels = args.secuencia
    center = anchors[args.centro]

    process_name = args.proceso or Config().get(
        "azahar", "process_name", default=PROCESS_NAME_OMEGA_RUBY
    )

    print("================================")
    print("   RASTREAR ZONA ACTUAL (Omega Ruby)")
    print("================================")
    print()
    print(
        "Secuencia: "
        + " -> ".join(labels)
    )
    print(
        f"Ancla: {args.centro} "
        f"({hex(center)})"
    )
    print()

    reader = AzaharReader(process_name=process_name)

    print(f"Buscando proceso {process_name!r}...")

    if not reader.connect():
        print(f"No se encontro {process_name!r}.")
        return

    print("Azahar conectado correctamente.")
    print()

    memory = reader.memory

    scan_start = center - WINDOW_BEFORE
    scan_size = WINDOW_BEFORE + WINDOW_AFTER

    print(
        f"Ventana de escaneo: {hex(scan_start)} - "
        f"{hex(scan_start + scan_size)} "
        f"({hex(scan_size)} bytes)"
    )
    print()

    steps = []

    for step_number, label in enumerate(labels, start=1):

        input(
            f"[Paso {step_number}/{len(labels)}] Parate en "
            f"'{label}' (fuera de combate/menus) y presiona "
            f"Enter..."
        )

        print(
            f"Leyendo memoria ({STABILITY_READS} lecturas para "
            f"detectar que esta quieto, quedate quieto "
            f"~{STABILITY_READS * STABILITY_DELAY_SECONDS:.1f}s)..."
        )

        snapshot, stable_mask = read_stable_step(
            memory,
            scan_start,
            scan_size,
        )

        if snapshot is None:
            print(f"Lectura del paso {step_number} fallo.")
            return

        steps.append((snapshot, stable_mask))

        stable_ratio = (
            100 * stable_mask.count(0) / len(stable_mask)
        )

        print(
            f"Snapshot {step_number} capturado "
            f"({stable_ratio:.1f}% de la ventana estuvo quieta)."
        )
        print()

    print("Analizando candidatos (1 byte)...")
    candidates_1 = find_candidates(steps, labels, width=1)

    print("Analizando candidatos (2 bytes)...")
    candidates_2 = find_candidates(steps, labels, width=2)

    print()
    print("================================")
    print("   RESULTADOS")
    print("================================")

    for width, candidates in (
        (1, candidates_1),
        (2, candidates_2),
    ):

        print()
        print(f"-- Candidatos de {width} byte(s): {len(candidates)} --")

        for offset, values in candidates[:20]:

            absolute_address = scan_start + offset
            relative_offset = absolute_address - center

            mapping = ", ".join(
                f"{label}={value}"
                for label, value in zip(labels, values)
            )

            sign = "+" if relative_offset >= 0 else ""

            print(
                f"  {hex(absolute_address)} "
                f"(ancla{sign}{hex(relative_offset)}): "
                f"{mapping}"
            )

        if len(candidates) > 20:
            print(
                f"  ... y {len(candidates) - 20} mas "
                f"(no se muestran todos)"
            )

    if not candidates_1 and not candidates_2:
        print()
        print(
            "Sin candidatos en esta ventana. Probar con "
            "--centro party, o repetir con una secuencia mas "
            "larga para descartar falsos positivos si aparecieron "
            "demasiados."
        )


if __name__ == "__main__":
    main()

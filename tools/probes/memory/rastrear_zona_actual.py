"""
Busca una direccion fija que identifique la zona/ruta actual del
jugador, comparando snapshots de memoria mientras te movés entre
distintos lugares del mapa.

Distinto de rastrear_slot_activo.py (la investigacion fallida del
slot en combate): ahi sabiamos de antemano el valor esperado
(indice 0-5). Aca NO sabemos como el juego codifica el ID de zona,
asi que en vez de pedir un valor exacto, pedis el NOMBRE de cada
lugar por el que pasas, y el script busca una direccion que cumpla
la regla logica que tiene que cumplir un "ID de zona" real:

    - Si volviste al MISMO lugar en dos pasos distintos, el valor
      en esa direccion tiene que ser IGUAL en ambos.
    - Si estuviste en lugares DISTINTOS, el valor tiene que ser
      DISTINTO.

Esto filtra mucho mejor que "cambio de valor" a secas: un timer
interno puede cambiar todo el tiempo, pero es muy dificil que por
casualidad tenga el mismo valor las dos veces que estuviste en la
misma ruta Y un valor distinto en cada ruta diferente.

COMO USARLO (necesitas volver a un lugar ya visitado al menos una
vez en la secuencia, para poder aplicar la regla de "mismo lugar =
mismo valor"):

    1. Anota el orden de lugares por los que vas a pasar, INCLUYENDO
       al menos una repeticion. Por ejemplo:
       Ruta101 -> CiudadPetalburgo -> Ruta101 -> Ruta104

    2. Corre:

           python -m tools.probes.memory.rastrear_zona_actual --secuencia "Ruta101,CiudadPetalburgo,Ruta101,Ruta104"

    3. El script te va pidiendo confirmar con Enter en cada lugar
       de la secuencia (parate ahi, fuera de combate y fuera de
       cualquier menu, antes de confirmar).

    4. Al final imprime los offsets candidatos (si los hay) que
       cumplieron la regla, tanto para valores de 1 byte como de
       2 bytes.

Repite con otra secuencia distinta (otra sesion) para confirmar que
el mismo offset se repite -- un solo intento puede tener falsos
positivos por casualidad, sobre todo con secuencias cortas.
"""

import argparse
import struct

from app.readers.azahar_reader import AzaharReader
from app.services.badges_service import BADGES_ADDRESS
from app.memory.pointers import PARTY_ORDER_ADDRESS


# Ventana de memoria a escanear, centrada en el ancla elegida.
# 256KB a cada lado (512KB total). Si no aparece nada, el siguiente
# paso logico es ampliar esto (mismo patron que ya se siguio con
# el slot de combate), pero arrancamos mas grande que ese caso
# porque aca no hay ninguna pista de "cerca de que" buscar.
WINDOW_BEFORE = 0x40000
WINDOW_AFTER = 0x40000

ANCHORS = {
    "badges": BADGES_ADDRESS,
    "party": PARTY_ORDER_ADDRESS,
}


def read_window(memory, start, size):
    data = memory.read(start, size)

    if len(data) != size:
        return None

    return data


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


def find_candidates(snapshots, labels, width):
    """
    Devuelve una lista de (offset, valores) para los offsets donde
    el valor de `width` bytes (little-endian) es igual en todos los
    pasos con la misma etiqueta, y distinto entre etiquetas
    distintas.
    """

    size = len(snapshots[0])

    unpack_format = "<B" if width == 1 else "<H"

    label_to_indices = {}

    for index, label in enumerate(labels):
        label_to_indices.setdefault(
            label,
            [],
        ).append(index)

    candidates = []

    for offset in range(size - width + 1):

        values = [
            struct.unpack(
                unpack_format,
                snapshot[offset:offset + width],
            )[0]
            for snapshot in snapshots
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
            # Dos lugares distintos con el mismo valor: no sirve
            # para distinguir zonas.
            continue

        candidates.append((offset, values))

    return candidates


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Busca una direccion de memoria que identifique la "
            "zona/ruta actual, usando una secuencia de lugares "
            "con al menos una repeticion."
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

    parser.add_argument(
        "--centro",
        choices=list(ANCHORS.keys()),
        default="badges",
        help=(
            "Direccion fija alrededor de la cual escanear. "
            "'badges' (por defecto) o 'party'."
        ),
    )

    args = parser.parse_args()
    labels = args.secuencia
    center = ANCHORS[args.centro]

    print("================================")
    print("   RASTREAR ZONA ACTUAL")
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

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
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

    snapshots = []

    for step_number, label in enumerate(labels, start=1):

        input(
            f"[Paso {step_number}/{len(labels)}] Parate en "
            f"'{label}' (fuera de combate/menus) y presiona "
            f"Enter..."
        )

        print(
            "Leyendo memoria (puede tardar varios segundos)..."
        )

        snapshot = read_window(
            memory,
            scan_start,
            scan_size,
        )

        if snapshot is None:
            print(f"Lectura del paso {step_number} fallo.")
            return

        snapshots.append(snapshot)
        print(f"Snapshot {step_number} capturado.")
        print()

    print("Analizando candidatos (1 byte)...")
    candidates_1 = find_candidates(snapshots, labels, width=1)

    print("Analizando candidatos (2 bytes)...")
    candidates_2 = find_candidates(snapshots, labels, width=2)

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
            "Sin candidatos en esta ventana. Puede que la "
            "direccion este mas lejos del ancla elegida, o "
            "codificada distinto (mas de 2 bytes, o no como "
            "entero simple). Probar con --centro party, o "
            "repetir con una secuencia mas larga para descartar "
            "falsos positivos si aparecieron demasiados."
        )


if __name__ == "__main__":
    main()

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

Ademas, en cada paso el script hace varias lecturas seguidas para
detectar, offset por offset, si el valor esta REALMENTE quieto
mientras estas parado (y no algo ligado al movimiento/animacion del
personaje, que puede coincidir por casualidad y colarse como falso
positivo -- paso ya por esto una vez, ver STABILITY_READS mas
abajo). Solo se consideran candidatos los offsets que fueron
estables en TODOS los pasos.

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
import time

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


# Cuantas lecturas seguidas se usan para detectar, POR OFFSET, si
# un valor esta quieto mientras el jugador esta parado. Agregado
# tras un falso positivo real (26/08/2026): un candidato coincidio
# por casualidad en dos corridas distintas, pero resulto ser algo
# ligado al movimiento del personaje (cambiaba varias veces por
# segundo), no un ID de zona fijo.
#
# IMPORTANTE (correccion 27/08/2026): la primera version de este
# filtro exigia que TODA la ventana de 512KB fuera identica en las
# N lecturas -- resulto ser una exigencia imposible de cumplir, un
# bloque asi de grande de la memoria de un juego SIEMPRE tiene algo
# cambiando en algun lado (temporizadores de sonido, contadores de
# frame, semillas de RNG, animaciones de fondo) aunque el jugador
# este perfectamente quieto. La version actual filtra por OFFSET
# individual: cada candidato se descarta por separado si SU propio
# byte(s) cambio durante las lecturas de estabilidad de cualquier
# paso, sin importar que otras partes de la ventana si hayan
# cambiado.
STABILITY_READS = 4

# Pausa entre lecturas de estabilidad. Tiene que ser lo bastante
# larga para que algo que cambia con el movimiento/animacion lo
# muestre (los ciclos normales del proyecto son de 200ms), pero sin
# hacer la espera desesperante.
STABILITY_DELAY_SECONDS = 0.3


def collect_stability_reads(memory, start, size):
    """
    Lee la ventana STABILITY_READS veces seguidas, con una pausa
    entre cada lectura. Devuelve la lista completa de lecturas (no
    filtra nada todavia -- eso lo hace build_stable_mask).
    """

    reads = []

    for _ in range(STABILITY_READS):

        snapshot = read_window(memory, start, size)

        if snapshot is None:
            return None

        reads.append(snapshot)
        time.sleep(STABILITY_DELAY_SECONDS)

    return reads


def build_stable_mask(reads):
    """
    A partir de varias lecturas de la misma ventana, devuelve un
    bytes() del mismo tamano donde cada posicion es 0x00 si ese
    byte fue IGUAL en todas las lecturas (estable), o distinto de
    0x00 si cambio en alguna (inestable -- descartar ese offset).

    Implementado con enteros grandes (XOR de toda la ventana de una
    sola vez) para que sea rapido incluso con una ventana de 512KB;
    un bucle byte a byte en Python puro seria demasiado lento para
    correr varias veces por sesion.
    """

    base = int.from_bytes(reads[0], "big")
    diff_mask = 0

    for snapshot in reads[1:]:
        diff_mask |= int.from_bytes(snapshot, "big") ^ base

    return diff_mask.to_bytes(len(reads[0]), "big")


def read_stable_step(memory, start, size):
    """
    Lee la ventana para un paso de la secuencia y arma tanto el
    snapshot base (primera lectura) como la mascara de estabilidad
    por offset. Devuelve (snapshot, stable_mask) o (None, None) si
    alguna lectura fallo.
    """

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
    """
    `steps` es una lista de (snapshot, stable_mask), uno por paso
    de la secuencia (mismo orden que `labels`).

    Devuelve una lista de (offset, valores) para los offsets donde:
      - el byte/los bytes fueron ESTABLES (no cambiaron durante las
        lecturas de estabilidad) en TODOS los pasos, y
      - el valor de `width` bytes (little-endian) es igual en todos
        los pasos con la misma etiqueta, y distinto entre etiquetas
        distintas.
    """

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
            "Sin candidatos en esta ventana. Puede que la "
            "direccion este mas lejos del ancla elegida, o "
            "codificada distinto (mas de 2 bytes, o no como "
            "entero simple). Probar con --centro party, o "
            "repetir con una secuencia mas larga para descartar "
            "falsos positivos si aparecieron demasiados."
        )


if __name__ == "__main__":
    main()

"""
Busca un offset RELATIVO a la base de combate (el puntero dinamico
que ya usa combat_service.py) que distinga un combate SALVAJE de un
combate contra ENTRENADOR.

Pieza 2 de 3 para la deteccion automatica de "perdido" en el
Nuzlocke Tracker (ver DexRelay_Contexto_Deteccion_Perdido.md).

Distinto de rastrear_zona_actual.py: ahi la direccion era FIJA y se
podia planear una secuencia de lugares de antemano. Aca la base de
combate es DINAMICA (se reubica en cada pelea, tal como ya esta
documentado en combat_service.py) y no se puede "programar" cuando
va a aparecer un combate salvaje vs uno de entrenador -- por eso
este script es un loop interactivo: vos activas el combate en el
juego, y mientras estas DENTRO (antes de que termine) le confirmas
al script que tipo fue.

COMO USARLO:

    python -m tools.probes.memory.buscar_flag_tipo_combate

    1. En el juego, entra a un combate (salvaje o de entrenador,
       cualquiera).
    2. TODAVIA DENTRO del combate (no lo termines todavia), volve a
       la terminal y escribi 's' (salvaje) o 'e' (entrenador), o
       'fin' para cortar y analizar lo recolectado hasta ahi.
    3. El script lee la ventana de memoria relativa a la base de
       combate en ese instante, valida que el puntero no haya
       cambiado a mitad de lectura (mismo patron que
       combat_service.py) y guarda la muestra.
    4. Repetir con varios combates de cada tipo -- cuantos mas,
       mejor filtra (recomendado: al menos 3 de cada tipo antes de
       terminar, idealmente 5+).
    5. Escribi 'fin' cuando termines. Imprime los offsets candidatos
       (relativos a la base de combate) que fueron constantes
       dentro de cada categoria y distintos entre categorias.

Si un combate termina antes de que llegues a confirmarlo, no pasa
nada -- el proximo intento de lectura va a fallar la validacion de
consistencia del puntero (como ya hace combat_service.py) y el
script te va a avisar para que lo intentes de nuevo con otro
combate.
"""

import argparse
import struct
import time

from app.readers.azahar_reader import AzaharReader


COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4

DEFAULT_WINDOW_START_OFFSET = -0x200
DEFAULT_WINDOW_SIZE = 0x1000  # 4096 bytes


def read_combat_base(memory):
    """
    Lee la base de combate actual, validando consistencia (mismo
    patron que CombatService.read()). Devuelve la direccion base si
    hay un combate activo y la lectura fue consistente, o None si
    no hay combate / la lectura no fue confiable.
    """

    pointer_before = memory.read(COMBAT_POINTER_ADDRESS, 4)

    if len(pointer_before) != 4:
        return None

    base_address = struct.unpack("<I", pointer_before)[0]

    if base_address in (0, COMBAT_INACTIVE_POINTER):
        return None

    return base_address


def read_window_relative_to_combat(memory, window_start_offset, window_size):
    """
    Lee la ventana de memoria relativa a la base de combate,
    validando que el puntero no haya cambiado entre el momento en
    que se leyo la base y el momento en que se termino de leer la
    ventana (mismo patron defensivo que combat_service.py).

    Devuelve (base_address, snapshot) o (None, None) si no hay
    combate activo o la lectura no fue consistente.
    """

    base_before = read_combat_base(memory)

    if base_before is None:
        return None, None

    snapshot = memory.read(
        base_before + window_start_offset,
        window_size,
    )

    if len(snapshot) != window_size:
        return None, None

    base_after = read_combat_base(memory)

    if base_after != base_before:
        return None, None

    return base_before, snapshot


def find_candidates(samples, width):
    """
    `samples` es una lista de (label, snapshot), label es 's' o 'e'.

    Devuelve una lista de (offset_relativo, valor_salvaje,
    valor_entrenador) para los offsets donde el valor es constante
    dentro de cada categoria y distinto entre 's' y 'e'.
    """

    size = len(samples[0][1])
    unpack_format = "<B" if width == 1 else "<H"

    by_label = {"s": [], "e": []}

    for label, snapshot in samples:
        by_label[label].append(snapshot)

    candidates = []

    for offset in range(size - width + 1):

        values_by_label = {}
        consistent = True

        for label, snapshots in by_label.items():

            values = [
                struct.unpack(
                    unpack_format,
                    snapshot[offset:offset + width],
                )[0]
                for snapshot in snapshots
            ]

            if any(v != values[0] for v in values[1:]):
                consistent = False
                break

            values_by_label[label] = values[0]

        if not consistent:
            continue

        if values_by_label["s"] == values_by_label["e"]:
            continue

        candidates.append(
            (
                offset,
                values_by_label["s"],
                values_by_label["e"],
            )
        )

    return candidates


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Busca un flag salvaje/entrenador relativo a la base "
            "de combate."
        )
    )
    parser.add_argument(
        "--start",
        type=lambda s: int(s, 0),
        default=DEFAULT_WINDOW_START_OFFSET,
        help=(
            "Offset de inicio de la ventana relativo a la base de "
            "combate (puede ser negativo). Default: "
            f"{hex(DEFAULT_WINDOW_START_OFFSET)}"
        ),
    )
    parser.add_argument(
        "--size",
        type=lambda s: int(s, 0),
        default=DEFAULT_WINDOW_SIZE,
        help=(
            f"Tamano de la ventana en bytes. Default: "
            f"{hex(DEFAULT_WINDOW_SIZE)}"
        ),
    )
    args = parser.parse_args()

    print("================================")
    print("   BUSCAR FLAG TIPO DE COMBATE")
    print("================================")
    print()
    print(
        f"Ventana relativa a la base de combate: "
        f"[{hex(args.start)}, {hex(args.start + args.size)})"
    )
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print()
    print(
        "Entra a un combate en el juego. TODAVIA DENTRO del "
        "combate, volve aca y escribi 's' (salvaje) o 'e' "
        "(entrenador). Escribi 'fin' para cortar y analizar."
    )
    print()

    memory = reader.memory
    samples = []
    counts = {"s": 0, "e": 0}

    while True:

        label = input(
            f"[s={counts['s']} e={counts['e']}] "
            f"Tipo de combate actual (s/e/fin): "
        ).strip().lower()

        if label in ("fin", "salir", "exit"):
            break

        if label not in ("s", "e"):
            print("  Escribi 's', 'e', o 'fin'.")
            continue

        base_address, snapshot = read_window_relative_to_combat(
            memory,
            args.start,
            args.size,
        )

        if snapshot is None:
            print(
                "  No se detecto un combate activo (o el puntero "
                "cambio a mitad de lectura). Confirma que seguis "
                "DENTRO del combate y proba de nuevo."
            )
            continue

        samples.append((label, snapshot))
        counts[label] += 1

        nombre = "salvaje" if label == "s" else "entrenador"
        print(
            f"  Muestra guardada ({nombre}). Base de combate: "
            f"{hex(base_address)}"
        )
        print()

    print()

    if counts["s"] == 0 or counts["e"] == 0:
        print(
            "Hacen falta muestras de AMBOS tipos (salvaje y "
            "entrenador) para poder comparar. No se analizo nada."
        )
        return

    print(
        f"Analizando {counts['s']} muestras salvajes y "
        f"{counts['e']} de entrenador..."
    )
    print()

    for width in (1, 2):

        print(f"-- Candidatos de {width} byte(s) --")

        candidates = find_candidates(samples, width)

        if not candidates:
            print("  (ninguno)")
        else:
            for window_offset, wild_value, trainer_value in candidates:
                # Offset REAL relativo a la base de combate: hay
                # que sumarle args.start, porque find_candidates
                # trabaja con indices dentro de la ventana leida
                # (que arranca en base + args.start), no con la
                # posicion real relativa a la base.
                real_offset = args.start + window_offset
                sign = "+" if real_offset >= 0 else "-"
                print(
                    f"  offset {sign}{hex(abs(real_offset))}: "
                    f"salvaje={wild_value}  "
                    f"entrenador={trainer_value}"
                )

        print()


if __name__ == "__main__":
    main()

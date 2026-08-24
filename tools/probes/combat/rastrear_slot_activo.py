"""
Busca la direccion fija que guarda el indice del Pokemon activo en
combate (0-5), tomando una SECUENCIA de snapshots (no solo
antes/despues) mientras cambias de Pokemon varias veces dentro del
mismo combate.

Por que una secuencia y no solo un antes/despues:
La primera version (un solo cambio, ej. slot 1 -> slot 3) devolvio
mas de 140 direcciones candidatas. Eso pasa porque muchos contadores
o temporizadores internos del juego pasan por casualidad de 0 a 2 en
algun momento del combate; un solo cambio no alcanza para
descartarlos. Si en cambio pedimos que una direccion coincida con el
indice correcto en 3, 4 o mas pasos SEGUIDOS (ej. 0 -> 2 -> 4 -> 1),
la probabilidad de que sea pura coincidencia baja muchisimo: cuantos
mas pasos, mas se reduce la lista, hasta quedar (idealmente) con una
sola direccion real.

COMO USARLO:

    1. Entra a combate.
    2. Corre el script pasandole la secuencia de slots por la que
       vas a pasar, en orden, separados por comas:

           python -m tools.probes.combat.rastrear_slot_activo --secuencia 1,3,5,2

    3. El script te va a pedir confirmar con Enter en cada paso:
       primero confirmas que el slot 1 esta activo, tomas snapshot;
       cambias a slot 3, confirmas, snapshot; cambias a slot 5,
       confirmas, snapshot; cambias a slot 2, confirmas, snapshot.
    4. Al final imprime SOLO las direcciones cuyo valor coincidio
       con el slot esperado en TODOS los pasos de la secuencia.

Mientras mas pasos uses (idealmente 4 o mas, con slots bien
variados, no solo alternando entre 2), mejor se filtra el ruido.
"""

import argparse

from app.readers.azahar_reader import AzaharReader
from app.services.combat_service import COMBAT_POINTER_ADDRESS


# Ventana de memoria global a escanear, centrada en
# COMBAT_POINTER_ADDRESS. 1MB de margen a cada lado (2MB total).
# Ampliado desde 0x8000 (64KB) porque esa ventana no dio ningun
# resultado con una secuencia de 4 pasos.
WINDOW_BEFORE = 0x100000
WINDOW_AFTER = 0x100000


def read_window(memory, start, size):
    data = memory.read(start, size)

    if len(data) != size:
        return None

    return data


def parse_sequence(raw_value):
    slots = []

    for piece in raw_value.split(","):

        piece = piece.strip()

        if not piece:
            continue

        slot_number = int(piece)

        if slot_number < 1 or slot_number > 6:
            raise argparse.ArgumentTypeError(
                f"Slot invalido: {slot_number} (debe ser 1-6)"
            )

        slots.append(slot_number)

    if len(slots) < 2:
        raise argparse.ArgumentTypeError(
            "La secuencia necesita al menos 2 slots."
        )

    return slots


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Toma una secuencia de snapshots mientras cambias de "
            "Pokemon activo en combate, para encontrar el offset "
            "fijo del indice de slot activo con mucha mas precision "
            "que un solo antes/despues."
        )
    )

    parser.add_argument(
        "--secuencia",
        type=parse_sequence,
        required=True,
        help=(
            "Slots (1-6) por los que vas a pasar, en orden, "
            "separados por comas. Ej: 1,3,5,2"
        ),
    )

    args = parser.parse_args()
    slot_sequence = args.secuencia
    index_sequence = [slot - 1 for slot in slot_sequence]

    print("================================")
    print("   RASTREAR SLOT ACTIVO (COMBATE)")
    print("           v2 - secuencia")
    print("================================")
    print()
    print(
        "Secuencia de slots: "
        + " -> ".join(str(slot) for slot in slot_sequence)
    )
    print(
        "Secuencia de indices: "
        + " -> ".join(str(index) for index in index_sequence)
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

    scan_start = COMBAT_POINTER_ADDRESS - WINDOW_BEFORE
    scan_size = WINDOW_BEFORE + WINDOW_AFTER

    print(
        f"Ventana de escaneo: {hex(scan_start)} - "
        f"{hex(scan_start + scan_size)} "
        f"(COMBAT_POINTER_ADDRESS +/- {hex(WINDOW_BEFORE)})"
    )
    print()

    snapshots = []

    for step_number, slot_number in enumerate(slot_sequence, start=1):

        input(
            f"[Paso {step_number}/{len(slot_sequence)}] Confirma que "
            f"el Pokemon activo es el del slot {slot_number} y "
            f"presiona Enter para tomar el snapshot..."
        )

        print("Leyendo memoria (~2MB, puede tardar varios segundos)...")

        snapshot = read_window(memory, scan_start, scan_size)

        if snapshot is None:
            print(f"Lectura del snapshot {step_number} fallo.")
            return

        snapshots.append(snapshot)
        print(f"Snapshot {step_number} capturado.")
        print()

    # --- Interseccion: la direccion tiene que cumplir el indice
    #     esperado en TODOS los pasos ---

    matches = []

    for offset in range(scan_size):

        values_at_offset = [
            snapshot[offset] for snapshot in snapshots
        ]

        if values_at_offset == index_sequence:
            absolute_address = scan_start + offset
            matches.append(absolute_address)

    if not matches:
        print(
            "No se encontro ninguna direccion que haya seguido "
            "exactamente esa secuencia de valores. Puede que este "
            "fuera de esta ventana, o que no se almacene como un "
            "solo byte."
        )
        return

    print(f"{len(matches)} direccion(es) candidata(s) (sobrevivieron toda la secuencia):")

    for address in matches:
        offset_from_pointer = address - COMBAT_POINTER_ADDRESS

        print(
            f"  {hex(address)}  "
            f"(COMBAT_POINTER_ADDRESS {'+' if offset_from_pointer >= 0 else ''}"
            f"{hex(offset_from_pointer)})"
        )

    print()

    if len(matches) == 1:
        print("Una sola direccion sobrevivio: candidata muy fuerte.")
    else:
        print(
            "Todavia hay varias. Repite con otra secuencia distinta "
            "(otro combate) y quedate solo con las direcciones que "
            "aparezcan en ambas corridas."
        )


if __name__ == "__main__":
    main()

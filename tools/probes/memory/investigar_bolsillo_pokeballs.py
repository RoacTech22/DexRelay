"""
Bloque 4.4 (guía siguiente versión, 23/09/2026): investigación del
bolsillo de Poké Balls -- primer paso hacia detectar "ya tengo
Poké Balls" para definir el inicio real de un Nuzlocke (encuentros/
muertes antes de la primera Poké Ball no deberían contar).

PISTA FUERTE YA EXISTENTE, sin confirmar todavía post-1.4: en una
sesión anterior (ver confirmar_bolsa_items.py), un candidato del
bolsillo de Poké Balls quedó confirmado en vivo:

    Alpha Sapphire (BASE, antes del parche): 0x08C6AC84 (Ultra Ball,
      23 -> 22)
    Omega Ruby:                              0x08C6EC70 (Poké Ball,
      4 -> 3)

El candidato de Omega Ruby (0x08C6EC70) coincide EXACTO con
BAG_START_ADDRESS tal como está HOY (get_bag_start_address()),
que además ya convergió entre Alpha Sapphire 1.4 y Omega Ruby (ver
pointers.py). Fuerte indicio de que el bolsillo de Poké Balls
empieza justo al principio de la bolsa -- pero es un indicio, no
una confirmación: el candidato de Omega Ruby se validó ANTES de la
migración de Alpha Sapphire a 1.4, y nunca se confirmó
específicamente "esto es el bolsillo de Poké Balls" con un dump
completo mirando los límites reales (mismo método que ya se usó
para encontrar el bolsillo de Medicina, ver dump_pocket_medicina.py
y buscar_pocket_medicina.py).

QUÉ HACE ESTE SCRIPT (solo lectura, no escribe nada):

    1. Dump manual desde BAG_START_ADDRESS hasta un poco después de
       MEDICINE_POCKET_START_ADDRESS (calculado, no un número fijo) -- para comparar a ojo contra lo que
       tenés REALMENTE en el bolsillo de Poké Balls del juego
       (mismo orden, mismos item_id, mismas cantidades).
    2. Auto-detección del tramo contiguo de casilleros con "forma
       válida" (mismo criterio que confirmar_bolsa_items.py) --
       para ver dónde termina ese tramo (debería cortar con una
       racha de (0,0) antes de llegar a MEDICINE_POCKET_START_ADDRESS,
       marcado explícitamente en el dump si cae dentro de la
       ventana).

CÓMO USARLO:

    python -m tools.probes.memory.investigar_bolsillo_pokeballs

Antes de correrlo: fijate bien QUÉ Poké Balls tenés (tipo, orden,
cantidad) abriendo la bolsa en el juego, para poder comparar contra
lo que imprime.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from tools.probes.legacy_pointers import (
    get_bag_start_address,
    get_bag_end_address,
    get_medicine_pocket_start_address,
)


SLOT_SIZE = 4

# Margen extra a mostrar DESPUÉS de MEDICINE_POCKET_START_ADDRESS,
# para confirmar visualmente que ahí sí hay items reales de
# Medicina (ancla ya conocida) y no seguir en zona vacía.
MARGIN_AFTER_MEDICINE_SLOTS = 20

# Cuántos casilleros seguidos con forma válida hacen falta para
# contar como "tramo real" -- mismo criterio que
# confirmar_bolsa_items.py.
MIN_RUN_LENGTH = 5
MAX_PLAUSIBLE_ITEM_ID = 999
MAX_PLAUSIBLE_QUANTITY = 999

# Rachas de (0,0) de al menos este largo se colapsan a una sola
# línea de resumen en el dump -- la distancia real entre
# BAG_START_ADDRESS y MEDICINE_POCKET_START_ADDRESS puede ser de
# varios cientos de casilleros, la enorme mayoría vacíos; listarlos
# uno por uno haría el dump imposible de leer.
COLLAPSE_EMPTY_RUN_FROM = 8


def decode_slot(data, offset):
    return struct.unpack("<HH", data[offset:offset + SLOT_SIZE])


def slot_is_plausible(item_id, quantity):
    if item_id == 0 and quantity == 0:
        return True

    return (
        1 <= item_id <= MAX_PLAUSIBLE_ITEM_ID
        and 1 <= quantity <= MAX_PLAUSIBLE_QUANTITY
    )


def dump_and_find_runs(memory, start, medicine_start):
    # El dump SIEMPRE llega hasta un poco después de
    # MEDICINE_POCKET_START_ADDRESS (con margen), sin importar
    # cuántos casilleros haya en el medio -- calculado, no
    # adivinado, así el corte real del bolsillo de Poké Balls
    # (donde sea que esté) siempre queda a la vista.
    dump_slots = (
        (medicine_start - start) // SLOT_SIZE
    ) + MARGIN_AFTER_MEDICINE_SLOTS
    size = dump_slots * SLOT_SIZE

    data = memory.read(start, size)

    if data is None or len(data) != size:
        print("No se pudo leer la zona de la bolsa.")
        return

    print("================================")
    print("   DUMP DESDE BAG_START_ADDRESS")
    print("================================")
    print(
        f"({dump_slots} casilleros, hasta "
        f"{MARGIN_AFTER_MEDICINE_SLOTS} después de "
        "MEDICINE_POCKET_START_ADDRESS -- las rachas de "
        f"{COLLAPSE_EMPTY_RUN_FROM}+ casilleros vacíos seguidos se "
        "colapsan a una línea de resumen)"
    )
    print()

    current_run_start = None
    current_run_length = 0
    runs = []

    # Buffer de líneas de casilleros vacíos pendientes de imprimir
    # (o colapsar) -- se vacía apenas aparece un casillero no vacío
    # o termina el dump.
    pending_empty = []

    def flush_pending_empty():
        if not pending_empty:
            return
        if len(pending_empty) >= COLLAPSE_EMPTY_RUN_FROM:
            first_addr, last_addr = pending_empty[0], pending_empty[-1]
            print(
                f"  ... {len(pending_empty)} casilleros vacíos "
                f"(0x{first_addr:08X} - 0x{last_addr:08X}) ..."
            )
        else:
            for addr in pending_empty:
                print(f"0x{addr:08X}  item_id=   0  cantidad=   0  [OK]")
        pending_empty.clear()

    for index in range(0, size, SLOT_SIZE):
        address = start + index
        item_id, quantity = decode_slot(data, index)
        plausible = slot_is_plausible(item_id, quantity)
        is_empty = item_id == 0 and quantity == 0

        if is_empty:
            if address == medicine_start:
                flush_pending_empty()
                print(
                    f"0x{address:08X}  item_id=   0  cantidad=   0  "
                    "[OK]  <-- ACÁ EMPIEZA EL BOLSILLO DE MEDICINA "
                    "(confirmado, pero vacío -- raro, revisar)"
                )
            else:
                pending_empty.append(address)
        else:
            flush_pending_empty()

            marker = ""
            if address == medicine_start:
                marker = "  <-- ACÁ EMPIEZA EL BOLSILLO DE MEDICINA (confirmado)"

            print(
                f"0x{address:08X}  item_id={item_id:>4}  "
                f"cantidad={quantity:>4}  "
                f"[{'OK' if plausible else '??'}]{marker}"
            )

        if plausible:
            if current_run_start is None:
                current_run_start = address
            current_run_length += 1
        else:
            if current_run_length >= MIN_RUN_LENGTH:
                runs.append((current_run_start, current_run_length))
            current_run_start = None
            current_run_length = 0

    flush_pending_empty()

    if current_run_length >= MIN_RUN_LENGTH:
        runs.append((current_run_start, current_run_length))

    print()
    print("================================")
    print("   TRAMOS CONTIGUOS CON FORMA VÁLIDA")
    print("================================")
    print()

    if not runs:
        print("Ningún tramo de al menos", MIN_RUN_LENGTH, "casilleros seguidos.")
        return

    for run_start, length in runs:
        run_end = run_start + length * SLOT_SIZE
        print(
            f"Tramo: 0x{run_start:08X} - 0x{run_end:08X} "
            f"({length} casilleros)"
        )

    print()
    print(
        "Comparar el PRIMER tramo (el que arranca en "
        f"0x{start:08X}) contra lo que tenés REALMENTE en el "
        "bolsillo de Poké Balls del juego: mismo orden, mismos "
        "item_id, mismas cantidades. Si calza, ese tramo completo "
        "es el bolsillo de Poké Balls -- anotar dónde termina "
        "exactamente (el primer (0,0) después del último item real, "
        "no el final del tramo detectado, que puede incluir alguna "
        "racha corta de ceros DENTRO del bolsillo sin ser el corte "
        "real -- mirar el dump de arriba con cuidado)."
    )


def main():
    print("================================")
    print(" DEXRELAY INVESTIGAR BOLSILLO POKÉ BALLS")
    print("================================")
    print()

    reader = AzaharReader(process_name=None)

    print("Buscando proceso (sango-1 / sango-2)...")

    if not reader.connect():
        print("No se encontró ningún proceso conocido.")
        return

    print(f"Azahar conectado correctamente. Proceso: {reader.process_name}")
    print()

    bag_start = get_bag_start_address(reader.process_name)
    bag_end = get_bag_end_address(reader.process_name)
    medicine_start = get_medicine_pocket_start_address(reader.process_name)

    print(f"BAG_START_ADDRESS:            0x{bag_start:08X}")
    print(f"BAG_END_ADDRESS:              0x{bag_end:08X}")
    print(f"MEDICINE_POCKET_START_ADDRESS: 0x{medicine_start:08X}")
    print()

    dump_and_find_runs(reader.memory, bag_start, medicine_start)


if __name__ == "__main__":
    main()

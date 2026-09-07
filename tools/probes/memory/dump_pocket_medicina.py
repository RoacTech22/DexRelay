"""
Dump amplio alrededor del anclaje confirmado del bolsillo de
MEDICINA (item_id=28 Revivir, 6 -> 5, confirmado en vivo por
buscar_pocket_medicina.py), para encontrar los limites reales de
ese bolsillo -- mismo objetivo que confirmar_bolsa_items.py tuvo
para el bolsillo de Poke Balls, pero la auto-deteccion de tramos de
ese script NO sirve aca: todo el tramo grande (BAG_START/END) ya es
"forma valida" de punta a punta, no hay forma de distinguir un
bolsillo del de al lado solo mirando si los bytes tienen pinta de
item real -- hace falta mirar el dump a ojo y buscar el corte real
(una racha larga de (0,0) que separe un bolsillo del siguiente).

COMO USARLO:

    python -m tools.probes.memory.dump_pocket_medicina

Solo lectura -- no escribe nada, no hace falta tocar el juego mas
alla de tenerlo abierto y conectado.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


# Anclaje confirmado en vivo: item_id=28 (Revivir), casillero
# empieza 2 bytes antes del byte que cambio (mismo criterio que el
# resto de los probes de esta investigacion).
_MEDICINE_ANCHOR_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6B5F2 - 2,
    # Omega Ruby: direccion calculada sumando el offset constante
    # (0x3FF0) ya confirmado entre AS y OR para el tramo completo de
    # la bolsa -- CONFIRMADA en vivo el mismo dia (el usuario agrego
    # Caramelo Raro con esta direccion y el juego lo mostro/conto
    # bien dentro de Medicina en un save real de Omega Ruby).
    PROCESS_NAME_OMEGA_RUBY: 0x08C6B5F0 + 0x3FF0,
}

SLOT_SIZE = 4

# Bastante margen para los dos lados -- un bolsillo de Medicina
# real puede tener varias decenas de casilleros de capacidad.
DUMP_SLOTS_BEFORE = 60
DUMP_SLOTS_AFTER = 60


def decode_slot(data, offset):
    return struct.unpack("<HH", data[offset:offset + SLOT_SIZE])


def dump_manual(memory, anchor_address):
    start = anchor_address - DUMP_SLOTS_BEFORE * SLOT_SIZE
    size = (DUMP_SLOTS_BEFORE + 1 + DUMP_SLOTS_AFTER) * SLOT_SIZE

    data = memory.read(start, size)

    if data is None or len(data) != size:
        print("No se pudo leer la zona del anclaje.")
        return

    print("================================")
    print("   DUMP ALREDEDOR DEL BOLSILLO DE MEDICINA")
    print("================================")
    print()

    for index in range(0, size, SLOT_SIZE):
        address = start + index
        item_id, quantity = decode_slot(data, index)

        marker = " <-- ANCLAJE (Revivir)" if address == anchor_address else ""

        print(
            f"0x{address:08X}  item_id={item_id:>4}  "
            f"cantidad={quantity:>4}{marker}"
        )

    print()
    print(
        "Buscar a ojo: donde termina la racha de (0,0) ANTES de "
        "llegar a item_id/cantidad reales -- ese es el limite de "
        "inicio del bolsillo (o el final del bolsillo anterior). "
        "Lo mismo del lado de despues -- donde vuelve a arrancar "
        "una racha larga de (0,0) es el limite de fin. Si un item "
        "real aparece MUY cerca de un extremo sin racha de ceros "
        "clara, probablemente ese extremo cae dentro de otro "
        "bolsillo -- avisar para ampliar DUMP_SLOTS_BEFORE/AFTER."
    )


def main():
    print("================================")
    print(" DEXRELAY DUMP BOLSILLO MEDICINA")
    print("================================")
    print()

    reader = AzaharReader(process_name=None)

    print("Buscando proceso (sango-1 / sango-2)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    print(f"Azahar conectado correctamente. Proceso: {reader.process_name}")
    print()

    anchor_address = _MEDICINE_ANCHOR_ADDRESS_BY_PROCESS.get(
        reader.process_name
    )

    if anchor_address is None:
        print(
            f"No hay un anclaje confirmado todavia para "
            f"'{reader.process_name}' -- correr primero "
            f"buscar_pocket_medicina.py contra esta version."
        )
        return

    print(f"Anclaje a usar: 0x{anchor_address:08X}")
    print()

    dump_manual(reader.memory, anchor_address)


if __name__ == "__main__":
    main()

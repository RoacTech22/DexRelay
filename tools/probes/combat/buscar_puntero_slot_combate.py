"""
Busca dentro (y alrededor) de la estructura de combate (base_address)
un puntero de 4 bytes que apunte de vuelta a la direccion real de
alguno de los 6 miembros de la party.

Por que este enfoque y no buscar el speciesId directo:
buscar_offset_slot_combate.py buscaba el speciesId como valor de 2
bytes dentro de la estructura, pero las pruebas mostraron que un
speciesId chico (15) aparecia por pura coincidencia en un par de
offsets, mientras que otro speciesId (92) no aparecia en ningun
lado. Eso indica que la estructura de combate probablemente NO
duplica el speciesId como numero plano; lo mas probable es que
tenga un PUNTERO de vuelta a la estructura del Pokemon real dentro
de la party (la misma direccion que ya calculas al leer la party
via PARTY_ORDER_ADDRESS + POKEMON_POINTER_OFFSET). Una direccion de
memoria de 32 bits es un valor mucho mas especifico que un speciesId
chico, asi que un match ahi es una senal mucho mas confiable.

Version 2: la primera pasada solo escaneaba 0x600 bytes HACIA
ADELANTE desde base_address y no encontro nada. Puede que el puntero
de vuelta este mas lejos, o ANTES de base_address (es decir, que
base_address no sea el inicio real del bloque, sino un puntero a la
mitad de una estructura mas grande). Esta version escanea una
ventana mas amplia en ambas direcciones.

COMO USARLO:

    1. Entra a combate con cualquier Pokemon de tu party.
    2. Corre:

           python -m tools.probes.combat.buscar_puntero_slot_combate

    3. El script lee la party completa (para saber la direccion
       real de cada uno de los 6 slots) y escanea alrededor de la
       estructura de combate buscando esas direcciones. Imprime en
       que offset (relativo a base_address, puede ser negativo)
       aparece la direccion de que slot.
    4. Anota el resultado.
    5. Sal, entra a otro combate con OTRO Pokemon (otro slot, de
       verdad distinto: sal del juego a otro Pokemon, no solo
       cambies el argumento del script) y repite.
    6. El offset correcto es el que se repite igual en todas las
       pruebas, pero apuntando cada vez al slot correcto que
       mandaste a pelear.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import POKEMON_POINTER_OFFSET
from app.services.combat_service import (
    COMBAT_INACTIVE_POINTER,
    COMBAT_POINTER_ADDRESS,
)


# Bytes escaneados ANTES de base_address (por si base_address no es
# el inicio real del bloque de memoria del Pokemon en combate).
SCAN_BEFORE = 0x800

# Bytes escaneados DESPUES de base_address.
SCAN_AFTER = 0x2000


def main():
    print("================================")
    print(" BUSCAR PUNTERO DE SLOT EN COMBATE")
    print("================================")
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print()

    memory = reader.memory

    # --- Direcciones reales de los 6 miembros de la party ---

    raw_pointers = reader.read_party_order()

    if not raw_pointers:
        print("No se pudo leer la tabla de orden de la party.")
        return

    print("Direcciones de la party (slot -> puntero crudo / direccion de datos):")

    slot_addresses = {}

    for index, raw_pointer in enumerate(raw_pointers):

        slot_number = index + 1

        if raw_pointer == 0:
            print(f"  slot {slot_number}: vacio")
            continue

        data_address = raw_pointer + POKEMON_POINTER_OFFSET

        slot_addresses[slot_number] = {
            "raw_pointer": raw_pointer,
            "data_address": data_address,
        }

        print(
            f"  slot {slot_number}: "
            f"raw_pointer={hex(raw_pointer)}  "
            f"data_address={hex(data_address)}"
        )

    print()

    # --- Estructura de combate ---

    pointer_bytes = memory.read(
        COMBAT_POINTER_ADDRESS,
        4,
    )

    if len(pointer_bytes) != 4:
        print("No se pudo leer el puntero de combate.")
        return

    base_address = struct.unpack(
        "<I",
        pointer_bytes,
    )[0]

    if base_address in (0, COMBAT_INACTIVE_POINTER):
        print(
            "No hay combate activo ahora mismo "
            f"(base_address={hex(base_address)}). "
            "Entra a combate y vuelve a correr el script."
        )
        return

    scan_start = base_address - SCAN_BEFORE
    scan_size = SCAN_BEFORE + SCAN_AFTER

    print(f"base_address (estructura de combate) = {hex(base_address)}")
    print(
        f"Escaneando de {hex(scan_start)} a "
        f"{hex(scan_start + scan_size)} "
        f"(base_address - {hex(SCAN_BEFORE)} hasta "
        f"base_address + {hex(SCAN_AFTER)})..."
    )
    print()

    data = memory.read(
        scan_start,
        scan_size,
    )

    if len(data) != scan_size:
        print("Lectura de la ventana de escaneo incompleta/fallida.")
        return

    # --- Escaneo: cada 4 bytes de la ventana, ¿coincide con
    #     alguna direccion de party conocida? ---

    found_any = False

    for offset in range(len(data) - 3):

        candidate = struct.unpack(
            "<I",
            data[offset:offset + 4],
        )[0]

        for slot_number, addresses in slot_addresses.items():

            relative_offset = offset - SCAN_BEFORE

            if candidate == addresses["raw_pointer"]:
                found_any = True
                print(
                    f"  offset {hex(relative_offset)} "
                    f"(relativo a base_address): coincide con "
                    f"raw_pointer del slot {slot_number}"
                )

            elif candidate == addresses["data_address"]:
                found_any = True
                print(
                    f"  offset {hex(relative_offset)} "
                    f"(relativo a base_address): coincide con "
                    f"data_address del slot {slot_number}"
                )

    if not found_any:
        print(
            "  No se encontro ninguna coincidencia ni siquiera con "
            "la ventana ampliada. Probemos otra hipotesis (ej. un "
            "indice de slot de 1 byte en vez de un puntero)."
        )

    print()
    print(
        "Repite con otro Pokemon (otro slot, cambiado de verdad en "
        "el juego) y compara: el offset correcto es el que se "
        "repite igual, apuntando cada vez al slot correcto."
    )


if __name__ == "__main__":
    main()


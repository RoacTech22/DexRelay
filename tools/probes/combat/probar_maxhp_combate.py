"""
Prueba rapida: el HP de combate ya confirmado esta en
COMBAT_POINTER_ADDRESS -> base_address + 0x404. En la estructura de
un Pokemon normal (Pokemon6 en structures.py), el HP maximo esta
justo despues del HP actual (0xF0 -> hp, 0xF2 -> maxHp). Esta prueba
verifica si la estructura de combate sigue el mismo patron: HP
maximo en base_address + 0x406.

COMO USARLO:

    1. Antes de entrar a combate, mira /api/team y anota el maxHp
       del Pokemon que vas a mandar a pelear.
    2. Entra a combate con el.
    3. Corre:

           python -m tools.probes.combat.probar_maxhp_combate

    4. Compara el valor que imprime contra el maxHp que anotaste.

Si coincide, quiere decir que podemos usar el maxHp de combate para
identificar cual de los 6 slots esta peleando (comparando contra el
maxHp de cada slot en /api/team), en vez de asumir siempre el slot 1.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.services.combat_service import (
    COMBAT_HP_OFFSET,
    COMBAT_INACTIVE_POINTER,
    COMBAT_POINTER_ADDRESS,
)


# Hipotesis: el HP maximo esta 2 bytes despues del HP actual,
# siguiendo el mismo patron que Pokemon6 (hp en 0xF0, maxHp en 0xF2).
MAX_HP_OFFSET = COMBAT_HP_OFFSET + 2


def main():
    print("================================")
    print("   PROBAR MAXHP EN COMBATE")
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
            "No hay combate activo ahora mismo. "
            "Entra a combate y vuelve a correr el script."
        )
        return

    hp_bytes = memory.read(
        base_address + COMBAT_HP_OFFSET,
        2,
    )

    max_hp_bytes = memory.read(
        base_address + MAX_HP_OFFSET,
        2,
    )

    if len(hp_bytes) != 2 or len(max_hp_bytes) != 2:
        print("Lectura fallida.")
        return

    hp = struct.unpack("<H", hp_bytes)[0]
    max_hp = struct.unpack("<H", max_hp_bytes)[0]

    print(f"HP actual (offset {hex(COMBAT_HP_OFFSET)}):     {hp}")
    print(f"HP maximo (offset {hex(MAX_HP_OFFSET)}, hipotesis): {max_hp}")
    print()
    print(
        "Compara el HP maximo de arriba contra el maxHp que "
        "anotaste en /api/team antes de entrar a combate."
    )


if __name__ == "__main__":
    main()

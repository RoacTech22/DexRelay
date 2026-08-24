"""
Busca en la estructura de combate (base_address, la misma que usa
CombatService para el HP en +0x404) que offset contiene datos que
identifiquen que Pokemon de la party esta peleando.

Idea: ya sabemos, mirando /api/team justo antes de entrar a combate,
que Pokemon mandaste (su speciesId y su numero de slot, 1-6). Este
script escanea toda la estructura buscando esos dos valores como
candidatos:

    - speciesId como entero de 2 bytes (little-endian), en cada
      offset de la estructura.
    - (slot - 1) como un solo byte (0-5), en cada offset.

Imprime todos los offsets donde aparece cada valor. Un offset real
va a aparecer SIEMPRE que hagas la prueba, sin importar que Pokemon
mandes; un offset "casualidad" (choque numerico) va a desaparecer o
cambiar de resultado entre pruebas distintas.

COMO USARLO (repite esto con AL MENOS 2 combates distintos, mandando
Pokemon de slots y especies diferentes cada vez):

    1. Antes de entrar a combate, mira /api/team y anota:
       - speciesId del Pokemon que vas a mandar
       - su numero de slot (1-6)
    2. Entra a combate con ese Pokemon.
    3. Corre este script y pasale esos dos valores:

           python -m tools.probes.combat.buscar_offset_slot_combate --species-id 659 --slot 1

    4. Anota los offsets candidatos que imprime.
    5. Sal, entra a otro combate con OTRO Pokemon (distinta especie
       y/o distinto slot) y repite.
    6. El offset correcto es el que aparece IGUAL en todas las
       pruebas (por ejemplo, si species_id aparece en el offset 0x20
       en las 3 pruebas, ese es el offset real de species dentro de
       la estructura de combate).

Una vez identificado el offset real, se agrega como constante fija
en combat_service.py (siguiendo la misma disciplina que ya usan
buscar_puntero.py / verificar_puntero.py: escanear una vez, despues
solo verificar).
"""

import argparse
import struct

from app.readers.azahar_reader import AzaharReader
from app.services.combat_service import (
    COMBAT_INACTIVE_POINTER,
    COMBAT_POINTER_ADDRESS,
)


# Ventana de bytes a escanear a partir de base_address. 0x600 es un
# margen holgado; si la estructura real es mas chica no pasa nada,
# solo se leen bytes que no importan.
SCAN_WINDOW_SIZE = 0x600


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Busca offsets candidatos para species/slot dentro de "
            "la estructura de combate."
        )
    )

    parser.add_argument(
        "--species-id",
        type=int,
        required=True,
        help="speciesId (de /api/team) del Pokemon que mandaste a combate.",
    )

    parser.add_argument(
        "--slot",
        type=int,
        required=True,
        choices=range(1, 7),
        help="Numero de slot (1-6, de /api/team) del Pokemon que mandaste.",
    )

    args = parser.parse_args()

    print("================================")
    print("  BUSCAR OFFSET DE SLOT/SPECIES")
    print("      EN COMBATE (DexRelay)")
    print("================================")
    print()
    print(f"speciesId esperado: {args.species_id}")
    print(f"slot esperado:       {args.slot} (indice {args.slot - 1})")
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
            "No hay combate activo ahora mismo "
            f"(base_address={hex(base_address)}). "
            "Entra a combate y vuelve a correr el script."
        )
        return

    print(f"base_address = {hex(base_address)}")
    print(f"Escaneando {hex(SCAN_WINDOW_SIZE)} bytes...")
    print()

    data = memory.read(
        base_address,
        SCAN_WINDOW_SIZE,
    )

    if len(data) != SCAN_WINDOW_SIZE:
        print("Lectura de la ventana de escaneo incompleta/fallida.")
        return

    species_matches = []
    slot_matches = []

    expected_species_bytes = struct.pack(
        "<H",
        args.species_id,
    )

    expected_slot_value = args.slot - 1

    for offset in range(len(data) - 1):

        if data[offset:offset + 2] == expected_species_bytes:
            species_matches.append(hex(offset))

        if data[offset] == expected_slot_value:
            slot_matches.append(hex(offset))

    print(
        f"Offsets candidatos para speciesId ({args.species_id}) "
        f"como 2 bytes LE:"
    )
    print(
        "  " + (", ".join(species_matches) if species_matches else "(ninguno)")
    )
    print()

    print(
        f"Offsets candidatos para slot (byte == {expected_slot_value}):"
    )
    print(
        "  " + (", ".join(slot_matches) if slot_matches else "(ninguno)")
    )
    print()

    print(
        "Repite esto con otro Pokemon (distinta especie y/o slot) "
        "y compara: el offset real es el que se repite igual en "
        "todas las pruebas."
    )


if __name__ == "__main__":
    main()

"""
Imprime el puntero crudo del slot 1 de la party (un valor de 4
bytes, tipo dirección, ej. 0x08CF7420). Sirve como ancla ESTABLE
para calcular el puente de traducción entre las direcciones "del
juego" (las que usa DexRelay) y las direcciones que ve Cheat Engine
en el proceso de Windows.

Por qué este ancla y no LAST_CAUGHT_ADDRESS: la primera versión de
este probe usó datos de LAST_CAUGHT_ADDRESS, que es una zona que se
actualiza con el juego -- el valor pudo haber cambiado entre una
búsqueda y la siguiente, dando resultados inconsistentes. El
puntero de la party NO cambia mientras no reordenes el equipo, así
que es un ancla mucho más confiable para este tipo de búsqueda
puntual.

COMO USARLO:

    1. Corre este script (sin reordenar tu equipo mientras tanto).
       Copia el valor que imprime.
    2. En Cheat Engine: New Scan, Value Type "4 Bytes", Scan Type
       "Exact Value", pegá ese valor (en Hex, marcando la casilla
       "Hex"), First Scan.
    3. Es probable que salgan varios resultados. Para cada uno,
       clic derecho -> "Browse this memory region" -- el correcto
       es el que está en una región GRANDE (decenas/cientos de MB,
       "Read/Write") -- esa es la RAM completa del 3DS emulado, NO
       un pedacito chico de memoria de otra cosa.
    4. Pasame la dirección de Cheat Engine que esté en esa región
       grande.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import PARTY_ORDER_ADDRESS


def main():
    print("================================")
    print("   ANCLA PARA EL PUENTE DE CHEAT ENGINE")
    print("   (puntero de party, estable)")
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

    data = memory.read(PARTY_ORDER_ADDRESS, 4)

    if len(data) != 4:
        print("Lectura fallida.")
        return

    value = struct.unpack("<I", data)[0]

    print(
        f"Dirección del juego (tabla de party, slot 1): "
        f"{hex(PARTY_ORDER_ADDRESS)}"
    )
    print()
    print(f"VALOR A BUSCAR EN CHEAT ENGINE (Hex): {value:08X}")
    print()
    print(
        "En Cheat Engine: Value Type = '4 Bytes', marcá la "
        "casilla 'Hex', Scan Type = 'Exact Value', pegá ese "
        "valor, New Scan. Filtrá los resultados con 'Browse "
        "this memory region' -- el correcto está en una región "
        "grande (Read/Write, decenas o cientos de MB)."
    )


if __name__ == "__main__":
    main()

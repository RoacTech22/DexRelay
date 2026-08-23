"""
Observa el puntero de combate (COMBAT_POINTER_ADDRESS) en vivo.

Objetivo: confirmar si ese puntero vuelve a 0 cuando termina el
combate, o si se queda apuntando a la ultima estructura de batalla
usada (memoria "sucia" que el juego no limpia).

Uso:
    1. Corre este script.
    2. Entra a un combate en el juego, recibe dano, gana o huye.
    3. Sal del combate y espera unos segundos observando la salida.
    4. Repite el ciclo un par de veces (varios combates seguidos).

Cada linea impresa muestra:
    - base_address: el valor crudo del puntero en COMBAT_POINTER_ADDRESS
    - hp: el HP leido en base_address + COMBAT_HP_OFFSET (solo si
      base_address != 0)

Lo que buscamos ver:
    - Si base_address vuelve a 0x00000000 al salir de combate -> el
      sentinel actual (0 = sin combate) es correcto y el bug esta en
      otro lado.
    - Si base_address se queda con el mismo valor no-cero de antes,
      y el hp leido ahi tambien se congela -> confirmado: el puntero
      no se limpia solo, y CombatService.read() necesita otra forma
      de saber si el combate sigue activo (no solo "es distinto de 0").
"""

import struct
import time

from app.readers.azahar_reader import AzaharReader
from app.services.combat_service import (
    COMBAT_HP_OFFSET,
    COMBAT_POINTER_ADDRESS,
)


def main():
    print("================================")
    print("   OBSERVAR PUNTERO DE COMBATE")
    print("================================")
    print()
    print(f"COMBAT_POINTER_ADDRESS = {hex(COMBAT_POINTER_ADDRESS)}")
    print(f"COMBAT_HP_OFFSET       = {hex(COMBAT_HP_OFFSET)}")
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory
    last_base_address = None

    try:
        while True:
            pointer_bytes = memory.read(
                COMBAT_POINTER_ADDRESS,
                4,
            )

            if len(pointer_bytes) != 4:
                print("Lectura de puntero fallida (tamano incorrecto).")
                time.sleep(0.5)
                continue

            base_address = struct.unpack(
                "<I",
                pointer_bytes,
            )[0]

            hp_text = "-"

            if base_address != 0:
                hp_bytes = memory.read(
                    base_address + COMBAT_HP_OFFSET,
                    2,
                )

                if len(hp_bytes) == 2:
                    hp_text = str(
                        struct.unpack("<H", hp_bytes)[0]
                    )

            changed = base_address != last_base_address
            marker = " <-- CAMBIO" if changed else ""

            print(
                f"base_address={hex(base_address)}  hp={hp_text}{marker}"
            )

            last_base_address = base_address

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

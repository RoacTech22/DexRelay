"""
Verifica en vivo la dirección candidata para el contador de
"Pokémon capturados en total" (0x08C8729C), traducida desde el
puente de Cheat Engine calculado el 25/08/2026 usando el puntero de
party como ancla estable.

COMO USARLO:

    python -m tools.probes.memory.verificar_contador_capturas

Se queda leyendo el valor cada 1 segundo. Andá jugando normal:
    - Si caminás/peleás sin capturar nada: el valor NO debería
      cambiar.
    - Si capturás un Pokémon de verdad (equipo o caja): el valor
      debería subir en exactamente 1, justo en ese momento.

Presioná Ctrl+C para detener.
"""

import struct
import time

from app.readers.azahar_reader import AzaharReader


# Dirección candidata, traducida desde Cheat Engine (host
# 0x2E1579DC2DC, ancla party 0x08CF71F0 <-> host 0x2E157A4C230,
# offset 0x2E14ED55040).
CANDIDATE_ADDRESS = 0x08C8729C


def main():
    print("================================")
    print("   VERIFICAR CONTADOR DE CAPTURAS")
    print("================================")
    print()
    print(f"Dirección candidata: {hex(CANDIDATE_ADDRESS)}")
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
    last_value = None

    try:
        while True:

            data = memory.read(CANDIDATE_ADDRESS, 4)

            if len(data) != 4:
                print("Lectura fallida.")
                time.sleep(1)
                continue

            value = struct.unpack("<I", data)[0]

            changed = value != last_value
            marker = " <-- CAMBIÓ" if changed and last_value is not None else ""

            print(f"valor={value}{marker}")

            last_value = value

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

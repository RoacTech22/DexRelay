"""
Observa en vivo el candidato a "cantidad de Pokémon en la party"
para OMEGA RUBY (29/08/2026) -- PARTY_COUNT_ADDRESS confirmada
para Alpha Sapphire (0x08CF7208) no aplica acá, ya que
PARTY_ORDER_ADDRESS tampoco es la misma entre las dos versiones
(confirmado: da 0x0 en Omega Ruby).

Traducción de esta sesión (ancla: CAPTURE_BUFFER_ADDRESS, que SÍ
se confirmó compartida entre AS/OR):

    ancla del juego:        CAPTURE_BUFFER_ADDRESS (0x08804A94)
    ancla Cheat Engine:      0x15BECBE7AD4
    offset:                  0x15BE43E3040
    candidato Cheat Engine:  0x15BED0DE238
    candidato traducido:     0x08CFB1F8

Este script imprime el valor en esa dirección interpretado de 3
formas (1 byte, 2 bytes, 4 bytes) cada medio segundo. Lo que hay
que ver:

    - Con la party completa (6), el valor debería ser 6.
    - Al depositar un Pokémon en la Caja PC, el valor debería
      bajar a 5 en el mismo instante.
    - Al sacar otro, a 4. Y así.
    - Si el valor NO se mueve para nada, o se mueve con otra cosa
      (caminar, entrar a un menú), esta dirección no es la que
      buscamos.

USO:
    python -m tools.probes.party.observar_candidato_party_count_or

    Con el script corriendo: fijate el valor con la party llena,
    después andá depositando Pokémon uno por uno en la PC y mirá
    si el valor baja de a uno, en el momento exacto del depósito.
"""

import struct
import time

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader


# Traducida con el puente calculado en esta sesión -- NO
# reutilizar en otra sesión sin recalcular (el offset cambia cada
# vez que se reinicia el emulador, ver docstring arriba).
CANDIDATE_ADDRESS = 0x08CFB1F8


def main():
    print("================================")
    print("   OBSERVAR CANDIDATO A")
    print("   'CANTIDAD DE PARTY' (Omega Ruby)")
    print("================================")
    print()
    print(f"Dirección candidata: {hex(CANDIDATE_ADDRESS)}")
    print()

    process_name = Config().get(
        "azahar", "process_name", default="sango-2"
    )

    reader = AzaharReader(process_name=process_name)

    print(f"Buscando proceso {process_name!r}...")

    if not reader.connect():
        print(f"No se encontro {process_name!r}.")
        return

    print("Azahar conectado correctamente.")
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory
    last_line = None

    try:
        while True:

            data = memory.read(
                CANDIDATE_ADDRESS,
                4,
            )

            if len(data) != 4:
                print("Lectura fallida (tamano incorrecto).")
                time.sleep(0.5)
                continue

            as_byte = data[0]

            as_2bytes = struct.unpack(
                "<H",
                data[:2],
            )[0]

            as_4bytes = struct.unpack(
                "<I",
                data,
            )[0]

            line = (
                f"1 byte={as_byte}   "
                f"2 bytes={as_2bytes}   "
                f"4 bytes={as_4bytes}   "
                f"(crudo: {data.hex()})"
            )

            marker = (
                " <-- CAMBIO"
                if line != last_line
                else ""
            )

            print(f"{line}{marker}")

            last_line = line

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

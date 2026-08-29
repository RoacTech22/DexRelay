"""
Ancla para el puente Cheat Engine↔juego, específica para Omega
Ruby (29/08/2026). El probe original (imprimir_ancla_puente.py)
usa PARTY_ORDER_ADDRESS como valor de referencia -- pero en Omega
Ruby esa dirección da 0x0 (confirmado, ver investigación de esta
sesión), así que no sirve como ancla ahí.

Un primer intento usó el Bloque 2 encontrado por
buscar_party_omega_ruby.py (0x08CFB26C) -- resultó ser una zona
de memoria temporal/reciclable que el juego reutiliza para otra
cosa (confirmado: en una segunda lectura ya estaba en 0x0). Esta
versión usa en cambio CAPTURE_BUFFER_ADDRESS (0x08804A94) --
¡la MISMA dirección ya confirmada y documentada de Alpha Sapphire!
Confirmado con un escaneo completo que en Omega Ruby esa dirección
exacta contiene el equipo real del usuario (Zen/Len/Yuuki/Jhosy/
Eva/Daron, stride 0x1E4 -- idéntico al de AS), y que
LAST_CAUGHT_ADDRESS (0x08805638) también coincide exacto. Esta
zona parece ser compartida entre las dos versiones, a diferencia
de PARTY_ORDER_ADDRESS.

COMO USARLO: igual que el probe original.

    1. Corré este script. Copiá el valor que imprime.
    2. En Cheat Engine: New Scan, Value Type "4 Bytes", Scan Type
       "Exact Value", pegá ese valor (en Hex, marcando la casilla
       "Hex"), First Scan.
    3. Es probable que salgan varios resultados. Para cada uno,
       clic derecho -> "Browse this memory region" -- el correcto
       es el que está en una región GRANDE (decenas/cientos de MB,
       "Read/Write").
    4. Pasame la dirección de Cheat Engine que esté en esa región
       grande -- con eso calculamos el offset del puente para
       traducir el candidato de "cantidad de party" que
       encuentres.
"""

import struct

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import CAPTURE_BUFFER_ADDRESS


# CAPTURE_BUFFER_ADDRESS -- ya confirmada y documentada para
# Alpha Sapphire, y confirmada TAMBIÉN válida en Omega Ruby con
# un escaneo completo (29/08/2026): contiene el equipo real del
# usuario en la misma dirección exacta. Mucho más confiable que
# cualquier dirección recién encontrada por escaneo, que puede
# resultar ser una zona temporal (como pasó con el primer intento
# de este mismo probe).
ANCHOR_ADDRESS = CAPTURE_BUFFER_ADDRESS


def main():
    print("================================")
    print("   ANCLA PARA EL PUENTE DE CHEAT ENGINE")
    print("   (Omega Ruby -- bloque de party encontrado)")
    print("================================")
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
    print()

    memory = reader.memory

    data = memory.read(ANCHOR_ADDRESS, 4)

    if len(data) != 4:
        print("Lectura fallida.")
        return

    value = struct.unpack("<I", data)[0]

    print(
        f"Dirección del juego (CAPTURE_BUFFER_ADDRESS): "
        f"{hex(ANCHOR_ADDRESS)}"
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

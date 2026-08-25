"""
Busca la Caja PC en memoria escaneando por checksum valido, no por
un offset adivinado.

Por que este enfoque: a diferencia de investigaciones anteriores
(el slot de combate, la zona actual), acá SI tenemos una señal
fuerte y confiable para reconocer un Pokemon real en memoria -- el
checksum de 16 bits que ya usamos en structures.py para descartar
lecturas corruptas de la party. La probabilidad de que un choque de
bytes random pase ese checksum por casualidad es de 1 en 65536, asi
que un "hit" del checksum es una señal mucho mas confiable que
cualquier cosa que buscamos en investigaciones pasadas.

Estrategia:
    1. Leer una ventana grande de memoria de una sola vez (rapido,
       una sola llamada de red).
    2. Para cada offset alineado a 4 bytes DENTRO de esa ventana
       (ya en memoria local, sin mas llamadas de red), probar si
       ahi hay una estructura PK6 valida: decrypt_data() +
       checksum. Esto es trabajo de CPU local, no de red, asi que
       se puede probar en cientos de miles de offsets rapido.
    3. Reportar donde aparecieron structuras validas, agrupadas,
       para inferir el "stride" (separacion entre slots) real de
       la Caja PC.

COMO USARLO:

    1. Antes de correr esto, mete un Pokemon a la Caja PC a
       proposito (llena la party a 6/6 y atrapa uno mas, o
       simplemente deposita uno a mano desde el PC) para tener algo
       fresco y facil de reconocer en el escaneo.
    2. Anota el nickname/especie de ese Pokemon para poder
       reconocerlo en la salida.
    3. Corre:

           python -m tools.probes.party.buscar_caja_pc

    (Tarda un rato: el escaneo de CPU sobre una ventana de varios
    MB puede llevar uno o dos minutos, es normal.)
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import PARTY_ORDER_ADDRESS, SLOT_DATA_SIZE
from app.memory.structures import Pokemon6, decrypt_data


# Ventana de memoria a escanear, centrada en PARTY_ORDER_ADDRESS --
# la Caja PC suele vivir cerca de la party dentro del mismo bloque
# de datos de guardado. 4MB a cada lado (8MB total) alcanza para
# cubrir una caja completa de Gen 6 (30 cajas x 30 slots) si esta
# ahi cerca; si no aparece nada, hay que probar mas lejos.
WINDOW_BEFORE = 0x400000
WINDOW_AFTER = 0x400000

# Alineacion de bytes a probar. 4 es lo minimo razonable (las
# estructuras del juego casi siempre estan alineadas a 4 bytes).
ALIGNMENT = 4


def main():
    print("================================")
    print("   BUSCAR CAJA PC (por checksum)")
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

    scan_start = PARTY_ORDER_ADDRESS - WINDOW_BEFORE
    scan_size = WINDOW_BEFORE + WINDOW_AFTER

    print(
        f"Ventana de escaneo: {hex(scan_start)} - "
        f"{hex(scan_start + scan_size)} "
        f"({scan_size / 1024 / 1024:.1f} MB)"
    )
    print("Leyendo memoria (puede tardar un rato)...")

    data = memory.read(scan_start, scan_size)

    if len(data) != scan_size:
        print(
            "Lectura incompleta/fallida "
            f"({len(data)} de {scan_size} bytes)."
        )
        return

    print("Memoria leida. Escaneando por checksums validos...")
    print(
        "(esto es calculo local, no mas llamadas de red -- "
        "puede tardar uno o dos minutos)"
    )
    print()

    matches = []

    last_report = 0

    for offset in range(
        0,
        scan_size - SLOT_DATA_SIZE + 1,
        ALIGNMENT,
    ):

        # Progreso cada ~10%
        progress = offset / scan_size
        if progress - last_report >= 0.1:
            print(f"  ... {progress * 100:.0f}%")
            last_report = progress

        chunk = data[offset:offset + SLOT_DATA_SIZE]

        # Filtro barato antes de gastar CPU en decrypt_data():
        # una estructura vacia (todo ceros) no sirve, y ya sabemos
        # que decrypt_data la descarta igual, pero chequearlo antes
        # es mucho mas rapido que llamar la funcion.
        if chunk[:8] == b"\x00" * 8:
            continue

        decrypted = decrypt_data(chunk)

        if not decrypted:
            continue

        pokemon = Pokemon6.__new__(Pokemon6)
        pokemon.raw_data = decrypted

        species_id = pokemon.species_id()

        # Rango razonable de especies validas (Gen 1-6 en ORAS).
        if species_id < 1 or species_id > 721:
            continue

        nickname = pokemon.nickname()

        absolute_address = scan_start + offset

        matches.append(
            (absolute_address, species_id, nickname)
        )

    print()
    print(f"Encontrados {len(matches)} candidatos con checksum valido.")
    print()

    if not matches:
        print(
            "Nada en esta ventana. Puede que la Caja PC este mas "
            "lejos de PARTY_ORDER_ADDRESS de lo esperado -- "
            "probemos ampliar la ventana o buscar en otra zona."
        )
        return

    print("Primeros 40 candidatos (dirección, especie, nickname):")

    for address, species_id, nickname in matches[:40]:
        print(
            f"  {hex(address)}  speciesId={species_id}  "
            f"nickname={nickname!r}"
        )

    if len(matches) > 40:
        print(f"  ... y {len(matches) - 40} más")

    print()

    # Si hay varios candidatos consecutivos con una separacion
    # constante, esa separacion es probablemente el tamaño real de
    # cada slot de la Caja PC.
    if len(matches) >= 2:

        gaps = {}

        for i in range(1, len(matches)):
            gap = matches[i][0] - matches[i - 1][0]
            gaps[gap] = gaps.get(gap, 0) + 1

        most_common_gap = max(
            gaps.items(),
            key=lambda item: item[1],
        )

        print(
            f"Separación más común entre candidatos: "
            f"{hex(most_common_gap[0])} bytes "
            f"({most_common_gap[1]} veces) -- probablemente el "
            f"tamaño real de cada slot de la Caja PC."
        )


if __name__ == "__main__":
    main()

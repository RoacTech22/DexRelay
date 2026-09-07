"""
Confirma y mapea la estructura real de la bolsa de items, a partir
de los candidatos fuertes que encontro buscar_bolsa_items.py:

    Alpha Sapphire: 0x08C6AC86 : 17 -> 16  (Ultra Ball, 23 -> 22)
    Omega Ruby:     0x08C6EC72 : 04 -> 03  (Poke Ball, 4 -> 3)

Interpretados como PAR de 2 bytes (item_id, cantidad) de 4 bytes por
casillero, los dos candidatos calzaron perfecto: item_id se mantuvo
igual y la cantidad bajo en 1, justo lo que se hizo en el juego en
cada version. Los demas candidatos de esas corridas (bloques grandes
de bytes cambiando juntos de forma erratica, sueltos cerca de
CURRENT_ZONE_ID_ADDRESS/su espejo) se descartaron como ruido -- mismo
patron en las dos versiones.

Multi-version (07/09/2026, mismo patron ya visto con
PARTY_ORDER_ADDRESS/BOX_BASE_ADDRESS/CURRENT_ZONE_ID_ADDRESS): la
direccion del candidato NO coincide entre Alpha Sapphire y Omega
Ruby -- calculada la diferencia contra BADGES_ADDRESS (confirmada
compartida entre versiones), el candidato de AS cae ANTES de badges
(-0x3150) y el de OR cae DESPUES (+0x0E9C) -- no es ni siquiera el
mismo lado. Este script elige el candidato segun la version que
detecte al conectar.

Esto NO prueba todavia que el formato sea el correcto ni encuentra
los limites del bolsillo (donde empieza/termina la lista) -- eso es
lo que hace este script, con dos pasos:

    1. DUMP MANUAL: imprime los casilleros de 4 bytes alrededor de
       0x08C6AC84 (bastante margen para los dos lados) ya decodificados
       como (item_id, cantidad), para inspeccionar a ojo si tiene
       pinta de bolsillo real (varios item_id validos seguidos,
       cantidades razonables, algun casillero vacio (0,0) marcando
       el final).

    2. AUTO-DETECCION DE BOLSILLOS: escanea una ventana mas grande
       alrededor del candidato buscando TRAMOS LARGOS y seguidos de
       casilleros con "forma valida" (item_id 1-999 y cantidad
       1-999, o (0,0) para casillero vacio) -- un bolsillo real de
       ORAS tiene varias decenas de casilleros, asi que un tramo
       largo de datos con esa forma es mucha mas señal que un
       candidato aislado.

COMO USARLO:

    python -m tools.probes.memory.confirmar_bolsa_items

No hace falta reproducir ningun cambio en el juego -- esto es pura
lectura e interpretacion de lo que ya haya en memoria en este
momento. Anota que items REALES tenes en la bolsa (nombre, orden,
cantidad) antes de correrlo, para poder comparar contra lo que
imprime.

IMPORTANTE: solo lectura, no escribe nada en el juego.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


# Candidatos confirmados por buscar_bolsa_items.py -- el casillero
# (item_id, cantidad) empieza 2 bytes antes del byte que cambio en
# cada corrida. Multi-version (07/09/2026, mismo patron ya visto con
# PARTY_ORDER_ADDRESS/BOX_BASE_ADDRESS/CURRENT_ZONE_ID_ADDRESS): la
# direccion NO coincide entre Alpha Sapphire y Omega Ruby, asi que
# no se puede usar una sola constante -- se elige segun la version
# detectada al conectar (reader.process_name).
_CANDIDATE_SLOT_ADDRESS_BY_PROCESS = {
    # Alpha Sapphire: Ultra Ball (item_id=2), 23 -> 22 confirmado en vivo.
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6AC86 - 2,
    # Omega Ruby: Poke Ball (item_id=4), 4 -> 3 confirmado en vivo.
    PROCESS_NAME_OMEGA_RUBY: 0x08C6EC72 - 2,
}

SLOT_SIZE = 4

# Cuantos casilleros mostrar antes/despues del candidato en el
# dump manual.
DUMP_SLOTS_BEFORE = 20
DUMP_SLOTS_AFTER = 20

# Ventana mas grande para la auto-deteccion de tramos largos.
SCAN_WINDOW_BEFORE = 0x4000
SCAN_WINDOW_AFTER = 0x4000

# "Forma valida" de un casillero: o esta vacio (0, 0), o tiene un
# item_id y una cantidad dentro de rangos razonables del juego
# (cantidad maxima real de un stack en ORAS es 999; el item_id mas
# alto conocido en esta generacion ronda ~900, se deja margen).
MAX_PLAUSIBLE_ITEM_ID = 999
MAX_PLAUSIBLE_QUANTITY = 999

# Tramos de al menos esta cantidad de casilleros seguidos con forma
# valida se reportan como posible bolsillo -- un bolsillo real tiene
# varias decenas de casilleros, un tramo corto es mas probable que
# sea casualidad.
MIN_RUN_LENGTH = 10


def decode_slot(data, offset):
    item_id, quantity = struct.unpack(
        "<HH", data[offset:offset + SLOT_SIZE]
    )
    return item_id, quantity


def slot_is_plausible(item_id, quantity):
    if item_id == 0 and quantity == 0:
        return True

    return (
        1 <= item_id <= MAX_PLAUSIBLE_ITEM_ID
        and 1 <= quantity <= MAX_PLAUSIBLE_QUANTITY
    )


def dump_manual(memory, candidate_address):
    start = candidate_address - DUMP_SLOTS_BEFORE * SLOT_SIZE
    size = (DUMP_SLOTS_BEFORE + 1 + DUMP_SLOTS_AFTER) * SLOT_SIZE

    data = memory.read(start, size)

    if data is None or len(data) != size:
        print("No se pudo leer la zona del candidato.")
        return

    print("================================")
    print("   DUMP MANUAL ALREDEDOR DEL CANDIDATO")
    print("================================")
    print()

    for index in range(0, size, SLOT_SIZE):
        address = start + index
        item_id, quantity = decode_slot(data, index)

        marker = " <-- CANDIDATO" if address == candidate_address else ""
        plausible = "OK" if slot_is_plausible(item_id, quantity) else "??"

        print(
            f"0x{address:08X}  item_id={item_id:>4}  "
            f"cantidad={quantity:>4}  [{plausible}]{marker}"
        )

    print()


def find_runs(data, window_start):
    """
    Recorre `data` de a 4 bytes y devuelve la lista de tramos
    (start_address, slot_count) donde TODOS los casilleros tienen
    forma valida (ver slot_is_plausible), de largo >= MIN_RUN_LENGTH.
    """

    runs = []
    slot_count = len(data) // SLOT_SIZE

    current_run_start = None
    current_run_length = 0

    for slot_index in range(slot_count):
        offset = slot_index * SLOT_SIZE
        item_id, quantity = decode_slot(data, offset)

        if slot_is_plausible(item_id, quantity):
            if current_run_start is None:
                current_run_start = slot_index
            current_run_length += 1
        else:
            if current_run_length >= MIN_RUN_LENGTH:
                runs.append((current_run_start, current_run_length))
            current_run_start = None
            current_run_length = 0

    if current_run_length >= MIN_RUN_LENGTH:
        runs.append((current_run_start, current_run_length))

    return [
        (window_start + start * SLOT_SIZE, length)
        for start, length in runs
    ]


def auto_detect_pockets(memory, candidate_address):
    scan_start = candidate_address - SCAN_WINDOW_BEFORE
    scan_size = SCAN_WINDOW_BEFORE + SCAN_WINDOW_AFTER

    data = memory.read(scan_start, scan_size)

    if data is None or len(data) != scan_size:
        print("No se pudo leer la ventana de auto-deteccion.")
        return

    print("================================")
    print("   AUTO-DETECCION DE BOLSILLOS")
    print("================================")
    print()
    print(
        f"Ventana escaneada: 0x{scan_start:08X} - "
        f"0x{scan_start + scan_size:08X} ({scan_size} bytes)"
    )
    print(
        f"Buscando tramos de {MIN_RUN_LENGTH}+ casilleros seguidos "
        f"con forma valida..."
    )
    print()

    runs = find_runs(data, scan_start)

    if not runs:
        print(
            "No aparecio ningun tramo largo. Puede que el candidato "
            "sea ruido despues de todo, o que la ventana no alcance "
            "-- probar ampliando SCAN_WINDOW_BEFORE/AFTER."
        )
        return

    for run_start, length in runs:
        run_end = run_start + length * SLOT_SIZE
        contains_candidate = (
            run_start <= candidate_address < run_end
        )

        marker = (
            "  <-- INCLUYE EL CANDIDATO CONFIRMADO"
            if contains_candidate
            else ""
        )

        print(
            f"Tramo: 0x{run_start:08X} - 0x{run_end:08X} "
            f"({length} casilleros){marker}"
        )

    print()
    print(
        "Si un tramo incluye el candidato confirmado y tiene pinta "
        "de bolsillo real (varias decenas de casilleros), ese es el "
        "bolsillo -- anota su direccion de inicio y cuantos "
        "casilleros tiene. Los demas tramos (si hay) pueden ser "
        "otros bolsillos (Objetos/MTs/Bayas van en arrays separados) "
        "o coincidencias -- hay que confirmarlos comparando contra "
        "lo que se ve realmente en la bolsa del juego."
    )


def main():
    print("================================")
    print(" DEXRELAY CONFIRMAR BOLSA DE ITEMS")
    print("================================")
    print()

    # Ver buscar_bolsa_items.py: process_name=None es el modo
    # automatico real (detecta AS u OR); AzaharReader() sin
    # argumentos queda fijo en "sango-2" (Alpha Sapphire).
    reader = AzaharReader(process_name=None)

    print("Buscando proceso (sango-1 / sango-2)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    print(f"Azahar conectado correctamente. Proceso: {reader.process_name}")
    print()

    candidate_address = _CANDIDATE_SLOT_ADDRESS_BY_PROCESS.get(
        reader.process_name
    )

    if candidate_address is None:
        print(
            f"No hay un candidato confirmado todavia para "
            f"'{reader.process_name}' -- correr primero "
            f"buscar_bolsa_items.py contra esta version."
        )
        return

    print(f"Candidato a usar: 0x{candidate_address:08X}")
    print()

    memory = reader.memory

    dump_manual(memory, candidate_address)
    auto_detect_pockets(memory, candidate_address)


if __name__ == "__main__":
    main()

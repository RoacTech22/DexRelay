"""
Investigación de compatibilidad Alpha Sapphire 1.4 (pendiente
heredado desde el Documento Maestro del 04/09/2026, nota completa
junto a PROCESS_NAME_ALPHA_SAPPHIRE en pointers.py).

CONTEXTO: las direcciones actuales de AS en pointers.py están
confirmadas contra el juego BASE (sin el parche 1.4). Con el 1.4
puesto, el mapa de memoria queda corrido -- mismo síntoma ya visto
con Omega Ruby cuando le faltó el parche (equipo/caja vacíos, sin
ningún error visible).

HALLAZGO REAL (09/09/2026) que ahorra la mayor parte del trabajo:
las direcciones ya confirmadas de AS-base y OR-1.4 (dos juegos, dos
versiones de parche DISTINTAS) mantienen exactamente la MISMA
distancia relativa entre sí para las 4 estructuras clave:

    PARTY_COUNT_ADDRESS         = PARTY_ORDER_ADDRESS + 0x18
    BOX_BASE_ADDRESS             = PARTY_ORDER_ADDRESS - 0x5D0AC
    CURRENT_ZONE_ID_ADDRESS      = PARTY_ORDER_ADDRESS - 0x8CA3E
    CURRENT_ZONE_ID_MIRROR_ADDR  = PARTY_ORDER_ADDRESS - 0x8C95C

(la primera ya estaba documentada en pointers.py como "misma
relación confirmada para las dos versiones"; las otras tres se
verificaron recién ahora, restando los pares AS-base/OR-1.4 ya
conocidos -- dan exactamente igual en los dos casos.)

Que esto se sostenga entre DOS JUEGOS DISTINTOS es una señal fuerte
de que es una propiedad fija del layout de memoria del motor/
Azahar, no algo específico de cada ROM -- así que lo más probable
es que también se sostenga para AS 1.4. No es una garantía (nunca
se probó con un cambio de VERSIÓN DE PARCHE del mismo juego, solo
entre juegos distintos), por eso este script no asume nada: deriva
las 4 direcciones a partir de UNA sola que vos encontrás con Cheat
Engine, y las valida todas en vivo antes de confiar en ninguna.

QUÉ TENÉS QUE HACER VOS EN CHEAT ENGINE (una sola dirección, la más
fácil de las 4 de encontrar):

    PARTY_COUNT_ADDRESS -- 1 byte, valor = cantidad real de
    Pokémon en el equipo (1-6). Mismo método ya usado el
    29/08/2026 para encontrarla en AS-base y OR:

    1. Cheat Engine -> abrir el proceso de Azahar.
    2. Value Type: "1 Byte". Scan Type: "Exact Value".
       Primer valor: la cantidad de Pokémon que tenés en el
       equipo AHORA (ej. si tenés 4, escaneá "4").
    3. Andá al juego, depositá o sacá un Pokémon en un PC para
       que la cantidad cambie a otro número.
    4. Volvé a Cheat Engine, "Next Scan" con el nuevo valor
       exacto (ej. si ahora tenés 3, escaneá "3").
    5. Repetí el paso 3-4 una vez más para terminar de descartar
       falsos positivos (debería quedar 1 o muy pocos resultados).
    6. Anotá la dirección -- ESA es tu PARTY_COUNT_ADDRESS
       candidata.

CÓMO USAR ESTE SCRIPT una vez que tenés esa dirección (con Azahar
corriendo, AS 1.4 cargado, sin hace falta nada más de Cheat
Engine):

    python -m tools.probes.memory.investigar_alpha_sapphire_1_4 0x08XXXXXX

Reporta, para cada una de las 4 direcciones derivadas, si la
lectura en vivo tiene pinta de ser correcta (equipo real
decodificado con checksum válido, caja con Pokémon reales o vacíos
limpios, zona actual con un ID que tenga sentido) -- y al final un
bloque listo para copiar directo a pointers.py si todo cierra.
"""

import sys

from app.memory.pointers import (
    ORDER_ENTRY_SIZE,
    PROCESS_NAME_ALPHA_SAPPHIRE,
)
from app.readers.azahar_reader import AzaharReader, READ_FAILED
from app.memory.structures import Pokemon6

# Offsets relativos confirmados estables entre AS-base y OR-1.4
# (ver docstring del módulo). Todos restan o suman sobre
# PARTY_ORDER_ADDRESS.
OFFSET_COUNT_DESDE_ORDER = 0x18
OFFSET_BOX_DESDE_ORDER = -0x5D0AC
OFFSET_ZONE_DESDE_ORDER = -0x8CA3E
OFFSET_ZONE_MIRROR_DESDE_ORDER = -0x8C95C

POKEMON_POINTER_OFFSET = 0x40
BOX_SLOT_STRIDE = 232  # SLOT_DATA_SIZE + STAT_DATA_SIZE, ver pointers.py


def parse_address(raw):
    return int(raw, 16)


def validate_party(reader, order_address, count_address):

    print(f"\n--- PARTY_ORDER_ADDRESS candidata: {hex(order_address)} ---")
    print(f"--- PARTY_COUNT_ADDRESS candidata: {hex(count_address)} ---")

    count_byte = reader.memory.read(count_address, 1)

    if count_byte is None or len(count_byte) != 1:
        print("  Lectura de PARTY_COUNT falló -- dirección probablemente mal.")
        return False

    count = count_byte[0]
    print(f"  Cantidad reportada: {count} (¿coincide con tu equipo real?)")

    if not (1 <= count <= 6):
        print("  Valor fuera de rango (1-6) -- dirección probablemente mal.")
        return False

    order_data = reader.memory.read(order_address, ORDER_ENTRY_SIZE * 6)

    if order_data is None or len(order_data) != ORDER_ENTRY_SIZE * 6:
        print("  Lectura de PARTY_ORDER falló -- dirección probablemente mal.")
        return False

    ok_count = 0

    for slot in range(6):
        pointer = int.from_bytes(
            order_data[slot * ORDER_ENTRY_SIZE:(slot + 1) * ORDER_ENTRY_SIZE],
            byteorder="little",
        )

        if slot >= count or pointer == 0:
            print(f"  Slot {slot + 1}: vacío (esperado)")
            continue

        pokemon = reader._read_pokemon_at_address(
            pointer + POKEMON_POINTER_OFFSET
        )

        if pokemon is READ_FAILED:
            print(f"  Slot {slot + 1}: FALLÓ el descifrado (checksum inválido)")
            ok_count -= 1
        else:
            print(
                f"  Slot {slot + 1}: species_id={pokemon.species_id()} "
                f"nivel={pokemon.level()} nickname={pokemon.nickname()!r} "
                f"(¿coincide con tu equipo real?)"
            )
            ok_count += 1

    return ok_count == count


def validate_box(reader, box_base_address):

    print(f"\n--- BOX_BASE_ADDRESS candidata: {hex(box_base_address)} ---")

    decoded = 0
    empty = 0
    failed = 0

    for slot in range(30):
        address = box_base_address + slot * BOX_SLOT_STRIDE
        data = reader.memory.read(address, BOX_SLOT_STRIDE)

        if not data or len(data) != BOX_SLOT_STRIDE:
            failed += 1
            continue

        pokemon = Pokemon6(data)

        if pokemon.species_id() == 0:
            empty += 1
        else:
            decoded += 1

    print(
        f"  Caja 1: {decoded} decodificados, {empty} vacíos, "
        f"{failed} con lectura fallida (¿el total te cierra con "
        f"lo que tenés guardado ahí de verdad?)"
    )

    return failed == 0


def validate_zone(reader, zone_address, mirror_address):

    print(f"\n--- CURRENT_ZONE_ID_ADDRESS candidata: {hex(zone_address)} ---")
    print(f"--- CURRENT_ZONE_ID_MIRROR candidata: {hex(mirror_address)} ---")

    zone_byte = reader.memory.read(zone_address, 1)
    mirror_byte = reader.memory.read(mirror_address, 1)

    if not zone_byte or not mirror_byte:
        print("  Lectura falló en alguna de las dos -- probablemente mal.")
        return False

    print(f"  Zona actual: {zone_byte[0]}  |  Espejo: {mirror_byte[0]}")

    if zone_byte[0] != mirror_byte[0]:
        print(
            "  Los dos valores NO coinciden -- podría ser normal (no "
            "confirmado que deban ser siempre iguales) o podría ser "
            "señal de que el offset del espejo está mal. Moverte de "
            "zona en el juego y volver a correr esto para comparar."
        )

    return True


def main():

    if len(sys.argv) != 2:
        print(
            "Uso: python -m tools.probes.memory.investigar_alpha_sapphire_1_4 "
            "0xDIRECCION_PARTY_COUNT_ENCONTRADA_CON_CHEAT_ENGINE"
        )
        return

    count_address = parse_address(sys.argv[1])
    order_address = count_address - OFFSET_COUNT_DESDE_ORDER
    box_address = order_address + OFFSET_BOX_DESDE_ORDER
    zone_address = order_address + OFFSET_ZONE_DESDE_ORDER
    zone_mirror_address = order_address + OFFSET_ZONE_MIRROR_DESDE_ORDER

    reader = AzaharReader(process_name=PROCESS_NAME_ALPHA_SAPPHIRE)

    if not reader.connect():
        print(
            "No se pudo conectar a Azahar -- ¿está corriendo con AS 1.4 "
            "cargado?"
        )
        return

    party_ok = validate_party(reader, order_address, count_address)
    box_ok = validate_box(reader, box_address)
    zone_ok = validate_zone(reader, zone_address, zone_mirror_address)

    print("\n=== RESUMEN ===")
    print(f"Party:  {'OK' if party_ok else 'REVISAR'}")
    print(f"Caja:   {'OK' if box_ok else 'REVISAR'}")
    print(f"Zona:   {'OK' if zone_ok else 'REVISAR'}")

    if party_ok and box_ok and zone_ok:
        print(
            "\nTodo cerró. Bloque listo para pointers.py (agregar "
            "PROCESS_NAME_ALPHA_SAPPHIRE_1_4 o reemplazar el valor "
            "actual, según decidamos si soportar las dos versiones "
            "de AS a la vez o migrar del todo a 1.4):\n"
        )
        print(f"  PARTY_ORDER_ADDRESS  = {hex(order_address)}")
        print(f"  PARTY_COUNT_ADDRESS  = {hex(count_address)}")
        print(f"  BOX_BASE_ADDRESS     = {hex(box_address)}")
        print(f"  CURRENT_ZONE_ID_ADDRESS        = {hex(zone_address)}")
        print(f"  CURRENT_ZONE_ID_MIRROR_ADDRESS = {hex(zone_mirror_address)}")
    else:
        print(
            "\nAlgo no cerró -- antes de descartar la hipótesis del "
            "offset fijo, revisá que PARTY_COUNT_ADDRESS sea la "
            "correcta (repetir el narrowing en Cheat Engine con más "
            "pasos de Next Scan). Si con una PARTY_COUNT_ADDRESS bien "
            "confirmada esto sigue sin cerrar, hay que escanear las "
            "otras 3 desde cero con Cheat Engine, cada una con su "
            "propia técnica (ver Documento Maestro 08-25 sección de "
            "TOTAL_CAUGHT_ADDRESS para el estilo de scan por cambio "
            "de valor)."
        )


if __name__ == "__main__":
    main()

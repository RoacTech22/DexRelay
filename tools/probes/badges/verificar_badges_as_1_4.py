"""
Bug real (10/09/2026, reportado por el usuario: "las medallas
muestran 0 aunque tengo varias", y por separado "el Nuzlocke marca
perdido aunque atrapé, y se duplica al asignar ruta"). Las dos
resultaron ser el MISMO tipo de problema: direcciones fijas que se
confirmaron hace tiempo contra Alpha Sapphire BASE y quedaron
afuera de la migración a la actualización 1.4 de la sesión
anterior -- a diferencia de PARTY_ORDER_ADDRESS/BOX_BASE_ADDRESS/
CURRENT_ZONE_ID_ADDRESS/BAG_START_ADDRESS (todas migradas), estas
dos viven sueltas (BADGES_ADDRESS en badges_service.py,
TOTAL_CAUGHT_ADDRESS en pointers.py pero como constante simple, no
en el diccionario _BY_PROCESS) -- fáciles de pasar por alto en un
refactor grande.

Diagnosticado el bug del duplicado con
tools/probes/combat/diagnostico_timing_captura.py: total_caught
daba 0 TODO el tiempo, incluso durante una captura real -- si nunca
sube, la comparación "¿subió el contador?" que usa
_update_lost_encounter_tracking() (runtime.py) para decidir
"perdido" siempre da que no subió, sin importar si hubo captura de
verdad.

CANDIDATOS (no confirmados todavía, por eso este probe): la
distancia AS-base -> AS-1.4 ya confirmada para PARTY_ORDER_ADDRESS
(y ahora también para BADGES_ADDRESS) es exactamente 0x3FF0.
Aplicando ese mismo delta:

    BADGES:       0x08C6DDD4 + 0x3FF0 = 0x08C71DC4  (BADGES ya
                  CONFIRMADO con este mismo método, 1 medalla real)
    TOTAL_CAUGHT: 0x08C8729C + 0x3FF0 = 0x08C8B28C  (sin confirmar
                  todavía)

Este probe lee las direcciones viejas y candidatas en vivo, lado a
lado -- SOLO LECTURA, no escribe nada.

USO (con Azahar corriendo, Alpha Sapphire 1.4 cargado):

    python -m tools.probes.badges.verificar_badges_as_1_4
"""

import struct

from app.readers.azahar_reader import AzaharReader

OLD_BADGES_ADDRESS = 0x08C6DDD4
CANDIDATE_BADGES_ADDRESS = 0x08C71DC4

OLD_TOTAL_CAUGHT_ADDRESS = 0x08C8729C
CANDIDATE_TOTAL_CAUGHT_ADDRESS = 0x08C8B28C


def describe_counter(label, address, reader):

    print(f"--- {label}: {hex(address)} ---")

    data = reader.memory.read(address, 4)

    if data is None or len(data) != 4:
        print("  Lectura fallida.")
        return

    value = struct.unpack("<I", data)[0]

    print(f"  Valor: {value}")
    print()


def describe(label, address, reader):

    print(f"--- {label}: {hex(address)} ---")

    data = reader.memory.read(address, 1)

    if data is None or len(data) != 1:
        print("  Lectura fallida.")
        return

    value = data[0]
    badges = [bool(value & (1 << bit)) for bit in range(8)]
    count = sum(badges)

    print(f"  Byte: 0x{value:02X}  ({value:08b})")
    print(f"  Medallas activas: {count}/8")
    print(
        "  Bits ON: "
        + (", ".join(str(i) for i, b in enumerate(badges) if b) or "ninguno")
    )
    print()


def main():
    print("================================")
    print("   VERIFICAR BADGES_ADDRESS -- AS 1.4")
    print("================================")
    print()

    # Autodetección (no un process_name fijo -- ya pasó antes que
    # forzar "sango-2" a mano falle según cómo esté detectando
    # Azahar el proceso en el momento; None deja que AzaharReader
    # resuelva el proceso activo solo).
    reader = AzaharReader(process_name=None)

    if not reader.connect():
        print("No se pudo conectar a Azahar.")
        return

    print(f"Conectado -- proceso detectado: {reader.process_name}")
    print()

    describe("BADGES -- VIEJA (AS-base)", OLD_BADGES_ADDRESS, reader)
    describe("BADGES -- CANDIDATA (AS-1.4)", CANDIDATE_BADGES_ADDRESS, reader)

    describe_counter(
        "TOTAL_CAUGHT -- VIEJA (AS-base)",
        OLD_TOTAL_CAUGHT_ADDRESS,
        reader,
    )
    describe_counter(
        "TOTAL_CAUGHT -- CANDIDATA (AS-1.4)",
        CANDIDATE_TOTAL_CAUGHT_ADDRESS,
        reader,
    )

    print(
        "Comparar contra lo que sabés real: medallas obtenidas, y "
        "cuántos Pokémon capturaste en total en esta partida (roster "
        "+ cementerio + los que soltaste/intercambiaste, si alguno). "
        "Avisame el resultado antes de que actualice el código."
    )


if __name__ == "__main__":
    main()

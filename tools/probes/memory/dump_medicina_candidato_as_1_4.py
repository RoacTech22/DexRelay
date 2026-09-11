"""
Bug reportado (09/09/2026): Caramelo Raro dejó de funcionar en
Alpha Sapphire después de migrar a la actualización 1.4. Hipótesis:
mismo fenómeno que ya se confirmó con PARTY_ORDER_ADDRESS/
BOX_BASE_ADDRESS/CURRENT_ZONE_ID_ADDRESS -- el parche 1.4 convergió
el mapa de memoria de AS con el de Omega Ruby, así que
MEDICINE_POCKET_START_ADDRESS (y probablemente BAG_START/END)
también deberían haberse movido a la dirección que ya usa OR, no
seguir en la vieja de AS-base (0x08C6B5F0).

Esto es SOLO LECTURA -- no escribe nada, no arriesga tu save. Dump
alrededor del candidato (la dirección de Medicina ya confirmada
para Omega Ruby) para confirmar a ojo si tu bolsillo de Medicina
real (Revivir/Zinc/Carbos/Cura Parálisis/Éter, mismo patrón ya
documentado) aparece ahí.

CÓMO USARLO:

    python -m tools.probes.memory.dump_medicina_candidato_as_1_4
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    _MEDICINE_POCKET_START_BY_PROCESS,
    PROCESS_NAME_OMEGA_RUBY,
)

# Candidato: la misma dirección ya confirmada para Omega Ruby 1.4.
CANDIDATE_ADDRESS = _MEDICINE_POCKET_START_BY_PROCESS[PROCESS_NAME_OMEGA_RUBY]

SLOT_SIZE = 4
DUMP_SLOTS_BEFORE = 10
DUMP_SLOTS_AFTER = 30


def decode_slot(data, offset):
    return struct.unpack("<HH", data[offset:offset + SLOT_SIZE])


def main():
    print("================================")
    print("   DUMP CANDIDATO -- MEDICINA AS 1.4")
    print(f"   (hipótesis: {hex(CANDIDATE_ADDRESS)}, igual a Omega Ruby)")
    print("================================")
    print()

    reader = AzaharReader(process_name=PROCESS_NAME_ALPHA_SAPPHIRE)

    if not reader.connect():
        print("No se pudo conectar a Azahar.")
        return

    start = CANDIDATE_ADDRESS - DUMP_SLOTS_BEFORE * SLOT_SIZE
    size = (DUMP_SLOTS_BEFORE + 1 + DUMP_SLOTS_AFTER) * SLOT_SIZE

    data = reader.memory.read(start, size)

    if data is None or len(data) != size:
        print("No se pudo leer la zona candidata.")
        return

    for index in range(0, size, SLOT_SIZE):
        address = start + index
        item_id, quantity = decode_slot(data, index)

        marker = (
            " <-- CANDIDATO (¿Revivir, item_id=28?)"
            if address == CANDIDATE_ADDRESS
            else ""
        )

        print(
            f"0x{address:08X}  item_id={item_id:>4}  "
            f"cantidad={quantity:>4}{marker}"
        )

    print()
    print(
        "Si en la dirección marcada CANDIDATO ves item_id=28 con la "
        "cantidad real de Revivir que tenés, y los casilleros de al "
        "lado tienen pinta de Zinc/Carbos/Cura Parálisis/Éter (items "
        "de Medicina reales), la hipótesis se confirma -- avisame el "
        "resultado."
    )


if __name__ == "__main__":
    main()

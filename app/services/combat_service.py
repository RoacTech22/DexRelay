from __future__ import annotations

import struct

from app.memory.memory_reader import MemoryReader


COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_HP_OFFSET = 0x404

# Confirmado con tools/probes/combat/observar_puntero_combate.py:
# al salir de combate, el puntero NO vuelve a 0x00000000. Se queda
# en este valor fijo (COMBAT_POINTER_ADDRESS - 4), que es memoria
# "basura" reutilizada por el juego, no una estructura de batalla
# real. Si se trata como puntero valido, CombatService devuelve un
# HP congelado (el ultimo leido antes de salir de combate) para
# siempre, en vez de reportar que ya no hay combate.
COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4

LECTURA_DESCARTADA = object()


class CombatService:
    """Lee el HP de combate validando la consistencia del puntero."""

    def __init__(self, memory_reader: MemoryReader) -> None:
        self.memory_reader = memory_reader

    def read(self):
        """Lee el HP de combate."""

        pointer_before = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
            4,
        )

        if len(pointer_before) != 4:
            return LECTURA_DESCARTADA

        base_address = struct.unpack(
            "<I",
            pointer_before,
        )[0]

        if base_address in (0, COMBAT_INACTIVE_POINTER):
            return None

        hp_data = self.memory_reader.read(
            base_address + COMBAT_HP_OFFSET,
            2,
        )

        if len(hp_data) != 2:
            return LECTURA_DESCARTADA

        pointer_after = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
            4,
        )

        if pointer_after != pointer_before:
            return LECTURA_DESCARTADA

        return struct.unpack(
            "<H",
            hp_data,
        )[0]

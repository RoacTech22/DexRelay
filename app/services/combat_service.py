from __future__ import annotations

import struct

from app.memory.memory_reader import MemoryReader


COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_HP_OFFSET = 0x404

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

        if base_address == 0:
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

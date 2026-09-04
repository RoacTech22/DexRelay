from __future__ import annotations

from app.memory.memory_reader import MemoryReader


BADGES_ADDRESS = 0x08C6DDD4
BADGES_SIZE = 1
BADGE_COUNT = 8


class BadgesService:
    """Reads and interprets the Gen 6 badge bitfield from Azahar memory."""

    def __init__(self, memory_reader: MemoryReader) -> None:
        self.memory_reader = memory_reader

    def read_value(self) -> int:
        """Read the raw one-byte badge bitfield."""
        data = self.memory_reader.read(
            BADGES_ADDRESS,
            BADGES_SIZE,
        )

        # Bug real (04/09/2026, mismo patrón ya encontrado en
        # azahar_reader.py): memory_reader.read() puede devolver
        # None en un fallo transitorio de socket, no solo lanzar
        # una excepción -- len(None) tira TypeError en vez de un
        # RuntimeError claro. El try/except de _run_realtime_loop()
        # (app.py) ya evita que esto tire abajo el hilo, pero el
        # mensaje de error quedaba inútil ("NoneType has no len()")
        # en vez de decir qué pasó realmente.
        if data is None or len(data) != BADGES_SIZE:
            raise RuntimeError(
                f"Expected {BADGES_SIZE} byte for badges, "
                f"received {data!r}."
            )

        return data[0]

    def read_badges(self) -> dict:
        """Return the raw value, badge flags, and obtained count."""
        value = self.read_value()

        badges = [
            bool(value & (1 << index))
            for index in range(BADGE_COUNT)
        ]

        return {
            "value": value,
            "count": sum(badges),
            "badges": badges,
        }

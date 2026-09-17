from __future__ import annotations

from app.memory.pointers import get_badges_address

BADGES_SIZE = 1
BADGE_COUNT = 8


class BadgesService:
    """Reads and interprets the Gen 6 badge bitfield from Azahar memory."""

    def __init__(self, reader) -> None:
        # CORRECCIÓN (10/09/2026, bug real: "las medallas muestran 0
        # aunque tengo varias" -- ver el comentario largo junto a
        # get_badges_address()/_BADGES_ADDRESS_BY_PROCESS en
        # pointers.py). Antes se guardaba solo `memory_reader` y se
        # leía siempre la MISMA dirección fija (BADGES_ADDRESS,
        # marcada "compartida entre versiones" -- resultó falso).
        # Ahora se guarda el `reader` completo (AzaharReader) para
        # poder consultar `reader.process_name` en cada lectura --
        # no alcanza con guardarlo una sola vez acá en __init__,
        # porque en el momento en que se construye BadgesService
        # (Runtime.__init__()) todavía puede no haberse resuelto
        # qué juego está conectado (modo de detección automática,
        # ver find_game_process() en azahar_reader.py) -- se resuelve
        # recién más tarde, la primera vez que el Runtime logra
        # conectarse.
        self.reader = reader

    def read_value(self) -> int:
        """Read the raw one-byte badge bitfield."""

        address = get_badges_address(self.reader.process_name)

        data = self.reader.memory.read(
            address,
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

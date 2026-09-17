import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app.services.badges_service import BadgesService


class FakeMemoryReader:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def read(self, address, size):
        self.calls.append((address, size))
        return bytes([self.value])


class FakeReader:
    """
    Actualizado (10/09/2026, ver el bug real corregido en
    badges_service.py/pointers.py: get_badges_address() ahora
    depende de process_name) -- BadgesService ya no recibe un
    MemoryReader suelto, recibe el reader completo (AzaharReader),
    para poder consultar reader.process_name en cada lectura.
    """

    def __init__(self, value, process_name="sango-2"):
        self.memory = FakeMemoryReader(value)
        self.process_name = process_name


def test_badges():
    cases = {
        0x00: 0,
        0x01: 1,
        0x03: 2,
        0x07: 3,
        0x0F: 4,
    }

    for value, expected_count in cases.items():
        reader = FakeReader(value)
        service = BadgesService(reader)

        result = service.read_badges()

        assert result["value"] == value
        assert result["count"] == expected_count
        # Dirección de Alpha Sapphire confirmada el 10/09/2026 (ver
        # pointers.py) -- ya no la vieja "compartida entre
        # versiones" (0x08C6DDD4), que resultó ser falsa.
        assert reader.memory.calls == [(0x08C71DC4, 1)]

    print("OK - BadgesService")


if __name__ == "__main__":
    test_badges()

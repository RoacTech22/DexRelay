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


def test_badges():
    cases = {
        0x00: 0,
        0x01: 1,
        0x03: 2,
        0x07: 3,
        0x0F: 4,
    }

    for value, expected_count in cases.items():
        reader = FakeMemoryReader(value)
        service = BadgesService(reader)

        result = service.read_badges()

        assert result["value"] == value
        assert result["count"] == expected_count
        assert reader.calls == [(0x08C6DDD4, 1)]

    print("OK - BadgesService")


if __name__ == "__main__":
    test_badges()

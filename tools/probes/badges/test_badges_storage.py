from pathlib import Path
import json

from app.services.badges_storage import BadgesStorage


TEST_PATH = Path("data/state/test_badges.json")


def main():
    badges = {
        "value": 15,
        "count": 4,
        "badges": [
            True,
            True,
            True,
            True,
            False,
            False,
            False,
            False,
        ],
    }

    storage = BadgesStorage(TEST_PATH)
    storage.save(badges)

    with TEST_PATH.open("r", encoding="utf-8") as file:
        loaded = json.load(file)

    assert loaded == badges

    print("BadgesStorage test OK")
    print(loaded)

    TEST_PATH.unlink()
    print("Test file removed")


if __name__ == "__main__":
    main()

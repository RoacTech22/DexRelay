"""
Reproduce y valida el fix del 28/08/2026: borrar un encuentro con
el botón ✕ del panel (delete_encounter()) no evitaba que se
volviera a registrar solo en el ciclo siguiente si el Pokémon
seguía vivo en el juego -- el botón no servía para nada en la
práctica, porque el Pokémon reaparecía idéntico.

Decisión del usuario: ignorar para siempre, sin forma de
"deshacer el borrado" todavía.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.services.nuzlocke_service import NuzlockeService


class FakeStorage:
    def __init__(self):
        self.saved = None

    def load(self):
        return {
            "roster": [],
            "graveyard": [],
            "encounters": [],
            "pending_encounters": [],
            "starter_assigned": False,
            "traded_away": [],
            "ignored_nicknames": [],
        }

    def save(self, data):
        self.saved = data


def _team_with(*slots):
    padded = list(slots) + [
        {"slot": i, "empty": True}
        for i in range(len(slots) + 1, 7)
    ]
    return padded


def _starter():
    return {
        "slot": 1,
        "empty": False,
        "nickname": "Rocío",
        "species": "Mudkip",
        "speciesId": 258,
        "level": 10,
        "hp": 30,
        "maxHp": 30,
        "shiny": False,
        "metLocation": "",
        "eggLocation": "",
    }


def test_borrar_un_encuentro_no_se_vuelve_a_registrar_solo():

    service = NuzlockeService(FakeStorage())

    wild_catch = {
        "slot": 2,
        "empty": False,
        "nickname": "Zigzagoon",
        "species": "Zigzagoon",
        "speciesId": 263,
        "level": 3,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ruta 101",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), wild_catch))

    assert any(
        e["nickname"] == "Zigzagoon" for e in state["encounters"]
    )
    assert any(
        e["nickname"] == "Zigzagoon" for e in state["roster"]
    )

    # El usuario borra la fila desde el panel.
    service.delete_encounter("Ruta 101")

    # El Pokémon SIGUE VIVO en el juego -- se pasa la misma party
    # de nuevo, varias veces seguidas.
    for _ in range(3):
        state = service.update(
            _team_with(_starter(), wild_catch)
        )

        assert not any(
            e["nickname"] == "Zigzagoon"
            for e in state["encounters"]
        )
        assert not any(
            e["nickname"] == "Zigzagoon"
            for e in state["roster"]
        )
        assert not any(
            p["nickname"] == "Zigzagoon"
            for p in state.get("pending_encounters", [])
        )

    print(
        "OK - un encuentro borrado con el botón ✕ no se vuelve a "
        "registrar solo, aunque el Pokémon siga vivo en el juego"
    )


def test_borrar_no_afecta_a_otros_pokemon():
    """
    Ignorar un nickname puntual no debe afectar a otros Pokémon
    -- capturas nuevas siguen funcionando normal.
    """

    service = NuzlockeService(FakeStorage())

    wild_catch = {
        "slot": 2,
        "empty": False,
        "nickname": "Zigzagoon",
        "species": "Zigzagoon",
        "speciesId": 263,
        "level": 3,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ruta 101",
        "eggLocation": "",
    }

    service.update(_team_with(_starter(), wild_catch))
    service.delete_encounter("Ruta 101")

    other_catch = {
        "slot": 3,
        "empty": False,
        "nickname": "Poochyena",
        "species": "Poochyena",
        "speciesId": 261,
        "level": 4,
        "hp": 16,
        "maxHp": 16,
        "shiny": False,
        "metLocation": "Ruta 104",
        "eggLocation": "",
    }

    state = service.update(
        _team_with(_starter(), wild_catch, other_catch)
    )

    assert any(
        e["nickname"] == "Poochyena" for e in state["encounters"]
    )
    assert not any(
        e["nickname"] == "Zigzagoon" for e in state["encounters"]
    )

    print(
        "OK - ignorar un nickname puntual no afecta la "
        "detección normal de otros Pokémon"
    )


if __name__ == "__main__":
    test_borrar_un_encuentro_no_se_vuelve_a_registrar_solo()
    test_borrar_no_afecta_a_otros_pokemon()

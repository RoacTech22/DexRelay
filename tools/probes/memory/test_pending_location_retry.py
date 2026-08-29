"""
Reproduce y valida el fix del 28/08/2026: una captura que quedó
pendiente porque metLocation/eggLocation todavía no se habían
terminado de resolver en el instante exacto de la captura (el
usuario lo notó sobre todo cuando NO le pone nombre al Pokémon)
ahora se reintenta cada ciclo, en vez de quedar pendiente para
siempre.
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


def test_captura_sin_ubicacion_se_resuelve_en_ciclos_siguientes():
    """
    Caso principal: el jugador no le pone nombre al Pokémon --
    metLocation viene vacío en el instante exacto de la captura
    (torn read), pero unos ciclos después el juego ya terminó de
    escribirlo.
    """

    service = NuzlockeService(FakeStorage())

    # Ciclo 1: la captura se detecta, pero metLocation todavía
    # está vacío (el juego no terminó de escribirlo).
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
        "metLocation": "",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), wild_catch))

    assert len(state["pending_encounters"]) == 1
    assert state["pending_encounters"][0]["nickname"] == (
        "Zigzagoon"
    )
    assert state["encounters"] == [
        e for e in state["encounters"] if e["location"] == "Inicial"
    ]

    # Ciclo 2: sigue sin resolverse -- debe seguir pendiente, sin
    # duplicar el pendiente.
    state = service.update(_team_with(_starter(), wild_catch))
    assert len(state["pending_encounters"]) == 1

    # Ciclo 3: el juego ya terminó de escribir el lugar de
    # encuentro -- LocationResolver ahora sí devuelve "Ruta 101".
    wild_catch_resolved = {
        **wild_catch,
        "metLocation": "Ruta 101",
    }

    state = service.update(
        _team_with(_starter(), wild_catch_resolved)
    )

    assert state["pending_encounters"] == []

    zigzagoon_encounter = next(
        e for e in state["encounters"]
        if e["nickname"] == "Zigzagoon"
    )
    assert zigzagoon_encounter["location"] == "Ruta 101"
    assert zigzagoon_encounter["status"] == "capturado"

    print(
        "OK - una captura sin ubicación en el instante exacto se "
        "resuelve sola unos ciclos después, no queda pendiente "
        "para siempre"
    )


def test_captura_que_nunca_se_resuelve_sigue_pendiente_sin_duplicarse():
    """
    Si metLocation/eggLocation nunca llegan a resolverse (ej. el
    Pokémon deja de estar visible, o el bridge sigue caído), la
    entrada pendiente se mantiene tal cual -- no se pierde ni se
    duplica en cada ciclo.
    """

    service = NuzlockeService(FakeStorage())

    wild_catch = {
        "slot": 2,
        "empty": False,
        "nickname": "Poochyena",
        "species": "Poochyena",
        "speciesId": 261,
        "level": 4,
        "hp": 16,
        "maxHp": 16,
        "shiny": False,
        "metLocation": "",
        "eggLocation": "",
    }

    for _ in range(5):
        state = service.update(
            _team_with(_starter(), wild_catch)
        )
        assert len(state["pending_encounters"]) == 1

    assert state["pending_encounters"][0]["nickname"] == (
        "Poochyena"
    )

    print(
        "OK - una captura que nunca resuelve ubicación sigue "
        "pendiente sin duplicarse en ciclos sucesivos"
    )


def test_reintento_tambien_funciona_para_egg_location():
    """
    El mismo reintento aplica a eggLocation ("Entregado por"), no
    solo a metLocation -- un huevo recién nacido también puede
    tardar un par de ciclos en que el bridge resuelva ese dato.
    """

    service = NuzlockeService(FakeStorage())

    hatched = {
        "slot": 2,
        "empty": False,
        "nickname": "Togepi",
        "species": "Togepi",
        "speciesId": 175,
        "level": 1,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), hatched))
    assert len(state["pending_encounters"]) == 1

    hatched_resolved = {
        **hatched,
        "eggLocation": "Anciana del Balneario",
    }

    state = service.update(
        _team_with(_starter(), hatched_resolved)
    )

    assert state["pending_encounters"] == []

    togepi_encounter = next(
        e for e in state["encounters"]
        if e["nickname"] == "Togepi"
    )
    assert togepi_encounter["location"] == "Anciana del Balneario"
    assert togepi_encounter["status"] == "especial"
    assert togepi_encounter.get("origin") == "huevo"

    print(
        "OK - el reintento también resuelve eggLocation, no solo "
        "metLocation"
    )


if __name__ == "__main__":
    test_captura_sin_ubicacion_se_resuelve_en_ciclos_siguientes()
    test_captura_que_nunca_se_resuelve_sigue_pendiente_sin_duplicarse()
    test_reintento_tambien_funciona_para_egg_location()

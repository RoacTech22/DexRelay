"""
Valida la detección automática de intercambios (28/08/2026, a
pedido del usuario):

1. El Pokémon que LLEGA por trueque se registra como "especial"/
   "intercambiado", con "Intercambiado" como pseudo-ubicación en
   vez del texto en inglés que reporta el juego ("a Link Trade
   (NPC)", confirmado en el juego real).
2. El Pokémon que SE VA (el que el jugador entregó) se marca en
   una lista aparte (`traded_away`) -- se infiere por correlación:
   un trueque es transaccional, así que el mismo ciclo en que
   aparece la captura nueva por intercambio, el que se fue
   desaparece de la party/caja para siempre sin haber muerto.
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


def test_pokemon_que_llega_se_registra_intercambiado():

    service = NuzlockeService(FakeStorage())

    traded_in = {
        "slot": 2,
        "empty": False,
        "nickname": "Wobbuffet",
        "species": "Wobbuffet",
        "speciesId": 202,
        "level": 15,
        "hp": 40,
        "maxHp": 40,
        "shiny": False,
        "metLocation": "a Link Trade (NPC)",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), traded_in))

    encounters = state["encounters"]

    wobbuffet_encounter = next(
        e for e in encounters if e["nickname"] == "Wobbuffet"
    )

    assert wobbuffet_encounter["location"] == "Intercambiado"
    assert wobbuffet_encounter["status"] == "especial"
    assert wobbuffet_encounter.get("origin") == "intercambio"

    assert state.get("pending_encounters", []) == []

    print(
        "OK - un Pokémon recibido por trueque se registra como "
        "'especial/intercambiado' con pseudo-ubicación fija, no "
        "el texto en inglés del juego"
    )


def test_segundo_intercambio_se_diferencia_con_nickname():

    service = NuzlockeService(FakeStorage())

    traded_in_a = {
        "slot": 2,
        "empty": False,
        "nickname": "Wobbuffet",
        "species": "Wobbuffet",
        "speciesId": 202,
        "level": 15,
        "hp": 40,
        "maxHp": 40,
        "shiny": False,
        "metLocation": "a Link Trade (NPC)",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), traded_in_a))
    assert (
        state["encounters"][-1]["location"] == "Intercambiado"
    )

    traded_in_b = {
        "slot": 3,
        "empty": False,
        "nickname": "Ledian",
        "species": "Ledian",
        "speciesId": 166,
        "level": 12,
        "hp": 30,
        "maxHp": 30,
        "shiny": False,
        "metLocation": "a Link Trade (NPC)",
        "eggLocation": "",
    }

    state = service.update(
        _team_with(_starter(), traded_in_a, traded_in_b)
    )

    ledian_encounter = next(
        e for e in state["encounters"]
        if e["nickname"] == "Ledian"
    )

    assert (
        ledian_encounter["location"] == "Intercambiado (Ledian)"
    )

    print(
        "OK - un segundo intercambio se diferencia con el "
        "nickname, el primero queda sin modificar"
    )


def test_captura_salvaje_normal_no_se_confunde_con_intercambio():

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

    zigzagoon_encounter = next(
        e for e in state["encounters"]
        if e["nickname"] == "Zigzagoon"
    )

    assert zigzagoon_encounter["location"] == "Ruta 101"
    assert zigzagoon_encounter["status"] == "capturado"
    assert zigzagoon_encounter.get("origin") is None

    print(
        "OK - una captura salvaje normal no se confunde con un "
        "intercambio"
    )


def test_pokemon_que_se_va_queda_marcado_en_traded_away():
    """
    Caso principal: el Pokémon que el jugador entrega en el
    trueque desaparece de la party/caja el mismo ciclo en que
    llega el nuevo -- se correlaciona y se mueve a `traded_away`.
    """

    service = NuzlockeService(FakeStorage())

    given_away = {
        "slot": 2,
        "empty": False,
        "nickname": "Poochyena",
        "species": "Poochyena",
        "speciesId": 261,
        "level": 8,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "Ruta 104",
        "eggLocation": "",
    }

    # Ciclo 1: se registra la captura salvaje normal que después
    # se va a intercambiar.
    state = service.update(_team_with(_starter(), given_away))
    assert len(state["roster"]) == 2

    # Ciclo 2: mismo equipo, para que quede "vista" en el ciclo
    # anterior (hace falta al menos un ciclo previo con la misma
    # composición antes de que la comparación de "visible" tenga
    # sentido).
    state = service.update(_team_with(_starter(), given_away))
    assert len(state["roster"]) == 2

    # Ciclo 3: el trueque se completa -- "Poochyena" desaparece,
    # llega "Abra" con metLocation de intercambio, en el MISMO
    # ciclo.
    traded_in = {
        "slot": 2,
        "empty": False,
        "nickname": "Abra",
        "species": "Abra",
        "speciesId": 63,
        "level": 9,
        "hp": 18,
        "maxHp": 18,
        "shiny": False,
        "metLocation": "a Link Trade (NPC)",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), traded_in))

    roster_nicknames = {
        entry["nickname"] for entry in state["roster"]
    }
    assert "Poochyena" not in roster_nicknames
    assert "Abra" in roster_nicknames

    traded_away = state.get("traded_away", [])
    assert len(traded_away) == 1
    assert traded_away[0]["nickname"] == "Poochyena"
    assert traded_away[0]["species"] == "Poochyena"
    assert traded_away[0]["receivedNickname"] == "Abra"

    # No debe haber terminado en el cementerio -- no murió.
    assert all(
        e["nickname"] != "Poochyena" for e in state["graveyard"]
    )

    # El encuentro original (Ruta 104, donde se lo capturó) tiene
    # que quedar marcado con tradedAway=True, sin perder el
    # registro de la ruta.
    poochyena_encounter = next(
        e for e in state["encounters"]
        if e["nickname"] == "Poochyena"
    )
    assert poochyena_encounter["location"] == "Ruta 104"
    assert poochyena_encounter.get("tradedAway") is True

    print(
        "OK - el Pokémon entregado en el trueque se marca en "
        "traded_away, correlacionado con el que llegó"
    )


def test_ambiguedad_no_marca_nada():
    """
    Si desaparecen DOS Pokémon a la vez (o ninguno) en el mismo
    ciclo en que llega un intercambio, no se adivina -- no se
    marca nada en traded_away.
    """

    service = NuzlockeService(FakeStorage())

    mon_a = {
        "slot": 2,
        "empty": False,
        "nickname": "Poochyena",
        "species": "Poochyena",
        "speciesId": 261,
        "level": 8,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "Ruta 104",
        "eggLocation": "",
    }

    mon_b = {
        "slot": 3,
        "empty": False,
        "nickname": "Taillow",
        "species": "Taillow",
        "speciesId": 276,
        "level": 8,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "Ruta 104",
        "eggLocation": "",
    }

    service.update(_team_with(_starter(), mon_a, mon_b))
    service.update(_team_with(_starter(), mon_a, mon_b))

    # Los dos desaparecen a la vez, y llega un intercambio.
    traded_in = {
        "slot": 2,
        "empty": False,
        "nickname": "Abra",
        "species": "Abra",
        "speciesId": 63,
        "level": 9,
        "hp": 18,
        "maxHp": 18,
        "shiny": False,
        "metLocation": "a Link Trade (NPC)",
        "eggLocation": "",
    }

    state = service.update(_team_with(_starter(), traded_in))

    assert state.get("traded_away", []) == []

    print(
        "OK - si desaparece más de un Pokémon a la vez, no se "
        "adivina cuál fue el intercambiado -- no se marca nada"
    )


def test_renombre_por_reconciliacion_no_se_confunde_con_intercambio():
    """
    Si un renombre por reconciliación (huevo que nace, por
    ejemplo) pasa en el MISMO ciclo que un intercambio totalmente
    aparte, el nickname viejo no debe terminar marcado como
    'traded_away' -- se renombró, no se fue.
    """

    service = NuzlockeService(FakeStorage())

    egg = {
        "slot": 2,
        "empty": False,
        "nickname": "Huevo",
        "species": "Togepi",
        "speciesId": 175,
        "level": 1,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "",
        "eggLocation": "",
    }

    service.update(_team_with(_starter(), egg))
    service.update(_team_with(_starter(), egg))

    # El huevo nace (se renombra a "Togepi") EN EL MISMO ciclo
    # en que, por otro lado, llega un intercambio sin relación.
    hatched = {**egg, "nickname": "Togepi"}

    traded_in = {
        "slot": 3,
        "empty": False,
        "nickname": "Abra",
        "species": "Abra",
        "speciesId": 63,
        "level": 9,
        "hp": 18,
        "maxHp": 18,
        "shiny": False,
        "metLocation": "a Link Trade (NPC)",
        "eggLocation": "",
    }

    state = service.update(
        _team_with(_starter(), hatched, traded_in)
    )

    # "Togepi" (nacido del huevo) tiene que seguir en el roster,
    # NO en traded_away.
    roster_nicknames = {
        entry["nickname"] for entry in state["roster"]
    }
    assert "Togepi" in roster_nicknames

    assert state.get("traded_away", []) == []

    print(
        "OK - un renombre por reconciliación en el mismo ciclo "
        "que un intercambio no se confunde con el que se fue"
    )


if __name__ == "__main__":
    test_pokemon_que_llega_se_registra_intercambiado()
    test_segundo_intercambio_se_diferencia_con_nickname()
    test_captura_salvaje_normal_no_se_confunde_con_intercambio()
    test_pokemon_que_se_va_queda_marcado_en_traded_away()
    test_ambiguedad_no_marca_nada()
    test_renombre_por_reconciliacion_no_se_confunde_con_intercambio()

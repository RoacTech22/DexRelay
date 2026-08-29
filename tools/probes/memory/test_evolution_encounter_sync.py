"""
Valida el fix del 28/08/2026 (a pedido del usuario): cuando un
Pokémon evoluciona, el registro de "encuentro" de su ruta (el que
alimenta el panel /panel/nuzlocke) tiene que actualizar el nombre
de especie también -- antes quedaba fijado para siempre con la
especie de la captura original, aunque el roster sí reflejara la
evolución correctamente.

El sprite del panel se resuelve en el frontend a partir del texto
de especie (species_list -> speciesId -> sprite, ver
panels/nuzlocke/app.js -> updateRowFromAssignment()), así que
alcanza con validar acá que el backend actualiza el campo
`species` del encuentro -- el resto ya estaba andando.
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
        }

    def save(self, data):
        self.saved = data


def _team_with(slot1):
    return [slot1] + [
        {"slot": i, "empty": True} for i in range(2, 7)
    ]


def test_evolucion_actualiza_especie_del_encuentro():

    service = NuzlockeService(FakeStorage())

    torchic = {
        "slot": 1,
        "empty": False,
        "nickname": "Poli",
        "species": "Torchic",
        "speciesId": 255,
        "level": 12,
        "hp": 30,
        "maxHp": 30,
        "shiny": False,
        "metLocation": "",
    }

    state = service.update(_team_with(torchic))

    # No es el inicial (es el primer Pokémon de la partida en este
    # test, así que en la práctica SÍ caería como "Inicial" -- no
    # importa para este test, solo nos interesa el campo species
    # del encuentro que haya quedado registrado).
    assert state["encounters"][0]["species"] == "Torchic"

    # Evoluciona a Combusken en el nivel 16.
    combusken = {
        **torchic,
        "species": "Combusken",
        "speciesId": 256,
        "level": 16,
    }

    state = service.update(_team_with(combusken))

    assert state["roster"][0]["species"] == "Combusken"
    assert state["roster"][0]["speciesId"] == 256

    assert state["encounters"][0]["species"] == "Combusken"
    assert state["encounters"][0]["nickname"] == "Poli"

    print(
        "OK - al evolucionar, el encuentro de la ruta actualiza "
        "el nombre de especie (antes quedaba fijado con la "
        "especie de la captura original)"
    )


def test_solo_subir_de_nivel_sin_evolucionar_no_toca_el_encuentro():
    """
    Un level-up SIN evolución (misma especie, nivel distinto) no
    debe tocar el campo `species` del encuentro -- ya estaba bien
    (nada que actualizar), solo confirma que el fix no reescribe
    de más innecesariamente.
    """

    service = NuzlockeService(FakeStorage())

    torchic = {
        "slot": 1,
        "empty": False,
        "nickname": "Poli",
        "species": "Torchic",
        "speciesId": 255,
        "level": 5,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(torchic))

    leveled_up = {
        **torchic,
        "level": 8,
    }

    state = service.update(_team_with(leveled_up))

    assert state["roster"][0]["level"] == 8
    assert state["encounters"][0]["species"] == "Torchic"

    print(
        "OK - subir de nivel sin evolucionar no altera el "
        "encuentro (sigue con la misma especie)"
    )


if __name__ == "__main__":
    test_evolucion_actualiza_especie_del_encuentro()
    test_solo_subir_de_nivel_sin_evolucionar_no_toca_el_encuentro()

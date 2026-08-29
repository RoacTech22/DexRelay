"""
Reproduce el bug real reportado el 27/08/2026: el inicial se
registra dos veces con dos nicknames distintos.

En la pelea contra el Pokémon salvaje que ataca al profesor (justo
al arrancar la partida), el inicial YA está en la party -- por eso
se puede pelear con él -- pero todavía no pasó por el evento
oficial del laboratorio donde el jugador le pone nombre. El juego
lo reporta con el nombre por defecto de la especie en ese momento;
después, en el laboratorio, aparece con el nickname real.

Datos reales del bug (data/nuzlocke.json de la partida del
usuario, antes del fix):

    roster:
      - nickname="Mudkip" speciesId=258 level=5  (fantasma, del
        combate contra el Pochiyena)
      - nickname="Daron"  speciesId=258 level=7  (el inicial real,
        nombrado en el laboratorio)
    encounters:
      - location="Inicial" nickname="Mudkip"   (nunca se actualizó
        al nombre real)

NuzlockeService._reconcile_starter_rename() migra la identidad del
fantasma al nickname real en vez de crear un registro aparte.
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


def test_rename_del_inicial_migra_identidad_sin_duplicar():
    service = NuzlockeService(FakeStorage())

    # Ciclo 1: pelea contra el Pochiyena -- el inicial ya está en
    # la party, con el nombre por defecto de la especie.
    default_named = {
        "slot": 1,
        "empty": False,
        "nickname": "Mudkip",
        "species": "Mudkip",
        "speciesId": 258,
        "level": 5,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    state = service.update(_team_with(default_named))

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Mudkip"
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["encounters"][0]["nickname"] == "Mudkip"

    # Ciclo 2: en el laboratorio, el jugador le pone nombre real.
    # Mismo Pokémon (misma especie), nickname distinto, y encima
    # subió de nivel en el camino (5 -> 7).
    renamed = {
        **default_named,
        "nickname": "Daron",
        "level": 7,
    }

    state = service.update(_team_with(renamed))

    # No debe haber quedado ningún fantasma "Mudkip" en el roster.
    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Daron"
    assert state["roster"][0]["level"] == 7
    assert state["roster"][0]["speciesId"] == 258

    # "Inicial" tiene que apuntar al nickname real, no al fantasma.
    assert len(state["encounters"]) == 1
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["encounters"][0]["nickname"] == "Daron"

    # Ciclos siguientes con el mismo nickname: no debe duplicar ni
    # volver a migrar nada.
    for _ in range(3):
        state = service.update(_team_with(renamed))
        assert len(state["roster"]) == 1
        assert len(state["encounters"]) == 1

    print(
        "OK - el rename del inicial (nombre por defecto -> nombre "
        "real del laboratorio) migra la identidad existente, sin "
        "dejar un fantasma en el roster ni duplicar 'Inicial'"
    )


def test_si_el_jugador_no_renombra_no_hay_migracion_ni_bug():
    """
    Si el jugador deja el nombre por defecto (no lo cambia en el
    laboratorio), el nickname es igual en los dos momentos -- el
    lookup normal por nickname ya lo encuentra, la reconciliación
    ni siquiera entra en juego. No debe haber ningún efecto
    secundario.
    """
    service = NuzlockeService(FakeStorage())

    default_named = {
        "slot": 1,
        "empty": False,
        "nickname": "Mudkip",
        "species": "Mudkip",
        "speciesId": 258,
        "level": 5,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(default_named))

    same_named = {**default_named, "level": 6}

    state = service.update(_team_with(same_named))

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Mudkip"
    assert state["roster"][0]["level"] == 6

    print(
        "OK - si el jugador no renombra el inicial, no hay "
        "migración ni efectos secundarios"
    )


def test_reconciliacion_no_aplica_a_especies_distintas():
    """
    Salvaguarda: si por algún motivo aparece un nickname nuevo con
    una especie DISTINTA a la del Inicial ya registrado, no debe
    migrarse nada -- eso sería una captura genuina, no un rename.
    (species clause / lógica normal de _register_new_capture se
    encarga de esa captura por su cuenta.)
    """
    service = NuzlockeService(FakeStorage())

    starter = {
        "slot": 1,
        "empty": False,
        "nickname": "Mudkip",
        "species": "Mudkip",
        "speciesId": 258,
        "level": 5,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(starter))

    other_species = {
        "slot": 2,
        "empty": False,
        "nickname": "Ziggy",
        "species": "Zigzagoon",
        "speciesId": 263,
        "level": 3,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ruta 101",
    }

    team = [starter, other_species] + [
        {"slot": i, "empty": True} for i in range(3, 7)
    ]

    state = service.update(team)

    nicknames = {e["nickname"] for e in state["roster"]}
    assert nicknames == {"Mudkip", "Ziggy"}
    assert len(state["roster"]) == 2

    print(
        "OK - una especie distinta al Inicial no dispara "
        "reconciliación, se trata como captura normal"
    )


if __name__ == "__main__":
    test_rename_del_inicial_migra_identidad_sin_duplicar()
    test_si_el_jugador_no_renombra_no_hay_migracion_ni_bug()
    test_reconciliacion_no_aplica_a_especies_distintas()

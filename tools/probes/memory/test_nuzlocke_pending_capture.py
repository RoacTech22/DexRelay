"""
Valida el diseño actual (26-27/08/2026, reemplaza al del
26/08/2026 probado antes en este mismo archivo):

- El Inicial se registra directo desde el escaneo de la party,
  igual que antes.
- Cualquier OTRA captura nueva vista en `team` (party) TAMBIÉN se
  registra directo ahora -- se volvió al comportamiento del
  Bloque A original. Ya no hace falta esperar ningún dato
  confirmado por separado para las capturas de party.
- Las capturas que van a la Caja PC (nunca aparecen en `team`)
  llegan por `boxed_party` (lista completa de AzaharReader.
  read_box()) y se registran igual, sin espera -- decisión
  explícita del usuario: probar sin colchón de estabilidad
  primero, agregar uno después solo si hace falta en el juego
  real.

El bucle de `team` sigue siendo responsable de evolución/muerte de
Pokémon YA registrados (por cualquier camino).
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


STARTER_READ = {
    "slot": 1,
    "empty": False,
    "nickname": "Blazy",
    "species": "Torchic",
    "speciesId": 255,
    "level": 5,
    "hp": 20,
    "maxHp": 20,
    "shiny": False,
    "metLocation": "",
}


def test_inicial_se_registra_de_inmediato_por_party():
    service = NuzlockeService(FakeStorage())

    state = service.update(_team_with(STARTER_READ))

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Blazy"
    assert state["starter_assigned"] is True
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["encounters"][0]["nickname"] == "Blazy"

    print("OK - el inicial se registra de inmediato por escaneo de party")


def test_captura_normal_en_party_se_registra_directo():
    """
    Una captura nueva vista en `team` que NO es el Inicial (ya hay
    starter_assigned=True) se registra directo, sin esperar
    `boxed_party` -- vuelve al comportamiento del Bloque A
    original. Solo las capturas de CAJA PC (que nunca aparecen en
    `team`) dependen de `boxed_party`.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [
            {
                "nickname": "Blazy",
                "speciesId": 255,
                "species": "Torchic",
                "level": 5,
                "caughtAt": "x",
            }
        ],
        "graveyard": [],
        "encounters": [
            {
                "location": "Inicial",
                "nickname": "Blazy",
                "species": "Torchic",
                "status": "capturado",
                "updatedAt": "x",
            }
        ],
        "pending_encounters": [],
        "starter_assigned": True,
    }

    wild_capture = {
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

    team = [STARTER_READ, wild_capture] + [
        {"slot": i, "empty": True} for i in range(3, 7)
    ]

    state = service.update(team)

    assert len(state["roster"]) == 2
    assert "Ziggy" in {e["nickname"] for e in state["roster"]}
    assert state["encounters"][-1]["location"] == "Ruta 101"
    assert state["encounters"][-1]["nickname"] == "Ziggy"

    # Ciclos siguientes: ya está en roster, no se duplica.
    for _ in range(5):
        state = service.update(team)
        assert len(state["roster"]) == 2

    print(
        "OK - una captura nueva (no inicial) vista en team se "
        "registra directo, sin esperar boxed_party"
    )


def test_boxed_party_registra_capturas_de_caja():
    """
    El registro real de una captura que fue a la Caja PC (party
    llena) llega por `boxed_party` (lista de AzaharReader.
    read_box()) -- NuzlockeService recorre cada entrada ocupada y
    registra la que no esté ya conocida, igual que hace con `team`.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [
            {
                "nickname": "Blazy",
                "speciesId": 255,
                "species": "Torchic",
                "level": 5,
                "caughtAt": "x",
            }
        ],
        "graveyard": [],
        "encounters": [
            {
                "location": "Inicial",
                "nickname": "Blazy",
                "species": "Torchic",
                "status": "capturado",
                "updatedAt": "x",
            }
        ],
        "pending_encounters": [],
        "starter_assigned": True,
    }

    team = _team_with(STARTER_READ)

    boxed_party = [
        {
            "slot": 1,
            "empty": False,
            "nickname": "Ziggy",
            "species": "Zigzagoon",
            "speciesId": 263,
            "level": 3,
            "hp": 0,
            "maxHp": 0,
            "shiny": False,
            "metLocation": "Ruta 101",
        }
    ]

    state = service.update(team, boxed_party=boxed_party)

    assert len(state["roster"]) == 2
    nicknames = {e["nickname"] for e in state["roster"]}
    assert nicknames == {"Blazy", "Ziggy"}
    assert state["encounters"][-1]["location"] == "Ruta 101"
    assert state["encounters"][-1]["nickname"] == "Ziggy"

    # Ciclo siguiente: la Caja PC sigue reportando el mismo
    # Pokémon (sigue ahí, no se fue a ningún lado) -- no debe
    # duplicarse.
    state = service.update(team, boxed_party=boxed_party)
    assert len(state["roster"]) == 2

    print(
        "OK - boxed_party registra las capturas de Caja PC y no "
        "duplica en ciclos siguientes"
    )


def test_boxed_party_vacio_o_none_no_rompe_nada():
    """
    `boxed_party` es opcional -- None o lista vacía no debe romper
    update() (compatibilidad con llamadas que no pasan el
    argumento, y con el caso real de una caja sin nada en ella).
    """
    service = NuzlockeService(FakeStorage())

    state = service.update(_team_with(STARTER_READ), boxed_party=None)
    assert len(state["roster"]) == 1

    state = service.update(_team_with(STARTER_READ), boxed_party=[])
    assert len(state["roster"]) == 1

    print("OK - boxed_party None o vacío no rompe update()")


if __name__ == "__main__":
    test_inicial_se_registra_de_inmediato_por_party()
    test_captura_normal_en_party_se_registra_directo()
    test_boxed_party_registra_capturas_de_caja()
    test_boxed_party_vacio_o_none_no_rompe_nada()

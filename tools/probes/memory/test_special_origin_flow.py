"""
Valida el rediseño de "Capturas sin ruta asignada" -> "¿Pokémon
Especial?" (27/08/2026, ver Documento Maestro):

- Los viejos estados sueltos "shiny"/"regalo"/"intercambiado"
  desaparecen -- ahora es un único status "especial" con el
  origen (shiny/huevo/intercambio/evento/regalo) guardado aparte.
- Un shiny detectado automáticamente CON ruta real conocida se
  registra directo (sin pasar por pendientes) como
  status="especial", origin="shiny", en la ruta real.
- Una captura pendiente (huevo/regalo/intercambio/evento, o un
  shiny cuya ruta ya estaba tomada) se resuelve vía
  assign_special_origin(), que genera una pseudo-ubicación única
  por Pokémon ("Especial (Nickname)") -- nunca una sola fila
  compartida, porque puede haber varias capturas especiales en la
  misma partida.
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
            "starter_assigned": True,
        }

    def save(self, data):
        self.saved = data


def _team_with(*slots):
    padded = list(slots) + [
        {"slot": i, "empty": True}
        for i in range(len(slots) + 1, 7)
    ]
    return padded


def test_shiny_con_ruta_conocida_registra_especial_directo():
    """
    Un shiny detectado con metLocation ya resuelto se registra
    DIRECTO (no pasa por pendientes) -- status="especial",
    origin="shiny", en la ruta real donde se lo encontró.
    """
    service = NuzlockeService(FakeStorage())

    shiny_wild = {
        "slot": 1,
        "empty": False,
        "nickname": "Brillante",
        "species": "Zigzagoon",
        "speciesId": 263,
        "level": 4,
        "hp": 15,
        "maxHp": 15,
        "shiny": True,
        "metLocation": "Ruta 101",
    }

    state = service.update(_team_with(shiny_wild))

    assert len(state["pending_encounters"]) == 0
    assert len(state["encounters"]) == 1

    entry = state["encounters"][0]

    assert entry["location"] == "Ruta 101"
    assert entry["status"] == "especial"
    assert entry["origin"] == "shiny"
    assert entry["nickname"] == "Brillante"

    print(
        "OK - shiny con ruta conocida se registra directo como "
        "especial/shiny, en la ruta real"
    )


def test_pendiente_guarda_metlocation_para_mostrar_en_el_panel():
    """
    Una captura que cae a pendientes por colisión de ruta (ya
    había un encuentro en esa ubicación) conserva su metLocation
    real en el registro pendiente, para que el panel pueda
    mostrar "Ruta real detectada: X" en la tarjeta.
    """
    service = NuzlockeService(FakeStorage())

    # Ocupa "Ruta 101" primero con una captura normal.
    first = {
        "slot": 1,
        "empty": False,
        "nickname": "Zig1",
        "species": "Zigzagoon",
        "speciesId": 263,
        "level": 4,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ruta 101",
    }

    service.update(_team_with(first))

    # Segunda captura, misma ruta -- colisiona, cae a pendientes,
    # pero con el metLocation real conservado.
    second = {
        "slot": 2,
        "empty": False,
        "nickname": "Zig2",
        "species": "Poochyena",
        "speciesId": 261,
        "level": 4,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ruta 101",
    }

    state = service.update(_team_with(first, second))

    assert len(state["pending_encounters"]) == 1

    pending = state["pending_encounters"][0]

    assert pending["nickname"] == "Zig2"
    assert pending["metLocation"] == "Ruta 101"

    print(
        "OK - una captura pendiente por colisión de ruta guarda "
        "su metLocation real para mostrar en el panel"
    )


def test_huevo_sin_ruta_pendiente_con_metlocation_none():
    """
    Un huevo/regalo/intercambio (sin metLocation en absoluto) cae
    a pendientes con metLocation=None -- el panel no muestra la
    línea de "ruta real detectada" en ese caso.
    """
    service = NuzlockeService(FakeStorage())

    egg_hatch = {
        "slot": 1,
        "empty": False,
        "nickname": "Huevito",
        "species": "Togepi",
        "speciesId": 175,
        "level": 1,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "",
    }

    state = service.update(_team_with(egg_hatch))

    assert len(state["pending_encounters"]) == 1
    assert state["pending_encounters"][0]["metLocation"] in (None, "")

    print(
        "OK - una captura sin ruta real (huevo/regalo/"
        "intercambio) cae a pendientes con metLocation vacío"
    )


def test_assign_special_origin_pseudo_ubicacion_unica_por_pokemon():
    """
    Dos capturas especiales distintas en la misma partida tienen
    que quedar en DOS filas separadas ("Especial (Nickname)"), no
    pisarse una a la otra.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [],
        "pending_encounters": [
            {
                "nickname": "Huevito",
                "speciesId": 175,
                "species": "Togepi",
                "shiny": False,
                "metLocation": None,
                "caughtAt": "x",
            },
            {
                "nickname": "Trueque",
                "speciesId": 92,
                "species": "Gastly",
                "shiny": False,
                "metLocation": None,
                "caughtAt": "x",
            },
        ],
        "starter_assigned": True,
    }

    result_1 = service.assign_special_origin("Huevito", "huevo")
    result_2 = service.assign_special_origin("Trueque", "intercambio")

    locations = {e["location"] for e in result_2["encounters"]}

    assert locations == {
        "Especial (Huevito)",
        "Especial (Trueque)",
    }

    huevito_entry = next(
        e for e in result_2["encounters"]
        if e["nickname"] == "Huevito"
    )
    trueque_entry = next(
        e for e in result_2["encounters"]
        if e["nickname"] == "Trueque"
    )

    assert huevito_entry["status"] == "especial"
    assert huevito_entry["origin"] == "huevo"

    assert trueque_entry["status"] == "especial"
    assert trueque_entry["origin"] == "intercambio"

    assert result_2["pending_encounters"] == []

    print(
        "OK - dos capturas especiales en la misma partida quedan "
        "en pseudo-ubicaciones separadas, sin pisarse"
    )


def test_assign_special_origin_rechaza_origen_invalido():
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [],
        "pending_encounters": [
            {
                "nickname": "Huevito",
                "speciesId": 175,
                "species": "Togepi",
                "shiny": False,
                "metLocation": None,
                "caughtAt": "x",
            }
        ],
        "starter_assigned": True,
    }

    try:
        service.assign_special_origin("Huevito", "no_existe")
        raise AssertionError("Debía rechazar un origen inválido")
    except ValueError:
        pass

    print("OK - assign_special_origin rechaza un origen inválido")


def test_save_encounter_conserva_origen_al_editar_sin_mandarlo():
    """
    Editar nickname/especie de una fila ya "especial" desde la
    tabla principal (que no manda 'origin' en el payload) no debe
    perder el origen que ya tenía.
    """
    service = NuzlockeService(FakeStorage())

    service.save_encounter(
        "Especial (Huevito)",
        "Huevito",
        "Togepi",
        "especial",
        origin="huevo",
    )

    encounters = service.save_encounter(
        "Especial (Huevito)",
        "Huevito",
        "Togetic",
        "especial",
        # sin origin -- simula lo que manda saveRow() del panel
    )

    entry = encounters[0]

    assert entry["species"] == "Togetic"
    assert entry["origin"] == "huevo"

    print(
        "OK - editar nickname/especie de una fila 'especial' sin "
        "mandar origen conserva el que ya tenía"
    )


def test_save_encounter_rechaza_especial_sin_origen_en_fila_nueva():
    service = NuzlockeService(FakeStorage())

    try:
        service.save_encounter(
            "Ruta 102",
            "Nuevo",
            "Wurmple",
            "especial",
        )
        raise AssertionError(
            "Debía rechazar 'especial' sin origen en una fila "
            "nueva"
        )
    except ValueError:
        pass

    print(
        "OK - una fila NUEVA con status='especial' y sin origen "
        "se rechaza"
    )


def test_especial_con_ruta_real_tomada_usa_sufijo_sin_pisar():
    """
    Caso principal (27/08/2026, corrección tras aclaración del
    usuario): si la captura pendiente SÍ tiene una ruta real
    conocida (colisión -- por eso cayó a pendientes), el origen
    especial se guarda en esa ruta con el sufijo "(Especial)",
    SIN pisar el registro que ya estaba ahí.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [
            {
                "location": "Ruta 101",
                "nickname": "Zig1",
                "species": "Zigzagoon",
                "status": "capturado",
                "origin": None,
                "updatedAt": "x",
            }
        ],
        "pending_encounters": [
            {
                "nickname": "Brillante",
                "speciesId": 263,
                "species": "Zigzagoon",
                "shiny": True,
                "metLocation": "Ruta 101",
                "caughtAt": "x",
            }
        ],
        "starter_assigned": True,
    }

    result = service.assign_special_origin("Brillante", "shiny")

    locations = {e["location"] for e in result["encounters"]}

    assert locations == {"Ruta 101", "Ruta 101 (Especial)"}

    original = next(
        e for e in result["encounters"]
        if e["location"] == "Ruta 101"
    )
    special = next(
        e for e in result["encounters"]
        if e["location"] == "Ruta 101 (Especial)"
    )

    assert original["nickname"] == "Zig1"
    assert special["nickname"] == "Brillante"
    assert special["status"] == "especial"
    assert special["origin"] == "shiny"

    print(
        "OK - una captura especial con ruta real tomada se "
        "guarda como 'Ruta (Especial)', sin pisar la existente"
    )


def test_especial_con_ruta_real_libre_la_usa_directo():
    """
    Caso raro pero posible: la ruta real ya viene en el pendiente
    pero en realidad todavía no hay ningún encuentro ahí (por
    ejemplo, se descartó el que la ocupaba). Se usa directo, sin
    sufijo -- no hace falta inventar un nombre distinto.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [],
        "pending_encounters": [
            {
                "nickname": "Brillante",
                "speciesId": 263,
                "species": "Zigzagoon",
                "shiny": True,
                "metLocation": "Ruta 102",
                "caughtAt": "x",
            }
        ],
        "starter_assigned": True,
    }

    result = service.assign_special_origin("Brillante", "shiny")

    assert result["encounters"][0]["location"] == "Ruta 102"

    print(
        "OK - una ruta real que en realidad está libre se usa "
        "directo, sin sufijo"
    )


def test_especial_con_ruta_real_y_sufijo_tambien_tomado():
    """
    Dos capturas especiales distintas colisionando con la MISMA
    ruta real -- la segunda no puede usar tampoco "Ruta (Especial)"
    porque ya la usó la primera. Se suma el nickname para
    garantizar unicidad.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [
            {
                "location": "Ruta 101",
                "nickname": "Zig1",
                "species": "Zigzagoon",
                "status": "capturado",
                "origin": None,
                "updatedAt": "x",
            }
        ],
        "pending_encounters": [
            {
                "nickname": "Brillante",
                "speciesId": 263,
                "species": "Zigzagoon",
                "shiny": True,
                "metLocation": "Ruta 101",
                "caughtAt": "x",
            },
            {
                "nickname": "OtroShiny",
                "speciesId": 261,
                "species": "Poochyena",
                "shiny": True,
                "metLocation": "Ruta 101",
                "caughtAt": "x",
            },
        ],
        "starter_assigned": True,
    }

    service.assign_special_origin("Brillante", "shiny")
    result = service.assign_special_origin("OtroShiny", "shiny")

    locations = {e["location"] for e in result["encounters"]}

    assert locations == {
        "Ruta 101",
        "Ruta 101 (Especial)",
        "Ruta 101 (Especial) - OtroShiny",
    }

    print(
        "OK - una tercera colisión en la misma ruta real usa el "
        "nickname para garantizar unicidad"
    )


def test_especial_con_ruta_real_guarda_anchor_location():
    """
    Cuando hay ruta real conocida, el encuentro guarda esa ruta
    en `anchorLocation` (sin el sufijo "(Especial)") -- es lo que
    el panel usa para ubicar la fila justo debajo de la ruta real,
    sin tener que parsear el texto de `location`.
    """
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [
            {
                "location": "Ruta 101",
                "nickname": "Zig1",
                "species": "Zigzagoon",
                "status": "capturado",
                "origin": None,
                "anchorLocation": None,
                "updatedAt": "x",
            }
        ],
        "pending_encounters": [
            {
                "nickname": "Brillante",
                "speciesId": 263,
                "species": "Zigzagoon",
                "shiny": True,
                "metLocation": "Ruta 101",
                "caughtAt": "x",
            }
        ],
        "starter_assigned": True,
    }

    result = service.assign_special_origin("Brillante", "shiny")

    special = next(
        e for e in result["encounters"]
        if e["nickname"] == "Brillante"
    )

    assert special["location"] == "Ruta 101 (Especial)"
    assert special["anchorLocation"] == "Ruta 101"

    print(
        "OK - un especial con ruta real conocida guarda esa ruta "
        "en anchorLocation"
    )


def test_especial_sin_ruta_real_no_tiene_anchor_location():
    service = NuzlockeService(FakeStorage())

    service._data = {
        "roster": [],
        "graveyard": [],
        "encounters": [],
        "pending_encounters": [
            {
                "nickname": "Huevito",
                "speciesId": 175,
                "species": "Togepi",
                "shiny": False,
                "metLocation": None,
                "caughtAt": "x",
            }
        ],
        "starter_assigned": True,
    }

    result = service.assign_special_origin("Huevito", "huevo")

    assert result["encounters"][0]["anchorLocation"] is None

    print(
        "OK - un especial sin ruta real conocida no tiene "
        "anchorLocation"
    )


if __name__ == "__main__":
    test_shiny_con_ruta_conocida_registra_especial_directo()
    test_pendiente_guarda_metlocation_para_mostrar_en_el_panel()
    test_huevo_sin_ruta_pendiente_con_metlocation_none()
    test_assign_special_origin_pseudo_ubicacion_unica_por_pokemon()
    test_assign_special_origin_rechaza_origen_invalido()
    test_save_encounter_conserva_origen_al_editar_sin_mandarlo()
    test_save_encounter_rechaza_especial_sin_origen_en_fila_nueva()
    test_especial_con_ruta_real_tomada_usa_sufijo_sin_pisar()
    test_especial_con_ruta_real_libre_la_usa_directo()
    test_especial_con_ruta_real_y_sufijo_tambien_tomado()
    test_especial_con_ruta_real_guarda_anchor_location()
    test_especial_sin_ruta_real_no_tiene_anchor_location()

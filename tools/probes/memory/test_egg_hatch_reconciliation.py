"""
Reproduce y valida el fix del 28/08/2026 para Pokémon nacidos de
un huevo, en dos etapas:

1. (Fix inicial) Se triplicaba en data/nuzlocke.json -- una
   entrada de roster/encuentro distinta por cada nickname que el
   juego le va dando con el tiempo (Huevo -> nombre por defecto ->
   nickname real). Resuelto con
   NuzlockeService._reconcile_pending_rename().

2. (Este fix, a pedido del usuario tras probar el primero) Aun sin
   triplicarse, el huevo SIN NACER todavía se contaba como una
   captura -- entraba a pending_encounters apenas se lo recibía,
   antes de eclosionar. Ahora se ignora por completo mientras el
   nickname siga siendo "Huevo": no se agrega a roster, no genera
   ningún encuentro/pendiente. Recién se registra como captura
   nueva cuando nace (nickname pasa al nombre por defecto de la
   especie).
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


def _team_with(*slots):
    padded = list(slots) + [
        {"slot": i, "empty": True}
        for i in range(len(slots) + 1, 7)
    ]
    return padded


def _new_service_with_egg_ignored():

    service = NuzlockeService(FakeStorage())

    starter = {
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
    }

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
    }

    # Mientras siga siendo "Huevo" -- ni en varios ciclos seguidos
    # -- no debe aparecer en roster ni en ningún encuentro.
    for _ in range(3):
        state = service.update(_team_with(starter, egg))
        assert len(state["roster"]) == 1
        assert state["roster"][0]["nickname"] == "Rocío"
        assert all(
            e["species"] != "Togepi"
            for e in state.get("encounters", [])
        )
        assert all(
            p["species"] != "Togepi"
            for p in state.get("pending_encounters", [])
        )

    return service, starter, egg


def test_huevo_sin_nacer_no_cuenta_para_nada():

    _new_service_with_egg_ignored()

    print(
        "OK - un huevo sin nacer no se registra en roster ni en "
        "ningún encuentro/pendiente, ni siquiera tras varios "
        "ciclos"
    )


def test_huevo_se_registra_recien_al_nacer_y_no_se_duplica():

    service, starter, egg = _new_service_with_egg_ignored()

    # Nace: el mismo slot pasa a tener el nombre por defecto de
    # la especie -- recién ahora se registra como captura nueva.
    hatched = {
        **egg,
        "nickname": "Togepi",
    }

    state = service.update(_team_with(starter, hatched))

    assert len(state["roster"]) == 2

    togepi_entries = [
        entry
        for entry in state["roster"]
        if entry["speciesId"] == 175
    ]
    assert len(togepi_entries) == 1
    assert togepi_entries[0]["nickname"] == "Togepi"
    assert togepi_entries[0]["level"] == 1

    # El jugador confirma el nickname real -- para cuando cierra
    # el diálogo, ya subió de nivel caminando (1 -> 6), como en el
    # reporte real.
    named = {
        **egg,
        "nickname": "AA",
        "level": 6,
    }

    state = service.update(_team_with(starter, named))

    assert len(state["roster"]) == 2

    final_entries = [
        entry
        for entry in state["roster"]
        if entry["speciesId"] == 175
    ]
    assert len(final_entries) == 1
    assert final_entries[0]["nickname"] == "AA"
    assert final_entries[0]["level"] == 6
    assert final_entries[0]["species"] == "Togepi"

    all_records = (
        state.get("encounters", [])
        + state.get("pending_encounters", [])
    )

    togepi_records = [
        record
        for record in all_records
        if record.get("speciesId") == 175
        or record.get("species") == "Togepi"
    ]

    # Un solo registro (no dos, no tres), y con el nickname final.
    assert len(togepi_records) == 1
    assert togepi_records[0]["nickname"] == "AA"

    # Ciclos siguientes con el mismo nickname: estable, sin
    # duplicar nada.
    for _ in range(3):
        state = service.update(_team_with(starter, named))
        assert len(state["roster"]) == 2

    print(
        "OK - recién nace y se registra como captura nueva (no "
        "antes) -- y no se duplica al pasar de nombre por "
        "defecto a nickname real"
    )


def test_segundo_huevo_sin_nacer_no_se_confunde_con_el_primero_ya_nacido():
    """
    Un segundo huevo de la MISMA especie, todavía sin nacer,
    coexistiendo con un Pokémon de esa especie que ya nació y
    tiene nombre por defecto -- el huevo sigue sin contar para
    nada (se ignora por completo mientras sea "Huevo"), y no debe
    confundirse ni fusionarse con el que ya nació.
    """

    service = NuzlockeService(FakeStorage())

    egg_a = {
        "slot": 1,
        "empty": False,
        "nickname": "Huevo",
        "species": "Togepi",
        "speciesId": 175,
        "level": 1,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(egg_a))

    hatched_a = {
        **egg_a,
        "nickname": "Togepi",
    }

    state = service.update(_team_with(hatched_a))
    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Togepi"

    egg_b = {
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
    }

    state = service.update(_team_with(hatched_a, egg_b))

    # egg_b sigue siendo "Huevo" -- se ignora, no aparece en
    # roster, y no se fusiona con hatched_a.
    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Togepi"

    print(
        "OK - un segundo huevo sin nacer de la misma especie no "
        "se confunde con el que ya nació (se ignora hasta que "
        "también nazca)"
    )


def test_huevo_guardado_en_la_caja_pc_tampoco_cuenta():
    """
    Bug real reportado el 28/08/2026 (segunda vuelta): el chequeo
    de "todavía es huevo, no cuenta" solo se había agregado al
    loop de party -- el loop de Caja PC (boxed_party, cuando el
    jugador guarda el huevo ahí en vez de llevarlo en la party) es
    un camino separado y no lo tenía, así que un huevo guardado en
    la caja SÍ se registraba como captura.
    """

    service = NuzlockeService(FakeStorage())

    starter = {
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
    }

    boxed_egg = {
        "slot": 1,
        "empty": False,
        "nickname": "Huevo",
        "species": "Togepi",
        "speciesId": 175,
        "level": 1,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "",
    }

    # El huevo está en la CAJA, no en la party -- se pasa como
    # boxed_party, no como parte del team.
    state = service.update(
        _team_with(starter),
        boxed_party=[boxed_egg],
    )

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Rocío"

    print(
        "OK - un huevo guardado en la Caja PC tampoco cuenta "
        "como captura mientras siga sin nacer"
    )


def test_huevo_nacido_se_autoregistra_con_entregado_por():
    """
    Bug/mejora del 28/08/2026: un huevo ya nacido usa "Entregado
    por" (eggLocation) como pseudo-ubicación en vez de caer a
    pending_encounters para asignar a mano en "¿Pokémon Especial?".

    IMPORTANTE (encontrado probando en el juego real, 28/08/2026):
    una vez que el huevo nace, el juego SÍ le asigna una ruta real
    a metLocation (la ruta donde eclosionó) -- por eso este test
    simula ese caso con metLocation TAMBIÉN resuelto, y confirma
    que eggLocation tiene prioridad de todas formas (huevo no debe
    tratarse como una captura salvaje normal en su ruta de
    eclosión, aunque el dato exista).
    """

    service = NuzlockeService(FakeStorage())

    starter = {
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
        # Ruta donde eclosionó -- SÍ viene resuelta por el juego,
        # a propósito en este test, para probar que no gana.
        "metLocation": "Ruta 110",
        "eggLocation": "Anciana del Balneario",
    }

    state = service.update(_team_with(starter, hatched))

    encounters = state.get("encounters", [])

    togepi_encounter = next(
        (
            e for e in encounters
            if e["nickname"] == "Togepi"
        ),
        None,
    )

    assert togepi_encounter is not None
    assert (
        togepi_encounter["location"] == "Anciana del Balneario"
    )
    assert togepi_encounter["status"] == "especial"
    assert togepi_encounter.get("origin") == "huevo"

    # No debe haber quedado registrado como una captura normal en
    # "Ruta 110" -- eggLocation le gana a metLocation.
    assert all(
        e["location"] != "Ruta 110" for e in encounters
    )

    # No debe haber quedado nada pendiente -- se auto-registró.
    assert state.get("pending_encounters", []) == []

    print(
        "OK - un huevo ya nacido se auto-registra usando "
        "'Entregado por' como pseudo-ubicación (con prioridad "
        "sobre la ruta de eclosión), sin pasar por pendientes"
    )


def test_captura_salvaje_normal_sigue_usando_met_location():
    """
    Una captura salvaje NORMAL (nunca fue huevo, eggLocation vacío)
    tiene que seguir usando metLocation como siempre -- el cambio
    de prioridad del 28/08/2026 no debe afectar el flujo estándar.
    """

    service = NuzlockeService(FakeStorage())

    starter = {
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

    state = service.update(_team_with(starter, wild_catch))

    encounters = state["encounters"]

    zigzagoon_encounter = next(
        e for e in encounters if e["nickname"] == "Zigzagoon"
    )

    assert zigzagoon_encounter["location"] == "Ruta 101"
    assert zigzagoon_encounter["status"] == "capturado"
    assert zigzagoon_encounter.get("origin") is None

    print(
        "OK - una captura salvaje normal (sin eggLocation) sigue "
        "usando metLocation, sin verse afectada por el cambio"
    )


def test_segundo_huevo_del_mismo_origen_se_diferencia_con_nickname():
    """
    Dos huevos entregados por la MISMA persona (mismo texto de
    'Entregado por') -- el primero se registra tal cual (sin
    agregarle nada, preferencia explícita del usuario), y recién
    el segundo, al chocar con esa ubicación ya tomada, se le
    agrega el nickname para diferenciarlo.
    """

    service = NuzlockeService(FakeStorage())

    starter = {
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

    hatched_a = {
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
        "eggLocation": "Anciana del Balneario",
    }

    state = service.update(_team_with(starter, hatched_a))

    encounters = state["encounters"]
    assert len(encounters) == 2  # Inicial + Togepi

    togepi_a = next(
        e for e in encounters if e["nickname"] == "Togepi"
    )
    assert togepi_a["location"] == "Anciana del Balneario"

    # Segundo huevo, mismo origen, especie distinta para que la
    # species clause no lo bloquee -- nace como "Igglybuff" (por
    # decir alguna) del mismo "Entregado por".
    hatched_b = {
        "slot": 3,
        "empty": False,
        "nickname": "Igglybuff",
        "species": "Igglybuff",
        "speciesId": 174,
        "level": 1,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "",
        "eggLocation": "Anciana del Balneario",
    }

    state = service.update(
        _team_with(starter, hatched_a, hatched_b)
    )

    encounters = state["encounters"]
    igglybuff = next(
        e for e in encounters if e["nickname"] == "Igglybuff"
    )

    assert (
        igglybuff["location"]
        == "Anciana del Balneario (Igglybuff)"
    )

    # El primero no se tocó.
    togepi_a = next(
        e for e in encounters if e["nickname"] == "Togepi"
    )
    assert togepi_a["location"] == "Anciana del Balneario"

    assert state.get("pending_encounters", []) == []

    print(
        "OK - el segundo huevo del mismo origen se diferencia "
        "con el nickname, el primero queda sin modificar"
    )


if __name__ == "__main__":
    test_huevo_sin_nacer_no_cuenta_para_nada()
    test_huevo_se_registra_recien_al_nacer_y_no_se_duplica()
    test_segundo_huevo_sin_nacer_no_se_confunde_con_el_primero_ya_nacido()
    test_huevo_guardado_en_la_caja_pc_tampoco_cuenta()
    test_huevo_nacido_se_autoregistra_con_entregado_por()
    test_captura_salvaje_normal_sigue_usando_met_location()
    test_segundo_huevo_del_mismo_origen_se_diferencia_con_nickname()

"""
Bloque 4.4 (guía siguiente versión, 23/09/2026): el desafío de un
Nuzlocke empieza cuando el jugador consigue sus primeras Poké
Balls, no antes. Mientras `nuzlocke_started` sea False,
NuzlockeService.update() no registra nada (ni capturas ni
muertes).

Confirmado en vivo por Ronald el 23/09/2026 con
investigar_bolsillo_pokeballs.py: las Poké Balls no tienen un
bolsillo propio, viven mezcladas dentro del bolsillo general de
Objetos -- item_id 4 (Poké Ball), 3 (Super Ball) y 12 (Premier
Ball) confirmados contra una partida real.
"""

from app.services.nuzlocke_service import NuzlockeService
from app.services.nuzlocke_storage import NuzlockeStorage


class FreshFakeStorage:
    """
    Simula una partida NUEVA (archivo todavía no creado) -- mismo
    criterio que NuzlockeStorage.load() cuando el archivo no
    existe: nuzlocke_started arranca en False.
    """

    def __init__(self):
        self.saved = None

    def load(self):
        return {
            "roster": [],
            "graveyard": [],
            "encounters": [],
            "pending_encounters": [],
            "starter_assigned": False,
            "nuzlocke_started": False,
        }

    def save(self, data):
        self.saved = data

    def backup(self):
        pass


class ExistingFakeStorage:
    """
    Simula una partida YA EN CURSO de antes de que existiera este
    flag -- sin la clave `nuzlocke_started` en absoluto (como
    NuzlockeStorage.load() la devolvería para un archivo real
    viejo, antes del setdefault a True).
    """

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

    def backup(self):
        pass


def _mon(nickname, species, species_id, level, hp=50, met_location="Ruta 101"):
    return {
        "slot": 1,
        "empty": False,
        "nickname": nickname,
        "species": species,
        "speciesId": species_id,
        "level": level,
        "hp": hp,
        "maxHp": max(hp, 1),
        "shiny": False,
        "metLocation": met_location,
        "genderId": 0,
    }


def _team(*mons):
    filled = list(mons)
    while len(filled) < 6:
        filled.append({"slot": len(filled) + 1, "empty": True})
    return filled


def test_partida_nueva_registra_solo_el_inicial_sin_pokeballs():
    # 03/10/2026: el inicial se registra apenas se obtiene; la
    # cláusula de las Poké Balls solo gatea todo lo demás.
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, met_location="")
    state = service.update(_team(boti), has_pokeballs=False)

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Boti"
    assert len(state["encounters"]) == 1
    assert state["encounters"][0]["location"] == "Inicial"
    assert state.get("nuzlocke_started") is False


def test_sin_pokeballs_lo_demas_no_se_registra():
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, met_location="")
    service.update(_team(boti), has_pokeballs=False)

    # Un segundo Pokémon (party o Caja) antes de las Poké Balls
    # NO se registra.
    segundo = _mon("Rocko", "Geodude", 74, 4, met_location="Ruta 102")
    segundo["slot"] = 2
    caja = _mon("Cajon", "Zigzagoon", 263, 3, met_location="Ruta 101")
    team = _team(boti, segundo)
    state = service.update(team, boxed_party=[caja], has_pokeballs=False)

    assert [e["nickname"] for e in state["roster"]] == ["Boti"]
    assert len(state["encounters"]) == 1

    # Con Poké Balls, ahora sí.
    state = service.update(team, boxed_party=[caja], has_pokeballs=True)
    assert {e["nickname"] for e in state["roster"]} == {
        "Boti", "Rocko", "Cajon",
    }
    assert state["nuzlocke_started"] is True


def test_inicial_renombrado_antes_de_las_pokeballs_no_se_duplica():
    service = NuzlockeService(FreshFakeStorage())

    # Nombre por defecto de la especie, y luego el que elige el
    # jugador en el laboratorio.
    service.update(
        _team(_mon("Torchic", "Torchic", 255, 5, met_location="")),
        has_pokeballs=False,
    )
    state = service.update(
        _team(_mon("Boti", "Torchic", 255, 5, met_location="")),
        has_pokeballs=False,
    )

    assert [e["nickname"] for e in state["roster"]] == ["Boti"]
    assert len(state["encounters"]) == 1
    assert state["encounters"][0]["nickname"] == "Boti"
    assert state["encounters"][0]["location"] == "Inicial"


def test_muerte_del_inicial_no_se_registra_antes_de_las_pokeballs():
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, hp=0, met_location="")
    state = service.update(_team(boti), has_pokeballs=False)

    assert state["graveyard"] == []
    assert len(state["roster"]) == 1


def test_partida_nueva_registra_todo_una_vez_que_hay_pokeballs():
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, met_location="")

    # Dos ciclos sin Poké Balls todavía -- el inicial ya se
    # registró (una sola vez, sin duplicarse).
    service.update(_team(boti), has_pokeballs=False)
    state = service.update(_team(boti), has_pokeballs=False)
    assert len(state["roster"]) == 1
    assert state.get("nuzlocke_started") is False

    # Ahora sí tiene Poké Balls -- el tracking completo arranca.
    state = service.update(_team(boti), has_pokeballs=True)

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Boti"
    assert len(state["encounters"]) == 1
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["nuzlocke_started"] is True


def test_una_vez_iniciado_queda_asi_aunque_has_pokeballs_vuelva_a_false():
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, met_location="")
    service.update(_team(boti), has_pokeballs=True)

    # El jugador gastó/perdió todas sus Poké Balls más adelante --
    # nuzlocke_started NO vuelve a False, sigue registrando normal.
    segundo = _mon("Rocko", "Geodude", 74, 4, met_location="Ruta 102")
    state = service.update(_team(boti, segundo), has_pokeballs=False)

    assert len(state["roster"]) == 2
    assert state["nuzlocke_started"] is True


def test_lectura_fallida_de_la_bolsa_no_arranca_el_tracking():
    # has_pokeballs=None (lectura de memoria fallida, ver
    # AzaharReader.read_has_pokeballs()) se trata igual que False
    # -- nunca arrancar el tracking por una lectura fallida (el
    # inicial se registra igual, no depende de la bolsa).
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, met_location="")
    state = service.update(_team(boti), has_pokeballs=None)

    assert len(state["roster"]) == 1
    assert state.get("nuzlocke_started") is False


def test_partida_ya_en_curso_sin_la_clave_no_se_bloquea_retroactivo():
    # Bloque 4.4: una partida que ya se venía trackeando antes de
    # este flag no debe bloquearse de golpe -- FreshFakeStorage vs
    # ExistingFakeStorage es justo esa diferencia (ver
    # NuzlockeStorage.load() real, que hace lo mismo con
    # path.exists()).
    service = NuzlockeService(ExistingFakeStorage())

    nuevo = _mon("Segundo", "Zigzagoon", 263, 10, met_location="Ruta 103")

    # NI SIQUIERA hace falta pasar has_pokeballs=True -- una
    # partida ya en curso arranca ya considerada iniciada.
    state = service.update(_team(nuevo), has_pokeballs=None)

    assert len(state["roster"]) == 1
    assert state["roster"][0]["nickname"] == "Segundo"


def test_nuzlocke_storage_real_archivo_nuevo_arranca_sin_iniciar(tmp_path):
    storage = NuzlockeStorage(tmp_path / "nuzlocke_omega_ruby.json")

    data = storage.load()

    assert data["nuzlocke_started"] is False


def test_nuzlocke_storage_real_archivo_existente_arranca_iniciado(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)

    # Simula un archivo real guardado ANTES de que existiera este
    # flag (sin la clave nuzlocke_started).
    storage.save({"roster": [], "graveyard": []})

    data = storage.load()

    assert data["nuzlocke_started"] is True


def test_reiniciar_partida_vuelve_a_exigir_pokeballs():
    # Bug real reportado por Ronald (23/09/2026): reset_all()
    # armaba self._data a mano, sin pasar por NuzlockeStorage.load()
    # -- sin la clave nuzlocke_started explícita ahí, el
    # setdefault(..., True) de update() la marcaba como "ya
    # iniciada" de nuevo al instante, y "Reiniciar partida" dejaba
    # de servir para probar el inicio real del Nuzlocke.
    service = NuzlockeService(ExistingFakeStorage())

    viejo = _mon("Viejo", "Torchic", 255, 20, met_location="")
    service.update(_team(viejo), has_pokeballs=None)
    assert len(service._data["roster"]) == 1  # ya estaba iniciada

    service.reset_all()
    assert service._data["nuzlocke_started"] is False

    nuevo = _mon("Nuevo", "Mudkip", 258, 5, met_location="")
    state = service.update(_team(nuevo), has_pokeballs=False)

    # Solo el inicial; el tracking completo espera a las Balls.
    assert [e["nickname"] for e in state["roster"]] == ["Nuevo"]
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["nuzlocke_started"] is False

    state = service.update(_team(nuevo), has_pokeballs=True)
    assert len(state["roster"]) == 1
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["nuzlocke_started"] is True


def test_register_lost_encounter_no_registra_nada_sin_pokeballs():
    # Bug real reportado por Ronald (23/09/2026): la detección de
    # "perdido" es un camino de Runtime totalmente aparte de
    # update() (Runtime._update_lost_encounter_tracking()/
    # _resolve_pending_lost_encounter() llaman a
    # register_lost_encounter() DIRECTO) -- el gateo de
    # nuzlocke_started dentro de update() no lo alcanzaba para
    # nada, así que "perdidos" se seguían registrando desde el
    # arranque aunque el resto (capturas/muertes) ya estuviera bien
    # gateado.
    service = NuzlockeService(FreshFakeStorage())

    result = service.register_lost_encounter("Ruta 101", "Zigzagoon")

    assert result == []
    assert service._data["encounters"] == []


def test_register_lost_encounter_funciona_normal_una_vez_iniciado():
    service = NuzlockeService(FreshFakeStorage())

    boti = _mon("Boti", "Torchic", 255, 5, met_location="")
    service.update(_team(boti), has_pokeballs=True)

    result = service.register_lost_encounter("Ruta 101", "Zigzagoon")

    assert len(result) == 2  # Inicial + el perdido
    perdido = next(e for e in result if e["location"] == "Ruta 101")
    assert perdido["status"] == "perdido"


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    test_partida_nueva_registra_solo_el_inicial_sin_pokeballs()
    test_sin_pokeballs_lo_demas_no_se_registra()
    test_inicial_renombrado_antes_de_las_pokeballs_no_se_duplica()
    test_muerte_del_inicial_no_se_registra_antes_de_las_pokeballs()
    test_partida_nueva_registra_todo_una_vez_que_hay_pokeballs()
    test_una_vez_iniciado_queda_asi_aunque_has_pokeballs_vuelva_a_false()
    test_lectura_fallida_de_la_bolsa_no_arranca_el_tracking()
    test_partida_ya_en_curso_sin_la_clave_no_se_bloquea_retroactivo()
    test_reiniciar_partida_vuelve_a_exigir_pokeballs()
    test_register_lost_encounter_no_registra_nada_sin_pokeballs()
    test_register_lost_encounter_funciona_normal_una_vez_iniciado()

    with tempfile.TemporaryDirectory() as base:
        test_nuzlocke_storage_real_archivo_nuevo_arranca_sin_iniciar(Path(base))
    with tempfile.TemporaryDirectory() as base:
        test_nuzlocke_storage_real_archivo_existente_arranca_iniciado(Path(base))

    print("OK - todos los tests del inicio real del Nuzlocke pasaron")

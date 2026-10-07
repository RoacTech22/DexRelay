"""
P3 (paridad X/Y, 06/10/2026): las señales de reglas especiales del
Nuzlocke que dependen del juego salen del perfil, sin cambiar ORAS.

Señales por juego: el fósil (ORAS: Devon Corp = 190, basta el lugar; Kalos:
Pueblo Petroglifo = 44 + una baja reciente de fósiles en la bolsa, sin
depender de la especie para que sirva en randomlocke, con pseudo-lugar
"Fósil"; medido en vivo con tools/probes/xy/origenes_xy.py y
fosil_bolsa_xy.py el 06/10/2026). El intercambio con un NPC se detecta
además por ID (30001), porque en Y PKHeX lo devuelve en español. Las demás
reglas (inicial, huevo, shiny) usan señales genéricas.
"""

from types import SimpleNamespace

from app.games.base import GameContent, SpecialRules
from app.games.oras.profile import ALPHA_SAPPHIRE, OMEGA_RUBY
from app.games.xy.profile import POKEMON_X, POKEMON_Y
from app.services.nuzlocke_service import (
    DEVON_CORP_LOCATION_ID,
    FOSSIL_DROP_WINDOW_SECONDS,
    NuzlockeService,
)

from app.core.runtime import Runtime
from tests.test_kalos_zone_names import _FakeNuzlocke, _make_runtime
from tests.test_nuzlocke_core import FakeStorage, _mon, _team


def _fossil(met_location_id=190, met_location="Ciudad Férrica"):
    mon = _mon(2, "Rex", "Lileep", 345, 20, met_location=met_location)
    mon["metLocationId"] = met_location_id
    return mon


def _service_with_starter(profile_provider="legacy"):
    if profile_provider == "legacy":
        service = NuzlockeService(FakeStorage())
    else:
        service = NuzlockeService(
            FakeStorage(), profile_provider=profile_provider
        )

    service.update(_team(_mon(1, "Boti", "Torchic", 255, 5, met_location="")))

    return service


def _encounter(state, nickname):
    return next(e for e in state["encounters"] if e["nickname"] == nickname)


def test_perfiles_de_oras_traen_devon_corp_como_lugar_de_fosil():
    for profile in (ALPHA_SAPPHIRE, OMEGA_RUBY):
        rules = profile.content.special_rules

        assert rules.fossil_location_ids == frozenset({190})

    assert DEVON_CORP_LOCATION_ID == 190


def test_perfiles_de_oras_no_piden_objetos_ni_pseudo_lugar_para_el_fosil():
    for profile in (ALPHA_SAPPHIRE, OMEGA_RUBY):
        rules = profile.content.special_rules

        assert rules.fossil_item_ids == frozenset()
        assert rules.fossil_pseudo_location == ""


def test_perfiles_de_xy_traen_la_senal_de_fosil_medida_en_vivo():
    for profile in (POKEMON_X, POKEMON_Y):
        rules = profile.content.special_rules

        assert rules.fossil_location_ids == frozenset({44})
        assert rules.fossil_pseudo_location == "Fósil"
        # IDs de la tabla de objetos de PKHeX; 100 y 710 medidos en vivo.
        assert {100, 710} <= rules.fossil_item_ids
        assert rules.fossil_item_ids == frozenset(
            {99, 100, 101, 102, 103, 104, 105, 572, 573, 710, 711}
        )


def test_defaults_de_special_rules_y_game_content_son_conservadores():
    assert SpecialRules().fossil_location_ids == frozenset()
    assert GameContent().special_rules == SpecialRules()


def test_sin_perfil_el_servicio_conserva_el_comportamiento_historico_de_hoenn():
    service = _service_with_starter()

    state = service.update(_team(
        _mon(1, "Boti", "Torchic", 255, 5, met_location=""), _fossil(),
    ))
    rex = _encounter(state, "Rex")

    assert rex["location"] == "Ciudad Férrica"
    assert rex["status"] == "especial"
    assert rex["origin"] == "fosil"


def test_con_perfil_de_oras_el_lugar_de_fosil_sigue_marcando_fosil():
    service = _service_with_starter(lambda: ALPHA_SAPPHIRE)

    state = service.update(_team(
        _mon(1, "Boti", "Torchic", 255, 5, met_location=""), _fossil(),
    ))

    assert _encounter(state, "Rex")["origin"] == "fosil"


def test_con_perfil_de_xy_el_id_190_ya_no_es_un_fosil():
    service = _service_with_starter(lambda: POKEMON_Y)

    state = service.update(_team(
        _mon(1, "Chespin", "Chespin", 650, 5, met_location=""), _fossil(),
    ))
    rex = _encounter(state, "Rex")

    assert rex["status"] == "capturado"
    assert rex.get("origin") in (None, "")


def test_juego_sin_perfil_apaga_la_senal_en_vez_de_caer_a_hoenn():
    service = _service_with_starter(lambda: None)

    state = service.update(_team(
        _mon(1, "Boti", "Torchic", 255, 5, met_location=""), _fossil(),
    ))

    assert _encounter(state, "Rex")["status"] == "capturado"


def test_un_perfil_con_ids_propios_los_usa():
    # Cuando se confirme la señal de Kalos entrará como datos del perfil,
    # sin tocar el servicio.
    kalos = SimpleNamespace(
        content=SimpleNamespace(
            special_rules=SpecialRules(fossil_location_ids=frozenset({106}))
        )
    )
    service = _service_with_starter(lambda: kalos)

    state = service.update(_team(
        _mon(1, "Chespin", "Chespin", 650, 5, met_location=""),
        _fossil(met_location_id=106, met_location="Pueblo Petroglifo"),
    ))
    rex = _encounter(state, "Rex")

    assert rex["location"] == "Pueblo Petroglifo"
    assert rex["origin"] == "fosil"


# ---------------------------------------------------------------
# Kalos: fósil (lugar 44 + baja de fósiles en la bolsa) e intercambio por ID
# ---------------------------------------------------------------

class _Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _kalos(nickname, species, species_id, met_id, met_name, slot=2, level=20):
    mon = _mon(slot, nickname, species, species_id, level, met_location=met_name)
    mon["metLocationId"] = met_id
    return mon


def _chespin():
    return _mon(1, "Chespin", "Chespin", 650, 5, met_location="")


def _y_service(reloj=None):
    service = NuzlockeService(
        FakeStorage(),
        profile_provider=lambda: POKEMON_Y,
        clock=reloj or _Reloj(),
    )
    service.update(_team(_chespin()), fossil_count=5)
    return service


def test_kalos_fosil_revivido_se_registra_como_fosil_en_su_propio_lugar():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=4)   # la bolsa baja...
    reloj.t += 14                                        # ...y 14 s después sale el Pokémon
    state = service.update(_team(
        _chespin(), _kalos("Tyrunt", "Tyrunt", 696, 44, "Pueblo Petroglifo"),
    ), fossil_count=4)
    tyrunt = _encounter(state, "Tyrunt")

    assert tyrunt["location"] == "Fósil"
    assert tyrunt["status"] == "especial"
    assert tyrunt["origin"] == "fosil"
    # La fila de la ruta queda libre para una captura salvaje.
    assert not any(e["location"] == "Pueblo Petroglifo" for e in state["encounters"])


def test_kalos_randomlocke_la_especie_no_importa():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=4)
    reloj.t += 14
    state = service.update(_team(
        _chespin(), _kalos("Pika", "Pikachu", 25, 44, "Pueblo Petroglifo"),
    ), fossil_count=4)

    assert _encounter(state, "Pika")["origin"] == "fosil"
    assert _encounter(state, "Pika")["location"] == "Fósil"


def test_kalos_pesca_salvaje_en_petroglifo_no_es_fosil_y_ocupa_la_ruta():
    # Reproduce lo medido: el Dragalge pescado trajo el MISMO lugar 44 y la
    # bolsa solo bajó Poké Balls (no cambia la cantidad de fósiles).
    service = _y_service()

    service.update(_team(_chespin()), fossil_count=5)
    state = service.update(_team(
        _chespin(),
        _kalos("Dragalge", "Dragalge", 691, 44, "Pueblo Petroglifo", level=35),
    ), fossil_count=5)
    dragalge = _encounter(state, "Dragalge")

    assert dragalge["location"] == "Pueblo Petroglifo"
    assert dragalge["status"] == "capturado"
    assert dragalge.get("origin") in (None, "")


def test_kalos_cada_baja_se_usa_una_sola_vez():
    # Tyrunt consume la baja; el Dragalge pescado 99 s después (medido en
    # vivo) NO puede reutilizarla aunque aún quede cerca en el tiempo.
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=4)
    reloj.t += 15
    tyrunt = _kalos("Tyrunt", "Tyrunt", 696, 44, "Pueblo Petroglifo")
    service.update(_team(_chespin(), tyrunt), fossil_count=4)
    reloj.t += 5
    state = service.update(_team(
        _chespin(), tyrunt,
        _kalos("Dragalge", "Dragalge", 691, 44, "Pueblo Petroglifo", slot=3, level=35),
    ), fossil_count=4)

    assert _encounter(state, "Tyrunt")["location"] == "Fósil"
    assert _encounter(state, "Dragalge")["location"] == "Pueblo Petroglifo"
    assert state["pending_encounters"] == []


def test_kalos_una_baja_vieja_caduca():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=4)   # p. ej. vendió un fósil
    reloj.t += FOSSIL_DROP_WINDOW_SECONDS + 1
    state = service.update(_team(
        _chespin(),
        _kalos("Dragalge", "Dragalge", 691, 44, "Pueblo Petroglifo", level=35),
    ), fossil_count=4)

    assert _encounter(state, "Dragalge")["status"] == "capturado"


def test_kalos_la_baja_solo_vale_para_el_lugar_del_laboratorio():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=4)
    reloj.t += 5
    state = service.update(_team(
        _chespin(), _kalos("Zigzag", "Zigzagoon", 263, 62, "Ruta 12"),
    ), fossil_count=4)

    assert _encounter(state, "Zigzag")["status"] == "capturado"
    # Y la baja sigue disponible para el fósil de verdad.
    reloj.t += 5
    state = service.update(_team(
        _chespin(),
        _kalos("Zigzag", "Zigzagoon", 263, 62, "Ruta 12"),
        _kalos("Rex", "Anorith", 347, 44, "Pueblo Petroglifo", slot=3),
    ), fossil_count=4)
    assert _encounter(state, "Rex")["origin"] == "fosil"


def test_kalos_dos_fosiles_seguidos_dan_dos_pares():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=3)   # dos fósiles de golpe
    reloj.t += 14
    uno = _kalos("Uno", "Anorith", 347, 44, "Pueblo Petroglifo", slot=2)
    dos = _kalos("Dos", "Tyrunt", 696, 44, "Pueblo Petroglifo", slot=3)
    state = service.update(_team(_chespin(), uno, dos), fossil_count=3)

    assert _encounter(state, "Uno")["location"] == "Fósil"
    assert _encounter(state, "Dos")["location"] == "Fósil (Dos)"
    assert _encounter(state, "Dos")["origin"] == "fosil"


def test_kalos_una_lectura_fallida_no_inventa_bajas():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=None)  # lectura fallida
    state = service.update(_team(
        _chespin(),
        _kalos("Dragalge", "Dragalge", 691, 44, "Pueblo Petroglifo", level=35),
    ), fossil_count=5)

    assert _encounter(state, "Dragalge")["status"] == "capturado"


def test_oras_no_usa_la_bolsa_aunque_le_pasen_bajas():
    service = NuzlockeService(FakeStorage(), profile_provider=lambda: ALPHA_SAPPHIRE)
    service.update(_team(_mon(1, "Boti", "Torchic", 255, 5, met_location="")), fossil_count=5)

    # Un salvaje del lugar 190 sigue siendo fósil por lugar, sin baja...
    state = service.update(_team(
        _mon(1, "Boti", "Torchic", 255, 5, met_location=""), _fossil(),
    ), fossil_count=5)

    assert _encounter(state, "Rex")["origin"] == "fosil"


def test_kalos_intercambio_npc_se_detecta_por_id_aunque_el_texto_venga_en_espanol():
    service = _y_service()

    state = service.update(_team(
        _chespin(),
        _kalos("Sr. Puerró", "Farfetch'd", 83, 30001, "Intercambio (NPC)", level=10),
    ))
    puerro = _encounter(state, "Sr. Puerró")

    assert puerro["location"] == "Intercambiado"
    assert puerro["status"] == "especial"
    assert puerro["origin"] == "intercambio"


def test_intercambio_por_id_tambien_funciona_con_el_texto_en_ingles_de_oras():
    # El texto histórico sigue valiendo (probe test_trade_detection).
    assert NuzlockeService._is_trade_location("a Link Trade (NPC)") is True
    assert NuzlockeService._is_trade_location("Intercambio (NPC)", 30001) is True
    assert NuzlockeService._is_trade_location("Intercambio (NPC)") is False
    assert NuzlockeService._is_trade_location("Ruta 101", 170) is False
    assert NuzlockeService._is_trade_location(None, None) is False


# ---------------------------------------------------------------
# Runtime: lectura de la bolsa de fósiles
# ---------------------------------------------------------------

class _NuzlockeConFosiles(_FakeNuzlocke):
    def __init__(self):
        super().__init__()
        self.fossil_counts = []

    def update(self, party, boxed_party=None, has_pokeballs=None, fossil_count=None):
        self.fossil_counts.append(fossil_count)
        return {"roster": [], "graveyard": []}


def _runtime_con_reloj(profile):
    runtime, reader, _ = _make_runtime([], profile=profile)
    nuzlocke = _NuzlockeConFosiles()
    runtime.nuzlocke_service = nuzlocke
    reloj = _Reloj()
    runtime._time_source = reloj
    reader.fossil_reads = 0
    valores = iter([5, 5, 4, 4, 4, 4])

    def read_fossil_item_count():
        reader.fossil_reads += 1
        return next(valores)

    reader.read_fossil_item_count = read_fossil_item_count

    return runtime, reader, nuzlocke, reloj


def test_runtime_xy_pasa_la_cantidad_de_fosiles_cada_segundo_no_cada_ciclo():
    runtime, reader, nuzlocke, reloj = _runtime_con_reloj(POKEMON_X)

    for _ in range(4):          # 4 ciclos de 200 ms dentro del mismo segundo
        runtime.update()
        reloj.t += 0.2

    assert reader.fossil_reads == 1
    assert nuzlocke.fossil_counts == [5, None, None, None]

    reloj.t += Runtime.FOSSIL_SCAN_INTERVAL_SECONDS
    runtime.update()

    assert reader.fossil_reads == 2


def test_runtime_oras_no_lee_la_bolsa_de_fosiles():
    runtime, reader, nuzlocke, reloj = _runtime_con_reloj(ALPHA_SAPPHIRE)

    for _ in range(3):
        runtime.update()
        reloj.t += 2

    assert reader.fossil_reads == 0
    assert nuzlocke.fossil_counts == [None, None, None]


# ---------------------------------------------------------------
# Kalos: las filas especiales se anclan al lugar donde se obtuvieron
# ---------------------------------------------------------------

def test_kalos_fosil_se_ancla_al_lugar_donde_se_revivio():
    reloj = _Reloj()
    service = _y_service(reloj)

    service.update(_team(_chespin()), fossil_count=4)
    reloj.t += 14
    state = service.update(_team(
        _chespin(), _kalos("Tyrunt", "Tyrunt", 696, 44, "Pueblo Petroglifo"),
    ), fossil_count=4)

    assert _encounter(state, "Tyrunt")["anchorLocation"] == "Pueblo Petroglifo"


def test_oras_fosil_no_lleva_ancla_y_conserva_su_lugar():
    service = NuzlockeService(FakeStorage(), profile_provider=lambda: ALPHA_SAPPHIRE)
    service.update(_team(_mon(1, "Boti", "Torchic", 255, 5, met_location="")))

    state = service.update(_team(
        _mon(1, "Boti", "Torchic", 255, 5, met_location=""), _fossil(),
    ))
    rex = _encounter(state, "Rex")

    assert rex["location"] == "Ciudad Férrica"
    assert rex.get("anchorLocation") is None


def _trade_service(place, profile=POKEMON_Y):
    service = NuzlockeService(
        FakeStorage(),
        profile_provider=lambda: profile,
        place_provider=lambda: place,
    )
    service.update(_team(_chespin()))
    return service


def test_kalos_intercambio_se_ancla_al_lugar_actual():
    service = _trade_service("Ciudad Luminalia")

    state = service.update(_team(
        _chespin(),
        _kalos("Sr. Puerró", "Farfetch'd", 83, 30001, "Intercambio (NPC)", level=10),
    ))

    assert _encounter(state, "Sr. Puerró")["anchorLocation"] == "Ciudad Luminalia"


def test_kalos_intercambio_sin_zona_cae_a_la_ultima_ruta_registrada():
    service = _trade_service(None)

    service.update(_team(
        _chespin(), _kalos("Bunny", "Bunnelby", 659, 16, "Ruta 3", level=3),
    ))
    state = service.update(_team(
        _chespin(),
        _kalos("Bunny", "Bunnelby", 659, 16, "Ruta 3", level=3),
        _kalos("Sr. Puerró", "Farfetch'd", 83, 30001, "Intercambio (NPC)", slot=3, level=10),
    ))

    assert _encounter(state, "Sr. Puerró")["anchorLocation"] == "Ruta 3"


def test_oras_intercambio_se_ancla_al_lugar_actual_igual_que_xy():
    service = _trade_service("Ciudad Férrica", profile=ALPHA_SAPPHIRE)
    mon = _mon(2, "Trueque", "Zigzagoon", 263, 10, met_location="a Link Trade (NPC)")

    state = service.update(_team(_chespin(), mon))

    assert _encounter(state, "Trueque")["anchorLocation"] == "Ciudad Férrica"


def test_kalos_el_pokemon_que_se_va_por_intercambio_queda_marcado():
    # Reproduce lo medido en Y: el intercambiado ocupa el MISMO casillero
    # del que se fue, así que ambos cambios caen en el mismo ciclo.
    service = _trade_service("Ciudad Luminalia")
    bunny = _kalos("Bunny", "Bunnelby", 659, 16, "Ruta 3", level=3)

    service.update(_team(_chespin(), bunny))
    state = service.update(_team(
        _chespin(),
        _kalos("Sr. Puerró", "Farfetch'd", 83, 30001, "Intercambio (NPC)", level=10),
    ))

    assert _encounter(state, "Bunny")["tradedAway"] is True
    assert [e["nickname"] for e in state["traded_away"]] == ["Bunny"]
    assert [m["nickname"] for m in state["roster"]] == ["Chespin", "Sr. Puerró"]

"""
P2 (06/10/2026): zona de memoria -> lugar del catálogo de Kalos y
detección automática de "perdido" en X/Y.
"""

from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.games.xy.locations import (
    EXCLUDED_LOCATION_IDS,
    KALOS_ID_MAX,
    KALOS_ID_MIN,
)
from app.games.xy.profile import POKEMON_X, POKEMON_Y
from app.services.kalos_locations_es import KALOS_LOCATION_NAMES_ES
from app.services.kalos_zone_names import (
    KALOS_ZONE_TO_LOCATION_ID,
    resolve_zone_name,
)


def test_zonas_recolectadas_resuelven_al_nombre_del_catalogo():
    assert resolve_zone_name(259) == "Ruta 2"
    assert resolve_zone_name(268) == "Ruta 10"
    assert resolve_zone_name(270) == "Ruta 12"
    assert resolve_zone_name(285) == "Ruta 22"
    assert resolve_zone_name(286) == "Bosque de Novarte"
    assert resolve_zone_name(305) == "Cueva Reflejos"
    assert resolve_zone_name(38) == "Pueblo Mosaico"
    assert resolve_zone_name(302) == "Palacio Cénit"
    assert resolve_zone_name(349) == "Hotel Desolación"


def test_calle_victoria_tiene_tres_zonas():
    assert {resolve_zone_name(z) for z in (324, 326, 328)} == {
        "Calle Victoria"
    }


def test_zona_sin_mapear_o_sin_lectura_devuelve_none_sin_placeholder():
    assert resolve_zone_name(999) is None
    assert resolve_zone_name(258) is None  # cualquier zona aún no recolectada
    assert resolve_zone_name(None) is None


def test_lugar_excluido_del_catalogo_no_se_resuelve():
    # Un lugar excluido (Ruta 1, id 8) no tiene fila donde registrar.
    assert 8 in EXCLUDED_LOCATION_IDS
    KALOS_ZONE_TO_LOCATION_ID[99999] = 8
    try:
        assert resolve_zone_name(99999) is None
    finally:
        del KALOS_ZONE_TO_LOCATION_ID[99999]


def test_villa_pokemon_ya_es_parte_del_catalogo_y_se_resuelve():
    assert 98 not in EXCLUDED_LOCATION_IDS
    assert resolve_zone_name(318) == "Villa Pokémon"


def test_la_tabla_apunta_solo_a_ids_validos_de_kalos():
    for zone, location_id in KALOS_ZONE_TO_LOCATION_ID.items():
        assert KALOS_ID_MIN <= location_id <= KALOS_ID_MAX, zone
        assert location_id in KALOS_LOCATION_NAMES_ES, zone


def test_cada_nombre_resuelto_es_una_fila_del_catalogo_precargado():
    catalog_names = {
        name
        for location_id, name in KALOS_LOCATION_NAMES_ES.items()
        if location_id not in EXCLUDED_LOCATION_IDS
    }

    for zone in KALOS_ZONE_TO_LOCATION_ID:
        name = resolve_zone_name(zone)
        if name is not None:
            assert name in catalog_names, zone


def test_zonas_de_kalos_no_se_cruzan_con_hoenn():
    # Los ids de zona de ORAS tienen su tabla; la de Kalos es aparte.
    assert POKEMON_X.content.zone_name_resolver is resolve_zone_name
    assert POKEMON_Y.content.zone_name_resolver is resolve_zone_name


# ---- Runtime: detección de "perdido" con el perfil de X/Y ----

class _FakeReader:
    profile = POKEMON_X

    def __init__(self):
        self.memory = None
        self.zone_id = 259  # Ruta 2
        self.total_caught = 5

    def is_connected(self):
        return True

    def connect(self):
        return True

    def read_party(self):
        return [{"slot": i + 1, "empty": True} for i in range(6)]

    def read_boxes_range(self, start_box_index=1, box_count=7):
        return []

    def read_current_zone_id(self):
        return self.zone_id

    def read_total_caught_count(self):
        return self.total_caught

    def read_fossil_item_count(self):
        # X/Y declaran objetos de fósil (P3); este test no los usa.
        return None

    def read_wild_rival_species(self):
        return "Pidgey"

    def read_last_caught(self):
        return None


class _FakeNuzlocke:
    def __init__(self):
        self.lost_calls = []
        self.registered = set()

    def update(self, party, boxed_party=None, has_pokeballs=None):
        return {"roster": [], "graveyard": []}

    def is_started(self):
        return True

    def has_encounter_for_location(self, location):
        return location in self.registered

    def register_lost_encounter(self, location, species):
        self.lost_calls.append((location, species))
        self.registered.add(location)


def _make_runtime(flags, profile=POKEMON_X):
    reader = _FakeReader()
    reader.profile = profile
    nuzlocke = _FakeNuzlocke()
    runtime = Runtime(reader, ApplicationState(), nuzlocke_service=nuzlocke)
    runtime.badges_service.read_badges = lambda: {
        "value": 0,
        "count": 0,
        "badges": [False] * 8,
    }
    runtime.combat_service.read = lambda: None

    def _seq():
        yield from flags
        while True:
            yield None

    seq = _seq()
    runtime.combat_service.read_wild_flag = lambda: next(seq)

    return runtime, reader, nuzlocke


def _settle(runtime):
    for _ in range(Runtime.LOST_ENCOUNTER_MAX_RETRIES + 1):
        runtime.update()


def test_xy_combate_salvaje_sin_captura_en_zona_mapeada_registra_perdido():
    runtime, _reader, nuzlocke = _make_runtime([True, True, None])

    runtime.update()
    runtime.update()
    runtime.update()
    _settle(runtime)

    assert nuzlocke.lost_calls == [("Ruta 2", "Pidgey")]


def test_xy_funciona_igual_con_pokemon_y():
    runtime, _reader, nuzlocke = _make_runtime(
        [True, None], profile=POKEMON_Y
    )

    runtime.update()
    runtime.update()
    _settle(runtime)

    assert nuzlocke.lost_calls == [("Ruta 2", "Pidgey")]


def test_xy_zona_sin_mapear_no_registra_nada():
    runtime, reader, nuzlocke = _make_runtime([True, True, None])
    reader.zone_id = 999

    for _ in range(3):
        runtime.update()
    _settle(runtime)

    assert nuzlocke.lost_calls == []
    assert runtime._lost_encounter_snapshot is None


def test_xy_zona_que_se_vuelve_conocida_se_registra_al_reintentar():
    # Lectura transitoria de una zona de paso y luego la real.
    runtime, reader, nuzlocke = _make_runtime([True, True, True, None])
    reader.zone_id = 999

    runtime.update()
    assert runtime._lost_encounter_snapshot is None

    reader.zone_id = 260  # Ruta 3
    runtime.update()
    runtime.update()
    runtime.update()
    _settle(runtime)

    assert nuzlocke.lost_calls == [("Ruta 3", "Pidgey")]

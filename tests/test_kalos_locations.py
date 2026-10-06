"""
P1 (paridad X/Y): catálogo de ubicaciones de Kalos.

Datos de entrada = volcado real del bridge (05/10/2026): X e Y devuelven
la misma lista y Kalos son 82 IDs pares entre 2 y 168 (sin el 4 ni el 80).
"""

from app.games.oras.locations import HOENN_ID_MAX, HOENN_ID_MIN
from app.games.oras.profile import ALPHA_SAPPHIRE
from app.games.xy.locations import (
    EXCLUDED_LOCATION_IDS,
    KALOS_ID_MAX,
    KALOS_ID_MIN,
    STORY_ORDER_IDS,
)
from app.games.xy.profile import POKEMON_X, POKEMON_Y
from app.services.kalos_locations_es import (
    KALOS_LOCATION_NAMES_ES,
    translate_location_name,
)
from app.services.location_catalog import LocationCatalog

KALOS_IDS = set(range(2, 169, 2)) - {4, 80}


class FakeBridge:
    def __init__(self):
        self.games_requested = []

    def location_list(self, game="AS"):
        self.games_requested.append(game)
        raw = [{"id": i, "name": f"{KALOS_LOCATION_NAMES_ES[i]} (aclaratorio)"}
               for i in sorted(KALOS_IDS)]
        raw += [
            {"id": 170, "name": "Villa Raíz"},
            {"id": 30010, "name": "Kalos"},
            {"id": 40021, "name": "Campeonato Mundial"},
        ]
        return {"locations": raw}


def _catalog(profile, tmp_path):
    bridge = FakeBridge()
    return LocationCatalog(
        bridge=bridge,
        cache_path=tmp_path / "c.json",
        profile_provider=lambda: profile,
    ), bridge


def test_tabla_cubre_exactamente_los_82_ids_de_kalos():
    assert set(KALOS_LOCATION_NAMES_ES) == KALOS_IDS
    assert len(KALOS_LOCATION_NAMES_ES) == 82


def test_sin_nombres_repetidos_ni_aclaratorios():
    names = list(KALOS_LOCATION_NAMES_ES.values())

    assert len(set(names)) == len(names)
    assert not any("(" in n for n in names)


def test_traduccion_conocida_y_fallback_crudo():
    assert translate_location_name(8, "Ruta 1 (Sendero Boceto)") == "Ruta 1"
    assert translate_location_name(106, "x") == "Liga Pokémon"
    assert translate_location_name(104, "x") == "Calle Victoria"
    assert translate_location_name(134, "x") == "Gruta Tierraunida"
    assert translate_location_name(30010, "Kalos") == "Kalos"


def test_rango_exclusiones_y_orden():
    assert (KALOS_ID_MIN, KALOS_ID_MAX) == (2, 168)
    assert KALOS_ID_MAX < HOENN_ID_MIN
    assert len(EXCLUDED_LOCATION_IDS) == 29
    assert len(STORY_ORDER_IDS) == 48
    assert len(set(STORY_ORDER_IDS)) == len(STORY_ORDER_IDS)
    assert not set(STORY_ORDER_IDS) & EXCLUDED_LOCATION_IDS
    assert set(STORY_ORDER_IDS) <= KALOS_IDS
    assert EXCLUDED_LOCATION_IDS <= KALOS_IDS
    # Lo no excluido y no ordenado va al final por ID (5 lugares).
    assert KALOS_IDS - set(STORY_ORDER_IDS) - EXCLUDED_LOCATION_IDS == {
        108, 112, 140, 144, 146,
    }


def test_orden_corregido_por_ronald():
    o = list(STORY_ORDER_IDS)

    assert o.index(38) < o.index(134) < o.index(42)   # Ruta 7, Tierraunida, Ruta 8
    assert o.index(74) < o.index(142)                  # Ruta 15, Hotel Desolación
    assert o.index(138) < o.index(96)                  # Team Flare antes de Ruta 20
    assert o.index(86) < o.index(94)                   # Fluxus (gim. 7) antes de Fractal (gim. 8)
    assert o.index(96) + 1 == o.index(98) < o.index(100)  # Villa Pokémon entre Ruta 20 y 21
    assert 98 not in EXCLUDED_LOCATION_IDS and 8 in EXCLUDED_LOCATION_IDS
    assert o.index(18) + 1 == o.index(102) < o.index(16)  # Ruta 22 tras Ciudad Novarte
    assert o[0] == 6 and o[-1] == 106                  # Pueblo Boceto ... Liga


def test_x_e_y_comparten_spec_y_cache():
    assert POKEMON_X.content.locations is POKEMON_Y.content.locations
    assert POKEMON_X.content.locations.cache_file == "location_cache_xy.json"
    assert POKEMON_X.content.locations.bridge_game == "X"
    assert POKEMON_X.capabilities.has_location_catalog is True


def test_catalogo_de_kalos_filtra_traduce_y_ordena(tmp_path):
    catalog, bridge = _catalog(POKEMON_Y, tmp_path)
    lista = catalog.list_all()
    ids = [e["id"] for e in lista]

    assert bridge.games_requested == ["X"]
    assert len(ids) == 82 - 29
    assert ids[:3] == [6, 10, 12]
    assert ids[len(STORY_ORDER_IDS) - 1] == 106
    assert ids[len(STORY_ORDER_IDS):] == [108, 112, 140, 144, 146]
    assert {"id": 98, "name": "Villa Pokémon"} in lista
    assert 8 not in ids  # Ruta 1: sin Pokémon salvajes
    assert not any(i in ids for i in (170, 30010, 40021))
    assert not set(ids) & EXCLUDED_LOCATION_IDS


def test_oras_intacto(tmp_path):
    spec = ALPHA_SAPPHIRE.content.locations

    assert (spec.id_min, spec.id_max) == (HOENN_ID_MIN, HOENN_ID_MAX) == (170, 354)
    assert spec.cache_file == "location_cache.json"
    assert spec.bridge_game == "AS"

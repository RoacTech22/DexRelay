"""
Bloque 13 (ruta multijuego, 04/10/2026): contenido y capacidades por perfil.

Dos cosas:
1. ORAS queda IDÉNTICO (catálogo de ubicaciones, textos de la GUI, lectura
   de medallas y bolsa).
2. Un "juego falso" con capacidades apagadas y mapa vacío apaga cada función
   en vez de caer a datos de Hoenn/Alpha Sapphire.
"""

import pytest

from app.games.base import (
    GameCapabilities,
    GameContent,
    GameProfile,
    MemoryMap,
)
from app.games.oras.locations import (
    EXCLUDED_LOCATION_IDS,
    HOENN_ID_MAX,
    HOENN_ID_MIN,
    STORY_ORDER_IDS,
)
from app.games.oras.profile import ALPHA_SAPPHIRE, OMEGA_RUBY
from app.games.xy.profile import POKEMON_X, POKEMON_Y
from app.gui_web.api_dashboard import GAME_VERSIONS
from app.memory.structures import Pokemon6
from app.services.badges_service import BadgesService
from app.services.bag_service import BagService, BagWriteError
from app.services.location_catalog import LocationCatalog
from app.services.location_resolver import LocationResolver


FAKE_GAME = GameProfile(
    key="juego-falso",
    display_name="Juego Falso",
    reader_kind="azahar",
    pokemon_format=Pokemon6,
    memory_map=MemoryMap(),
    capabilities=GameCapabilities(
        has_gym_badges=False,
        has_location_catalog=False,
        has_zone_names=False,
        has_leader_data=False,
        has_bag_writing=False,
        has_hackroom=False,
    ),
    content=GameContent(storage_slug="juego_falso"),
)


class FakeBridge:
    def __init__(self):
        self.games_requested = []

    def location_list(self, game="AS"):
        self.games_requested.append(game)
        return {
            "locations": [
                {"id": 2, "name": "Kalos cualquiera"},
                {"id": 170, "name": "Littleroot Town"},
                {"id": 204, "name": "Route 101"},
                {"id": 276, "name": "???"},
                {"id": 354, "name": "Secret Base"},
                {"id": 40001, "name": "Evento"},
            ]
        }

    def met_location(self, data):
        return {"metLocationId": 204, "metLocationName": "Route 101"}


class FakeMemory:
    def read(self, address, size):
        return bytes([0b00000111])


class FakeReader:
    def __init__(self, profile):
        self.profile = profile
        self.memory = FakeMemory()
        self.process_name = None if profile is None else profile.key

    def is_connected(self):
        return True


def _catalog(profile, tmp_path):
    bridge = FakeBridge()
    catalog = LocationCatalog(
        bridge=bridge,
        cache_path=tmp_path / "cache.json",
        profile_provider=(lambda: profile),
    )
    return catalog, bridge


# ---------- ORAS idéntico ----------

def test_catalogo_oras_igual_que_antes(tmp_path):
    catalog, bridge = _catalog(ALPHA_SAPPHIRE, tmp_path)

    assert catalog.list_all() == [
        {"id": 170, "name": "Villa Raíz"},
        {"id": 204, "name": "Ruta 101"},
    ]
    assert bridge.games_requested == ["AS"]


def test_omega_ruby_pide_la_misma_lista_que_alpha_sapphire(tmp_path):
    catalog, bridge = _catalog(OMEGA_RUBY, tmp_path)

    assert [e["id"] for e in catalog.list_all()] == [170, 204]
    assert bridge.games_requested == ["AS"]


def test_rango_y_exclusiones_de_hoenn_congelados():
    spec = ALPHA_SAPPHIRE.content.locations

    assert (spec.id_min, spec.id_max) == (HOENN_ID_MIN, HOENN_ID_MAX) == (170, 354)
    assert spec.excluded_ids == EXCLUDED_LOCATION_IDS
    assert len(EXCLUDED_LOCATION_IDS) == 14
    assert spec.story_order_ids == STORY_ORDER_IDS
    assert len(STORY_ORDER_IDS) == 69
    assert spec.cache_file == "location_cache.json"
    assert ALPHA_SAPPHIRE.content.locations is OMEGA_RUBY.content.locations


def test_textos_de_la_gui_de_oras_congelados():
    assert GAME_VERSIONS[:2] == [
        {
            "label": "Alpha Sapphire",
            "process_name": "sango-2",
            "badge": "AS",
            "background": "bg_alpha_sapphire.jpg",
            "avatar": "avatar_alpha_sapphire.jpg",
            "card": "card_alpha_sapphire.jpg",
            "experimental": False,
        },
        {
            "label": "Omega Ruby",
            "process_name": "sango-1",
            "badge": "OR",
            "background": "bg_omega_ruby.jpg",
            "avatar": "avatar_omega_ruby.jpg",
            "card": "card_omega_ruby.jpg",
            "experimental": False,
        },
    ]


def test_xy_aparecen_en_la_gui_como_experimentales_con_su_arte():
    assert GAME_VERSIONS[2:] == [
        {
            "label": "Pokémon X",
            "process_name": "kujira-1",
            "badge": "X",
            "background": "bg_pokemon_x.jpg",
            "avatar": "avatar_pokemon_x.jpg",
            "card": "card_pokemon_x.jpg",
            "experimental": True,
        },
        {
            "label": "Pokémon Y",
            "process_name": "kujira-2",
            "badge": "Y",
            "background": "bg_pokemon_y.jpg",
            "avatar": "avatar_pokemon_y.jpg",
            "card": "card_pokemon_y.jpg",
            "experimental": True,
        },
    ]


def test_zona_de_oras_se_resuelve_con_su_tabla():
    resolve = ALPHA_SAPPHIRE.content.zone_name_resolver

    assert resolve(None) is None
    assert resolve(999999) == "Zona 999999"


def test_resolver_de_oras_traduce_con_la_tabla_de_hoenn():
    resolver = LocationResolver(
        bridge=FakeBridge(), profile_provider=lambda: ALPHA_SAPPHIRE
    )

    info = resolver.resolve("Mon", b"\x00" * 232)

    assert info["metLocation"] == "Ruta 101"


def test_medallas_de_oras_se_leen_de_su_direccion():
    reader = FakeReader(ALPHA_SAPPHIRE)

    assert BadgesService(reader).read_badges()["count"] == 3


# ---------- juego falso: todo apagado ----------

def test_juego_falso_no_tiene_catalogo_de_ubicaciones(tmp_path):
    catalog, bridge = _catalog(FAKE_GAME, tmp_path)

    assert catalog.list_all() == []
    assert bridge.games_requested == []


def test_sin_juego_soportado_no_hay_catalogo(tmp_path):
    catalog, bridge = _catalog(None, tmp_path)

    assert catalog.list_all() == []
    assert bridge.games_requested == []


def test_resolver_de_juego_falso_deja_el_texto_de_pkhex():
    resolver = LocationResolver(
        bridge=FakeBridge(), profile_provider=lambda: FAKE_GAME
    )

    info = resolver.resolve("Mon", b"\x00" * 232)

    # El texto crudo de PKHeX, sin pasar por la tabla de Hoenn.
    assert info["metLocation"] == "Route 101"


def test_juego_falso_sin_medallas():
    with pytest.raises(RuntimeError):
        BadgesService(FakeReader(FAKE_GAME)).read_value()


def test_juego_falso_sin_escritura_de_bolsa():
    service = BagService(FakeReader(FAKE_GAME))

    with pytest.raises(BagWriteError):
        service.add_medicine_item(50, 1)


def test_juego_falso_sin_zonas_ni_lideres():
    caps = FAKE_GAME.capabilities

    assert caps.has_zone_names is False
    assert caps.has_leader_data is False
    assert FAKE_GAME.content.zone_name_resolver is None


def test_defaults_de_capacidades_son_los_de_oras():
    caps = GameCapabilities()

    assert caps.has_location_catalog and caps.has_zone_names
    assert caps.has_leader_data and caps.has_bag_writing


def test_hackroom_solo_donde_el_perfil_lo_declara():
    import types

    from app.gui_web.api_hackroom import HackroomMixin

    class Config:
        def get(self, *keys, default=None):
            return True

    def api_for(profile):
        api = HackroomMixin()
        api.app = types.SimpleNamespace(
            reader=types.SimpleNamespace(profile=profile),
            config=Config(),
        )
        return api

    assert api_for(ALPHA_SAPPHIRE)._hackroom_enabled() is True
    assert api_for(None)._hackroom_enabled() is True
    assert api_for(FAKE_GAME)._hackroom_enabled() is False
    assert api_for(FAKE_GAME)._hackroom_available() is False


# ---------- arte y medallas por juego (Bloque 15) ----------

def test_los_archivos_de_arte_de_cada_juego_existen():
    from pathlib import Path

    from app.games.registry import all_profiles

    root = Path(__file__).resolve().parent.parent
    for profile in all_profiles():
        for asset in (
            profile.content.background_asset,
            profile.content.avatar_asset,
            profile.content.card_asset,
        ):
            if asset is not None:
                assert (root / "assets" / "ui" / asset).is_file(), asset


def test_medallas_de_kalos_tienen_sus_ocho_sprites_y_nombres():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for profile in (POKEMON_X, POKEMON_Y):
        assert profile.content.badge_sprite_set == "kalos"
        assert len(profile.content.badge_names) == 8
        for number in range(1, 9):
            sprite = (
                root / "overlays" / "badges" / "sprites" / "kalos" / f"{number}.png"
            )
            assert sprite.is_file(), sprite


def test_medallas_de_hoenn_siguen_en_la_raiz_con_sus_nombres():
    for profile in (ALPHA_SAPPHIRE, OMEGA_RUBY):
        assert profile.content.badge_sprite_set == ""
        assert profile.content.badge_names == (
            "Roca", "Cascada", "Electro", "Llama",
            "Corazón", "Alma", "Lluvia", "Tierra",
        )


def test_lideres_de_kalos_tienen_ocho_retratos_y_nombres():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for profile in (POKEMON_X, POKEMON_Y):
        assert profile.content.leader_portrait_set == "kalos"
        assert len(profile.content.leader_names) == 8
        for number in range(1, 9):
            portrait = root / "assets" / "gym_leaders" / "kalos" / f"{number}.png"
            assert portrait.is_file(), portrait
    for profile in (ALPHA_SAPPHIRE, OMEGA_RUBY):
        assert profile.content.leader_portrait_set == ""

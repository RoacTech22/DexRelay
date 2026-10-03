"""
Bloque 9.4 (01/10/2026): `Api` (lo que pywebview expone a JS como
`window.pywebview.api`) se dividió en un mixin por dominio
(api_dashboard, api_pokemon, api_nuzlocke, api_leaders, api_settings,
api_tools, api_hackroom). Estos tests fijan que la división no cambió
lo que ve el frontend y que no puede degradarse en silencio:

- La lista de métodos públicos que usa app.js es EXACTAMENTE la de
  antes de la división (si se pierde uno, el botón correspondiente
  deja de andar sin ningún error visible en Python).
- Ningún método está definido en dos mixins: con herencia múltiple
  el segundo taparía al primero sin avisar.
"""

import pytest

pytest.importorskip("webview")

from app.gui_web.api import Api  # noqa: E402
from app.gui_web import (  # noqa: E402
    api_dashboard,
    api_hackroom,
    api_leaders,
    api_nuzlocke,
    api_pokemon,
    api_settings,
    api_tools,
)

EXPECTED_PUBLIC_METHODS = [
    "add_rare_candy",
    "cancel",
    "clear_data_cache",
    "clear_logs",
    "get_ability_modal_data",
    "get_ability_modal_data_by_name",
    "get_app_version",
    "get_box_page_data",
    "get_boxes_overview",
    "get_connection_diagnosis",
    "get_connection_status",
    "get_dashboard_data",
    "get_game_avatars",
    "get_game_versions",
    "get_github_url",
    "get_herramientas_page_data",
    "get_issues_url",
    "get_leader_team_window_data",
    "get_location_catalog",
    "get_logo_data_uri",
    "get_mark_data_uri",
    "get_logs",
    "get_move_modal_data",
    "get_move_modal_data_by_name",
    "get_nuzlocke_page_data",
    "get_overlay_preview_data_uri",
    "get_pokemon_page_data",
    "get_runtime_health",
    "get_server_base_url",
    "get_settings_page_data",
    "get_species_catalog",
    "get_species_modal_data",
    "get_team_overlay_settings",
    "get_welcome_background_data_uri",
    "nuzlocke_assign_special",
    "nuzlocke_delete_encounter",
    "nuzlocke_discard_pending",
    "nuzlocke_get_ruleset",
    "nuzlocke_reset_all",
    "nuzlocke_restore_backup",
    "nuzlocke_save_encounter",
    "nuzlocke_save_ruleset",
    "open_external",
    "open_leader_team_window",
    "reset_connection_settings",
    "restart_reader",
    "save_connection_settings",
    "save_hackroom_setting",
    "save_logs_to_file",
    "save_team_overlay_settings",
    "start",
    "start_auto",
    "start_http_server",
    "start_runtime",
    "stop_http_server",
    "stop_runtime",
]

MIXINS = [
    api_hackroom.HackroomMixin,
    api_dashboard.DashboardMixin,
    api_pokemon.PokemonMixin,
    api_nuzlocke.NuzlockeMixin,
    api_leaders.LeadersMixin,
    api_settings.SettingsMixin,
    api_tools.ToolsMixin,
]


def _public_methods(cls):
    return sorted(
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name))
    )


def test_public_api_surface_is_unchanged():
    assert _public_methods(Api) == sorted(EXPECTED_PUBLIC_METHODS)


def test_no_method_is_defined_in_two_mixins():
    seen = {}
    duplicates = []

    for mixin in MIXINS:
        for name, value in vars(mixin).items():
            if name.startswith("__") or not callable(value):
                continue

            if name in seen:
                duplicates.append(f"{name}: {seen[name]} y {mixin.__name__}")

            seen[name] = mixin.__name__

    assert duplicates == []


def test_api_class_only_adds_init_on_top_of_the_mixins():
    own = {
        name
        for name, value in vars(Api).items()
        if callable(value) and not name.startswith("__")
    }

    assert own == set()
    assert "__init__" in vars(Api)


def test_api_inherits_every_mixin():
    for mixin in MIXINS:
        assert issubclass(Api, mixin)

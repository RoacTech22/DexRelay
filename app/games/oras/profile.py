"""
Perfiles de Pokémon Omega Ruby y Alpha Sapphire (Bloque 11).

Migración directa de app/memory/pointers.py y
app/services/combat_service.py: los VALORES son los mismos (los fija
tests/test_pointers_golden.py). Todo el historial de investigación
(AS base vs 1.4, por qué se unificaron las direcciones, cómo se
confirmó cada una) sigue en los comentarios de pointers.py como
referencia histórica; este archivo solo guarda el valor final.

Requisito de versión: las direcciones valen para la actualización
1.4 de AMBOS juegos (el parche unificó el mapa de memoria).
"""

from __future__ import annotations

from app.games.base import (
    GameCapabilities,
    GameContent,
    GameProfile,
    LocationSpec,
    MemoryMap,
    SpecialRules,
)
from app.games.oras.locations import (
    EXCLUDED_LOCATION_IDS,
    HOENN_ID_MAX,
    HOENN_ID_MIN,
    STORY_ORDER_IDS,
)
from app.memory.structures import Pokemon6
from app.services.hoenn_locations_es import translate_location_name
from app.services.zone_names import resolve_zone_name

_LAST_CAUGHT_ADDRESS = 0x08805638
_COMBAT_POINTER_ADDRESS = 0x083F8658

_ORAS_MEMORY_MAP = MemoryMap(
    trainer_card_address=0x08C81340,
    trainer_card_read_size=0x60,
    trainer_card_id_offset=0x00,
    trainer_card_name_offset=0x48,
    trainer_card_name_bytes=24,
    party_order_address=0x08CFB1E0,
    party_count_address=0x08CFB1F8,
    box_base_address=0x08C9E134,
    box_slot_stride=0xE8,
    box_slot_count=30,
    badges_address=0x08C71DC4,
    current_zone_id_address=0x08C6E7A2,
    current_zone_id_mirror_address=0x08C6E884,
    total_caught_address=0x08C8B28C,
    last_caught_address=_LAST_CAUGHT_ADDRESS,
    capture_buffer_address=0x08804A94,
    capture_buffer_entry_stride=0x1E4,
    wild_rival_addresses=(
        0x081FEEC8,
        0x081FFA6C,
        _LAST_CAUGHT_ADDRESS,
    ),
    combat_pointer_address=_COMBAT_POINTER_ADDRESS,
    combat_inactive_pointers=(0, _COMBAT_POINTER_ADDRESS - 4),
    combat_hp_offset=0x404,
    wild_battle_flag_offset=0x87F,
    bag_start_address=0x08C6EC70,
    bag_end_address=0x08C6F800,
    medicine_pocket_start_address=0x08C6B5F0 + 0x3FF0,
    items_pocket_start_address=0x08C6EC70,
    items_pocket_slot_count=400,
    pokeball_item_ids=frozenset(range(1, 17)),
)

# Omega Ruby y Alpha Sapphire comparten la lista de ubicaciones de Hoenn
# (el bridge siempre la pide con GameVersion.AS) y su caché cruda.
# Fósil (29/08/2026): en Ciudad Férrica (Devon Corp, lugar 190) no hay pasto
# salvaje, así que lo que traiga ese Met_Location es un fósil revivido.
# Antes era la constante DEVON_CORP_LOCATION_ID de nuzlocke_service.py.
# El fósil ya queda bajo su lugar real (Devon Corp), así que solo el
# intercambio necesita ancla al lugar donde se recibió (mismo orden que X/Y).
_HOENN_SPECIAL_RULES = SpecialRules(
    fossil_location_ids=frozenset({190}),
    anchor_specials_to_place=True,
)

_HOENN_BADGE_NAMES = (
    "Roca",
    "Cascada",
    "Electro",
    "Llama",
    "Corazón",
    "Alma",
    "Lluvia",
    "Tierra",
)

_HOENN_LOCATIONS = LocationSpec(
    id_min=HOENN_ID_MIN,
    id_max=HOENN_ID_MAX,
    excluded_ids=EXCLUDED_LOCATION_IDS,
    story_order_ids=STORY_ORDER_IDS,
    translate=translate_location_name,
    bridge_game="AS",
    cache_file="location_cache.json",
)

# Los dos juegos comparten mapa de memoria (confirmado en vivo con la
# actualización 1.4), pero cada uno es un perfil propio: el día que
# difieran en algo basta con darle su propio MemoryMap.
ALPHA_SAPPHIRE = GameProfile(
    key="sango-2",
    display_name="Pokémon Alpha Sapphire",
    reader_kind="azahar",
    pokemon_format=Pokemon6,
    memory_map=_ORAS_MEMORY_MAP,
    capabilities=GameCapabilities(generation=6, box_count=7),
    content=GameContent(
        storage_slug="alpha_sapphire",
        title_id_low="0011c500",
        label="Alpha Sapphire",
        badge="AS",
        background_asset="bg_alpha_sapphire.jpg",
        avatar_asset="avatar_alpha_sapphire.jpg",
        card_asset="card_alpha_sapphire.jpg",
        badge_names=_HOENN_BADGE_NAMES,
        locations=_HOENN_LOCATIONS,
        zone_name_resolver=resolve_zone_name,
        special_rules=_HOENN_SPECIAL_RULES,
    ),
)

OMEGA_RUBY = GameProfile(
    key="sango-1",
    display_name="Pokémon Omega Ruby",
    reader_kind="azahar",
    pokemon_format=Pokemon6,
    memory_map=_ORAS_MEMORY_MAP,
    capabilities=GameCapabilities(generation=6, box_count=7),
    content=GameContent(
        storage_slug="omega_ruby",
        title_id_low="0011c400",
        label="Omega Ruby",
        badge="OR",
        background_asset="bg_omega_ruby.jpg",
        avatar_asset="avatar_omega_ruby.jpg",
        card_asset="card_omega_ruby.jpg",
        badge_names=_HOENN_BADGE_NAMES,
        locations=_HOENN_LOCATIONS,
        zone_name_resolver=resolve_zone_name,
        special_rules=_HOENN_SPECIAL_RULES,
    ),
)

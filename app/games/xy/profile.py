"""
Perfiles de Pokémon X y Pokémon Y (Bloque 15, ruta multijuego).

Todos los valores salen de la investigación del Bloque 14 (probes de
solo lectura en tools/probes/xy/, con X y Y en la actualización 1.5) y
están anotados en la sección 9 de la guía de la ruta multijuego. X y Y
comparten mapa de memoria (se confirmó en los dos juegos), igual que
ORAS, pero cada uno es un perfil propio.

Estado de cada dirección:
- CONFIRMADAS en X e Y: tarjeta de entrenador, equipo, cantidad de
  equipo, cajas.
- CANDIDATAS FUERTES, a validar en vivo (Bloque 15): medallas, zona,
  contador de capturas, último capturado, rival salvaje, combate y
  bolsillo de Objetos. Si alguna no se confirma, se deja en None: la
  función se apaga, no se aproxima (reglas 1, 11 y 12).
- Sin investigar (None): buffer de capturas, bolsa completa,
  bolsillo de Medicina.

El contenido de Kalos llega por bloques de la guía de paridad: arte de
medallas, catálogo de ubicaciones (P1) y nombres de zona / detección de
"perdido" (P2, solo zonas ya recolectadas) están activos; líderes sigue
apagado en las capacidades.
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
from app.games.xy.locations import (
    EXCLUDED_LOCATION_IDS,
    KALOS_ID_MAX,
    KALOS_ID_MIN,
    STORY_ORDER_IDS,
)
from app.memory.structures import Pokemon6
from app.services.kalos_locations_es import translate_location_name
from app.services.kalos_zone_names import resolve_zone_name

# Reglas especiales del Nuzlocke en Kalos (P3, 06/10/2026). Fósil: el
# Laboratorio de Fósiles está en Pueblo Petroglifo (lugar 44, que también
# tiene pesca salvaje), así que el lugar solo no basta, y la especie
# tampoco (randomlocke). Medido en vivo en Y con tres casos: al revivir un
# fósil la cantidad de ese objeto baja 1 unos 13-15 s ANTES de que el
# Pokémon aparezca (Fósil Mandíbula 710 -> Tyrunt; Fósil Garra 100 ->
# Anorith), con lugar 44 y nivel de encuentro 20; una captura pescada solo
# baja Poké Balls (Ultra Ball 2). Los IDs de fósil salen de la tabla de
# objetos de PKHeX (data/item_cache.json): 99-105 (Raíz, Garra, Hélix, Domo,
# Ámbar Viejo, Coraza, Cráneo), 572 Tapa, 573 Pluma, 710 Mandíbula, 711
# Aleta. Confirmados en vivo: 100 y 710; el resto, por nombre en la tabla.
_KALOS_SPECIAL_RULES = SpecialRules(
    fossil_location_ids=frozenset({44}),
    fossil_item_ids=frozenset({99, 100, 101, 102, 103, 104, 105, 572, 573, 710, 711}),
    fossil_pseudo_location="Fósil",
    anchor_specials_to_place=True,
)

_LAST_CAUGHT_ADDRESS = 0x08805614
_COMBAT_POINTER_ADDRESS = 0x081FB304

_XY_MEMORY_MAP = MemoryMap(
    # Confirmadas en X e Y.
    trainer_card_address=0x08C79C3C,
    trainer_card_read_size=0x60,
    trainer_card_id_offset=0x00,
    trainer_card_name_offset=0x48,
    trainer_card_name_bytes=24,
    party_order_address=0x08CE1C6C,
    party_count_address=0x08CE1C84,
    box_base_address=0x08C861C8,
    box_slot_stride=0xE8,
    box_slot_count=30,
    # Candidatas fuertes (validar en vivo).
    badges_address=0x08C6A6B0,
    current_zone_id_address=0x08C670AE,
    current_zone_id_mirror_address=0x08C67190,
    current_zone_id_width=2,
    total_caught_address=0x08C82AC0,
    last_caught_address=_LAST_CAUGHT_ADDRESS,
    wild_rival_addresses=(
        0x081FEBA0,
        0x081FF744,
        _LAST_CAUGHT_ADDRESS,
    ),
    combat_pointer_address=_COMBAT_POINTER_ADDRESS,
    # Fuera de combate la celda vale 0 (no queda puntero obsoleto).
    combat_inactive_pointers=(0,),
    combat_hp_offset=0x10,
    # Confirmado en vivo (04-05/10/2026, combate_vivo_xy.py v2): la celda
    # vale 0x08203EC8 en combates SALVAJES (incluidas 3 capturas) y
    # 0x082059D8 en los de ENTRENADOR, desde la primera muestra. El byte
    # +0xFF7 NO sirve: es la fase del combate (0 -> 128 -> 192), no un tipo.
    wild_battle_pointers=frozenset({0x08203EC8}),
    trainer_battle_pointers=frozenset({0x082059D8}),
    items_pocket_start_address=0x08C67564,
    items_pocket_slot_count=400,
    pokeball_item_ids=frozenset(range(1, 17)),
)

# Medallas de Kalos en orden de gimnasio (Viola, Cornelio, Corelia,
# Amaro, Lem, Valeria, Astrid, Edel). Arte provisto por el usuario.
_KALOS_BADGE_NAMES = (
    "Bicho",
    "Acantilado",
    "Lucha",
    "Planta",
    "Voltaje",
    "Hada",
    "Psíquica",
    "Iceberg",
)

_KALOS_LEADER_NAMES = (
    "Violeta",
    "Lino",
    "Corelia",
    "Amaro",
    "Lem",
    "Valeria",
    "Astrid",
    "Edel",
)

# P1 (05/10/2026): X e Y devuelven la misma lista de PKHeX (volcado real),
# así que comparten spec y caché cruda.
_KALOS_LOCATIONS = LocationSpec(
    id_min=KALOS_ID_MIN,
    id_max=KALOS_ID_MAX,
    excluded_ids=EXCLUDED_LOCATION_IDS,
    story_order_ids=STORY_ORDER_IDS,
    translate=translate_location_name,
    bridge_game="X",
    cache_file="location_cache_xy.json",
)

_XY_CAPABILITIES = GameCapabilities(
    generation=6,
    box_count=7,
    experimental=True,
    has_location_catalog=True,
    has_zone_names=True,
    has_leader_data=False,
    has_badge_art=True,
    has_bag_writing=False,
    has_hackroom=False,
)

# Nombres de proceso en Azahar: se leyeron con listar_procesos_xy.py.
POKEMON_X = GameProfile(
    key="kujira-1",
    display_name="Pokémon X",
    reader_kind="azahar",
    pokemon_format=Pokemon6,
    memory_map=_XY_MEMORY_MAP,
    capabilities=_XY_CAPABILITIES,
    content=GameContent(
        storage_slug="pokemon_x",
        title_id_low="00055d00",
        label="Pokémon X",
        badge="X",
        background_asset="bg_pokemon_x.jpg",
        avatar_asset="avatar_pokemon_x.jpg",
        card_asset="card_pokemon_x.jpg",
        badge_sprite_set="kalos",
        badge_names=_KALOS_BADGE_NAMES,
        leader_portrait_set="kalos",
        leader_names=_KALOS_LEADER_NAMES,
        locations=_KALOS_LOCATIONS,
        zone_name_resolver=resolve_zone_name,
        special_rules=_KALOS_SPECIAL_RULES,
    ),
)

POKEMON_Y = GameProfile(
    key="kujira-2",
    display_name="Pokémon Y",
    reader_kind="azahar",
    pokemon_format=Pokemon6,
    memory_map=_XY_MEMORY_MAP,
    capabilities=_XY_CAPABILITIES,
    content=GameContent(
        storage_slug="pokemon_y",
        title_id_low="00055e00",
        label="Pokémon Y",
        badge="Y",
        background_asset="bg_pokemon_y.jpg",
        avatar_asset="avatar_pokemon_y.jpg",
        card_asset="card_pokemon_y.jpg",
        badge_sprite_set="kalos",
        badge_names=_KALOS_BADGE_NAMES,
        leader_portrait_set="kalos",
        leader_names=_KALOS_LEADER_NAMES,
        locations=_KALOS_LOCATIONS,
        zone_name_resolver=resolve_zone_name,
        special_rules=_KALOS_SPECIAL_RULES,
    ),
)

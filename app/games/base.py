"""
Tipos base de la arquitectura multijuego (Bloque 11).

Regla heredada del boceto: NO se agregan campos "por las dudas". Un
campo nuevo aparece cuando un juego real lo necesita, y toda
dirección nueva se confirma antes con un probe en la instancia real
(reglas 1, 11 y 12 del Documento Maestro). Un campo en `None` significa
"no confirmado para este juego": el servicio que lo necesite debe
apagarse (ver `GameCapabilities`), no aproximar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


class PokemonFormat(Protocol):
    """
    Contrato que cumple cualquier decoder de Pokémon (Pokemon6 hoy;
    a futuro Pokemon7, etc.): se construye con los bytes crudos y
    expone lo mismo hacia arriba.
    """

    def __init__(self, encrypted_data: bytes) -> None: ...


@dataclass(frozen=True)
class MemoryMap:
    """
    Todas las direcciones y offsets de memoria de UN juego+versión.

    Es la migración directa de lo que antes vivía suelto en
    app/memory/pointers.py y app/services/combat_service.py; los
    valores de ORAS no cambiaron (los fija tests/test_pointers_golden.py).
    """

    # Entrenador (identifica la PARTIDA, Bloque 5).
    trainer_card_address: int | None = None
    trainer_card_read_size: int | None = None
    trainer_card_id_offset: int | None = None
    trainer_card_name_offset: int | None = None
    trainer_card_name_bytes: int | None = None

    # Party.
    party_order_address: int | None = None
    party_count_address: int | None = None

    # Cajas PC.
    box_base_address: int | None = None
    box_slot_stride: int | None = None
    box_slot_count: int | None = None

    # Progreso y ubicación.
    badges_address: int | None = None
    current_zone_id_address: int | None = None
    current_zone_id_mirror_address: int | None = None

    # Capturas y detección de "perdido".
    total_caught_address: int | None = None
    last_caught_address: int | None = None
    capture_buffer_address: int | None = None
    capture_buffer_entry_stride: int | None = None
    # Direcciones donde buscar el PK6 cifrado del rival salvaje,
    # en orden de prioridad.
    wild_rival_addresses: tuple[int, ...] | None = None

    # Bytes de la zona actual (ORAS: 1; X/Y: 2, u16 little-endian).
    current_zone_id_width: int = 1

    # Combate.
    combat_pointer_address: int | None = None
    # Valores de la celda de combate que significan "sin combate".
    # ORAS: 0 y (celda - 4), un puntero obsoleto; X/Y: solo 0 (la celda
    # vuelve a 0 fuera de combate). None = no hay combate confirmado.
    combat_inactive_pointers: tuple[int, ...] | None = None
    combat_hp_offset: int | None = None
    # Cómo saber si el combate es salvaje o de entrenador (uno de los dos):
    # - ORAS: un byte a `base + wild_battle_flag_offset` (0 = entrenador).
    # - X/Y: el propio valor de la celda de combate (la base de la
    #   estructura) vale una cosa en salvajes y otra en entrenadores.
    wild_battle_flag_offset: int | None = None
    wild_battle_pointers: frozenset[int] | None = None
    trainer_battle_pointers: frozenset[int] | None = None

    # Bolsa.
    bag_start_address: int | None = None
    bag_end_address: int | None = None
    medicine_pocket_start_address: int | None = None
    items_pocket_start_address: int | None = None
    items_pocket_slot_count: int | None = None
    pokeball_item_ids: frozenset[int] | None = None


@dataclass(frozen=True)
class GameCapabilities:
    """
    Qué funciones tienen sentido y están confirmadas para este juego.

    Los defaults son los de ORAS (todo confirmado en vivo). Un juego
    nuevo debe declarar explícitamente lo que NO está confirmado, para
    que la GUI y los servicios lo apaguen en vez de asumirlo.
    """

    generation: int = 6
    box_count: int = 7
    has_gym_badges: bool = True
    # Juego recién agregado, todavía sin validar a fondo: la GUI lo marca.
    experimental: bool = False
    # Bloque 13: cada función que depende de CONTENIDO del juego (no solo
    # de memoria) se declara aquí. Un juego sin ese contenido confirmado
    # apaga la función en vez de mostrar datos de otra región.
    has_location_catalog: bool = True
    has_zone_names: bool = True
    has_leader_data: bool = True
    # Arte y nombres de las 8 medallas de la región (hoy solo Hoenn).
    has_badge_art: bool = True
    has_bag_writing: bool = True
    # Datos del hack Rising Ruby / Sinking Sapphire (solo existen sobre ORAS).
    has_hackroom: bool = True


@dataclass(frozen=True)
class LocationSpec:
    """
    Cómo se arma el catálogo de ubicaciones de un juego (Bloque 13).

    PKHeX devuelve CIENTOS de ubicaciones de todas las regiones; cada
    juego declara qué rango de IDs es el suyo, cuáles se excluyen del
    panel precargado, el orden narrativo y cómo se traduce el nombre.
    """

    id_min: int
    id_max: int
    excluded_ids: frozenset[int]
    story_order_ids: tuple[int, ...]
    # (id, nombre_crudo_de_pkhex) -> nombre mostrado.
    translate: Callable[[int, str], str]
    # Versión que se le pide al bridge ("AS" = GameVersion.AS).
    bridge_game: str = "AS"
    # Archivo de caché CRUDA en data/. Juegos que comparten lista
    # (Omega Ruby y Alpha Sapphire) comparten archivo.
    cache_file: str = "location_cache.json"


@dataclass(frozen=True)
class GameContent:
    """
    Datos del juego que NO son memoria: cómo se llaman sus archivos
    de progreso, cómo se ubica su save, qué ubicaciones y zonas tiene
    y cómo se presenta en la GUI.
    """

    # Parte del nombre de los archivos de progreso
    # (nuzlocke_<slug>_<tid>_<sid>.json). NO cambiar nunca el de un
    # juego ya publicado: dejaría huérfano el progreso de los usuarios.
    storage_slug: str = ""
    # Mitad baja del Title ID, para ubicar la carpeta del save.
    title_id_low: str = ""

    # Presentación en la GUI (Bloque 13). `label` es el nombre corto
    # ("Alpha Sapphire"), `badge` la sigla de la tarjeta ("AS"); los
    # archivos viven en assets/ui/ y pueden faltar (la GUI muestra un
    # fondo/círculo neutro).
    label: str = ""
    badge: str = ""
    background_asset: str | None = None
    avatar_asset: str | None = None
    # Tarjeta cuadrada de la pantalla de inicio (assets/ui/).
    card_asset: str | None = None
    # Medallas: carpeta de sprites dentro de overlays/badges/sprites/
    # ("" = la raíz, arte de Hoenn publicado) y nombres en orden de
    # gimnasio. Vacío = la GUI muestra "Medalla N".
    badge_sprite_set: str = ""
    badge_names: tuple[str, ...] = ()
    # Retratos de líderes para la página Medallas: carpeta dentro de
    # assets/gym_leaders/ y nombres en orden de gimnasio. Vacío = se
    # usa el bloque de Hoenn que ya trae la GUI.
    leader_portrait_set: str = ""
    leader_names: tuple[str, ...] = ()

    # None = el juego no tiene catálogo de ubicaciones confirmado.
    locations: LocationSpec | None = None
    # id de zona -> nombre. None = sin tabla confirmada.
    zone_name_resolver: Callable[[int | None], str | None] | None = None


@dataclass(frozen=True)
class GameProfile:
    """
    Identidad completa de un juego+versión soportado.

    `key` es lo que hoy es `process_name` en Azahar ("sango-2"); el
    resto del proyecto sigue usándolo como identidad del juego, por
    eso la migración puede ser incremental.
    """

    key: str
    display_name: str
    reader_kind: str  # "azahar"
    pokemon_format: type[PokemonFormat]
    memory_map: MemoryMap
    capabilities: GameCapabilities = field(default_factory=GameCapabilities)
    content: GameContent = field(default_factory=GameContent)

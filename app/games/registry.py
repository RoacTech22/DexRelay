"""
Registro de perfiles de juego (Bloque 11).

A diferencia de los getters históricos de app/memory/pointers.py (que
ante un juego desconocido caen a Alpha Sapphire), este registro es
ESTRICTO: un juego sin perfil devuelve `None`. Quien lo use debe
tratarlo como "juego no soportado" y NO leer memoria con direcciones
de otro juego (regla 4 del Documento Maestro).
"""

from __future__ import annotations

from app.games.base import GameProfile
from app.games.oras.profile import ALPHA_SAPPHIRE, OMEGA_RUBY
from app.games.xy.profile import POKEMON_X, POKEMON_Y

_PROFILES: dict[str, GameProfile] = {
    ALPHA_SAPPHIRE.key: ALPHA_SAPPHIRE,
    OMEGA_RUBY.key: OMEGA_RUBY,
    POKEMON_X.key: POKEMON_X,
    POKEMON_Y.key: POKEMON_Y,
}


# Juegos de 3DS que DexRelay RECONOCE por Title ID aunque todavía no
# tengan perfil (son los mismos de TITLE_ID_REGIONS en
# app/gui_web/api_dashboard.py). Sirven para decirle al usuario "detecté
# Pokémon X pero aún no es compatible" en vez de un genérico "no hay
# juego". Reconocer un juego NO significa soportarlo: solo lo soportan
# los que están en _PROFILES.
RECOGNIZED_TITLE_IDS: dict[str, str] = {
    "0004000000055D00": "Pokémon X",
    "0004000000055E00": "Pokémon Y",
    "000400000011C400": "Pokémon Omega Ruby",
    "000400000011C500": "Pokémon Alpha Sapphire",
    "0004000000164800": "Pokémon Sun",
    "0004000000175E00": "Pokémon Moon",
    "00040000001B5000": "Pokémon Ultra Sun",
    "00040000001B5100": "Pokémon Ultra Moon",
}


def recognized_title_name(title_id: int | None) -> str | None:
    """Nombre del juego si el Title ID es uno reconocido, o None."""
    if title_id is None:
        return None
    return RECOGNIZED_TITLE_IDS.get(f"{title_id:016X}")


def get_profile(key: str | None) -> GameProfile | None:
    """Perfil del juego `key` (el process_name), o None si no existe."""
    if key is None:
        return None
    return _PROFILES.get(key)


def all_profiles() -> list[GameProfile]:
    return list(_PROFILES.values())


def process_names(reader_kind: str | None = None) -> tuple[str, ...]:
    """Llaves de los perfiles registrados (opcionalmente de un reader)."""
    return tuple(
        p.key
        for p in _PROFILES.values()
        if reader_kind is None or p.reader_kind == reader_kind
    )

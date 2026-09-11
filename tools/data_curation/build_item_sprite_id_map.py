"""
Bug real encontrado (09/09/2026, reportado por el usuario: "Roca
del Rey... me sale el sprite de Pico Afilado"): los SPRITES de
ítem (`assets/items/{id}.png`, descargados por
download_item_sprites.py) están nombrados con el id PROPIO de
PokéAPI -- pero el resto de DexRelay (item_cache.json, construido
desde PKHeX.item_list() -- ver ItemCatalog --, y el `argument` que
llega de las evoluciones vía el bridge) usa el ÍNDICE REAL del
ítem en el juego (el mismo que usa RARE_CANDY_ITEM_ID=50, tabla
oficial de Bulbapedia). Son DOS numeraciones DISTINTAS que
coinciden para muchos ítems tempranos pero divergen para otros --
confirmado con dos casos reales:

    id=198: item_cache.json (índice real) -> "Baya Dillo"
            item_descriptions.json (id PokéAPI) -> "kings-rock"
    id=221: item_cache.json (índice real) -> "Roca del Rey"
            item_descriptions.json (id PokéAPI) -> "sharp-beak"

Como `_serve_item_sprite()` (app/server/http_server.py) sirve
`assets/items/{id}.png` usando el ÍNDICE REAL tal cual llega del
backend (ver `itemId` en Api._resolve_evolution_transition()), pide
`221.png` esperando la Roca del Rey pero ese archivo se descargó
usando el id 221 de PokéAPI, que ahí es Pico Afilado -- de ahí el
sprite cruzado. Esto es SISTÉMICO: afecta a cualquier ítem donde
las dos numeraciones no coincidan, no solo a estos 2 casos.

FUENTE PARA EL MAPEO REAL: `item_game_indices.csv` del mismo repo
PokeAPI/pokeapi de siempre -- esta tabla existe justamente para
esto (varios juegos/generaciones reindexan los ítems distinto,
PokéAPI documenta la equivalencia real por generación). Se filtra
por `generation_id` de Generación VI (X/Y/ORAS comparten numeración
de ítems, confirmado que Gen 6 es una sola franja sin distinguir
X/Y de ORAS en esta tabla).

SALIDA: data/item_sprite_id_map.json, {indice_real_del_juego (str):
id_de_pokeapi (int)} -- SOLO para los ítems donde los dos ids son
DISTINTOS (si coinciden, no hace falta mapeo, se sirve directo como
ya se hace hoy). http_server.py debe consultar este mapa ANTES de
buscar el archivo.

USO (necesita red -- no se puede correr en un sandbox sin acceso a
internet):

    python -m tools.data_curation.build_item_sprite_id_map
"""

import json

from app.core import paths
from tools.data_curation.build_move_data import fetch_csv_rows

ITEM_GAME_INDICES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/item_game_indices.csv"
)

# Generación VI (X/Y/Omega Ruby/Alpha Sapphire) -- id fijo en el
# esquema de PokéAPI, no algo que haga falta descubrir por CSV
# aparte (mismo criterio que TARGET_VERSION_GROUP_ORDER en
# build_move_data.py: un id de catálogo de PokéAPI, no un dato de
# memoria que necesite verificación empírica).
GENERATION_VI_ID = "6"

OUTPUT_PATH = paths.path("data", "item_sprite_id_map.json")


def main():

    print("Descargando item_game_indices.csv...")
    rows = fetch_csv_rows(ITEM_GAME_INDICES_CSV_URL)

    if not rows:
        raise RuntimeError("item_game_indices.csv vino vacío.")

    real_columns = set(rows[0].keys())
    expected = {"item_id", "generation_id", "game_index"}
    missing = expected - real_columns

    if missing:
        raise RuntimeError(
            f"item_game_indices.csv: faltan columnas esperadas "
            f"{missing}. Columnas reales: {sorted(real_columns)}"
        )

    mapping = {}
    conflicts = []

    for row in rows:

        if row["generation_id"] != GENERATION_VI_ID:
            continue

        game_index = row["game_index"]
        pokeapi_id = int(row["item_id"])

        if game_index in mapping and mapping[game_index] != pokeapi_id:
            conflicts.append(
                (game_index, mapping[game_index], pokeapi_id)
            )
            continue

        mapping[game_index] = pokeapi_id

    if conflicts:
        print(
            f"ADVERTENCIA: {len(conflicts)} índices de juego con más "
            f"de un id de PokéAPI distinto en Generación VI -- "
            f"revisar a mano antes de confiar en el mapeo:"
        )
        for game_index, first_id, second_id in conflicts[:20]:
            print(f"  índice {game_index}: {first_id} vs {second_id}")

    # Solo interesan los casos donde los dos ids NO coinciden -- si
    # son iguales, no hace falta traducir nada (comportamiento
    # actual, servir directo, sigue funcionando bien).
    only_mismatches = {
        game_index: pokeapi_id
        for game_index, pokeapi_id in mapping.items()
        if str(pokeapi_id) != str(game_index)
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(only_mismatches, file, ensure_ascii=False, indent=2)

    print(
        f"Listo: {len(only_mismatches)} ítems con id distinto entre "
        f"el índice real del juego y PokéAPI (de {len(mapping)} "
        f"ítems de Generación VI en total) -- guardado en "
        f"{OUTPUT_PATH}."
    )

    for check_index in ("198", "221"):
        print(
            f"  Verificación: índice real {check_index} -> "
            f"id PokéAPI {only_mismatches.get(check_index, '(sin cambio)')}"
        )


if __name__ == "__main__":
    main()

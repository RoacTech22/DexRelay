"""
Fase E -- overrides de evolución para Rising Ruby / Sinking
Sapphire, parseados de EvolutionChanges.txt (documento oficial del
hack, subido por el usuario).

POR QUÉ HACE FALTA UN OVERRIDE Y NO ALCANZA CON EL BRIDGE TAL CUAL:
species_details() (Program.cs) resuelve evoluciones desde las
tablas INTERNAS de PKHeX.Core (EvolutionTree.GetEvolutionTree) --
son las del juego BASE, PKHeX no tiene forma de saber que el ROM
está parcheado. Para el hackroom hace falta reemplazar/completar
esas respuestas a mano con lo que el documento real dice.

TRES CATEGORÍAS DEL DOCUMENTO, cada una con su regla de aplicación
(confirmado leyendo la nota del documento: "estos métodos nuevos
son ADEMÁS del intercambio, intercambiar sigue funcionando como
antes" -- aplica a las tres subcategorías de trade):

1. Trade Evolutions (8 especies, ej. Kadabra->Alakazam): se AGREGAN
   dos métodos nuevos (amistad alta, o nivel fijo) -- el Trade
   original queda intacto, sigue funcionando.
2. Trade with Item Evolutions (14 especies, ej. Poliwhirl con Roca
   del Rey -> Politoed): se AGREGA "usar el objeto" como si fuera
   una piedra evolutiva -- el Trade original (con o sin objeto
   equipado) sigue funcionando también.
3. Trade with Pokémon Evolutions (2 especies, Karrablast/Shelmet):
   se AGREGA "subir de nivel con la otra especie en el equipo" --
   el Trade original sigue funcionando.
4. Level Adjustments (48 especies): esto SÍ reemplaza -- mismo
   método (subida de nivel simple), nivel más bajo. Los 48 pares de
   este documento son evoluciones estándar sin condición especial
   conocida (no hay ningún caso de género/hora del día/stat en esta
   lista específica), así que methodKey se asume "LevelUp" -- si
   alguna resultara tener una condición especial real (no debería,
   pero no se puede descartar al 100% sin el bridge en vivo), el
   nivel iría igual mal etiquetado; revisar en vivo contra el juego
   si algo se ve raro.

IDs de objeto (14 de la categoría 2) confirmados a mano contra
data/item_cache.json REAL (no adivinados/traducidos por Claude) --
ver el mapeo ITEM_NAME_TO_ID más abajo con el id de cada uno.

SALIDA: data/evolution_changes_rrss.json, lista de entradas
{"fromSpeciesId", "fromSpecies", "toSpeciesId", "toSpecies", "mode"
("add"|"replace"), "methodKey", "level", "argument"} -- "argument"
es 0 salvo para la categoría 2 (id de ítem) y 3 (id de especie
compañera). El consumidor (api.py) filtra por fromSpeciesId y
aplica "add" (agregar a la lista que ya devolvió el bridge) o
"replace" (reemplazar la entrada existente hacia el mismo
toSpeciesId).

USO:
    python -m tools.data_curation.build_evolution_changes_hackroom
"""

import json
import re

from app.core import paths

EVOLUTION_CHANGES_PATH = paths.path(
    "tools", "data_curation", "hackroom_source", "EvolutionChanges.txt"
)
SPECIES_CACHE_PATH = paths.path("data", "species_cache.json")
OUTPUT_PATH = paths.path("data", "evolution_changes_rrss.json")

# Confirmados a mano contra data/item_cache.json real (09/09/2026)
# -- ver docstring del módulo, nombres oficiales verificados contra
# WikiDex/Fandom antes de buscarlos.
ITEM_NAME_TO_ID = {
    "King's Rock": 221,
    "Metal Coat": 233,
    "Protector": 321,
    "Dragon Scale": 235,
    "Electirizer": 322,
    "Magmarizer": 323,
    "Up-Grade": 252,
    "Dubious Disc": 324,
    "Prism Scale": 537,
    "Reaper Cloth": 325,
    "Deep Sea Tooth": 226,
    "Deep Sea Scale": 227,
}

ROW_3COL_PATTERN = re.compile(
    r"^\|\s*\d+\s*\|\s*(?P<from>[^|]+?)\s*\|\s*(?P<to>[^|]+?)\s*\|"
    r"\s*(?P<rest>[^|]+?)\s*\|\s*$"
)

ROW_ITEM_PATTERN = re.compile(
    r"^\|\s*\d+\s*\|\s*(?P<from>[^|]+?)\s*\|\s*(?P<to>[^|]+?)\s*\|"
    r"\s*Use an?\s+(?P<item>.+?)\.\s*\|"
)

ROW_LEVEL_ADJUST_PATTERN = re.compile(
    r"^\|\s*\d+\s*\|\s*(?P<from>[^|]+?)\s*\|\s*(?P<to>[^|]+?)\s*\|"
    r"\s*Lv\.\s*\d+\s*\|\s*Lv\.\s*(?P<new_level>\d+)\s*\|"
)

FRIENDSHIP_OR_LEVEL_PATTERN = re.compile(
    r"friendship value or at Lv\.\s*(\d+)"
)


def load_species_name_to_id():

    with open(SPECIES_CACHE_PATH, "r", encoding="utf-8") as file:
        entries = json.load(file)

    return {entry["name"]: entry["id"] for entry in entries}


def find_section(lines, title):
    """
    Devuelve el índice de línea donde empieza la tabla de datos de
    una sección (la que sigue al título exacto, ej. "Trade
    Evolutions"), o None si no se encuentra.
    """

    for index, line in enumerate(lines):
        if re.match(r"^\|\s*" + re.escape(title) + r"\s*\|\s*$", line):
            return index

    return None


def parse_rows_until_close(lines, start_index):
    """
    Desde 3 líneas después del título de sección (separador,
    encabezado de columnas, separador -- mismo desplazamiento fijo
    que ya usó build_gym_leaders_hackroom.py), junta filas de datos
    hasta la línea de cierre.
    """

    rows = []
    row_index = start_index + 4

    while row_index < len(lines):
        line = lines[row_index]

        if not line.strip().startswith("|"):
            break

        rows.append(line.rstrip("\r\n"))
        row_index += 1

    return rows


def resolve_species_id(name, species_name_to_id, context):

    species_id = species_name_to_id.get(name)

    if species_id is None:
        print(f"ADVERTENCIA ({context}): especie sin resolver: {name!r}")

    return species_id


def main():

    with open(EVOLUTION_CHANGES_PATH, "r", encoding="utf-8") as file:
        lines = file.readlines()

    species_name_to_id = load_species_name_to_id()
    overrides = []

    # --- 1. Trade Evolutions (amistad O nivel fijo) ---
    index = find_section(lines, "Trade Evolutions")
    for row in parse_rows_until_close(lines, index):
        match = ROW_3COL_PATTERN.match(row)
        if not match:
            continue

        from_id = resolve_species_id(
            match.group("from"), species_name_to_id, "Trade Evolutions"
        )
        to_id = resolve_species_id(
            match.group("to"), species_name_to_id, "Trade Evolutions"
        )

        if from_id is None or to_id is None:
            continue

        level_match = FRIENDSHIP_OR_LEVEL_PATTERN.search(match.group("rest"))
        new_level = int(level_match.group(1)) if level_match else None

        overrides.append({
            "fromSpeciesId": from_id,
            "fromSpecies": match.group("from"),
            "toSpeciesId": to_id,
            "toSpecies": match.group("to"),
            "mode": "add",
            "methodKey": "LevelUpFriendship",
            "level": 0,
            "argument": 0,
        })

        if new_level is not None:
            overrides.append({
                "fromSpeciesId": from_id,
                "fromSpecies": match.group("from"),
                "toSpeciesId": to_id,
                "toSpecies": match.group("to"),
                "mode": "add",
                "methodKey": "LevelUp",
                "level": new_level,
                "argument": 0,
            })

    # --- 2. Trade with Item Evolutions ---
    index = find_section(lines, "Trade with Item Evolutions")
    for row in parse_rows_until_close(lines, index):
        match = ROW_ITEM_PATTERN.match(row)
        if not match:
            continue

        from_id = resolve_species_id(
            match.group("from"), species_name_to_id, "Trade with Item"
        )
        to_id = resolve_species_id(
            match.group("to"), species_name_to_id, "Trade with Item"
        )
        item_id = ITEM_NAME_TO_ID.get(match.group("item").strip())

        if from_id is None or to_id is None or item_id is None:
            if item_id is None:
                print(
                    f"ADVERTENCIA (Trade with Item): ítem sin id "
                    f"conocido: {match.group('item')!r}"
                )
            continue

        overrides.append({
            "fromSpeciesId": from_id,
            "fromSpecies": match.group("from"),
            "toSpeciesId": to_id,
            "toSpecies": match.group("to"),
            "mode": "add",
            "methodKey": "UseItem",
            "level": 0,
            "argument": item_id,
        })

    # --- 3. Trade with Pokémon Evolutions ---
    index = find_section(lines, "Trade with Pokémon Evolutions")
    for row in parse_rows_until_close(lines, index):
        match = ROW_3COL_PATTERN.match(row)
        if not match:
            continue

        from_id = resolve_species_id(
            match.group("from"), species_name_to_id, "Trade with Pokémon"
        )
        to_id = resolve_species_id(
            match.group("to"), species_name_to_id, "Trade with Pokémon"
        )

        # El "argumento" acá es la especie COMPAÑERA -- se menciona
        # en el texto libre de la columna "rest" (ej. "Level up with
        # a Shelmet in the party."), no en una columna propia.
        teammate_match = re.search(
            r"with an? ([A-Za-zé]+) in the party", match.group("rest")
        )
        teammate_id = (
            species_name_to_id.get(teammate_match.group(1))
            if teammate_match
            else None
        )

        if from_id is None or to_id is None or teammate_id is None:
            if teammate_match and teammate_id is None:
                print(
                    f"ADVERTENCIA (Trade with Pokémon): compañero sin "
                    f"resolver: {teammate_match.group(1)!r}"
                )
            continue

        overrides.append({
            "fromSpeciesId": from_id,
            "fromSpecies": match.group("from"),
            "toSpeciesId": to_id,
            "toSpecies": match.group("to"),
            "mode": "add",
            "methodKey": "LevelUpWithTeammate",
            "level": 0,
            "argument": teammate_id,
        })

    # --- 4. Level Adjustments (reemplaza el nivel) ---
    index = find_section(lines, "Level Adjustments")
    for row in parse_rows_until_close(lines, index):
        match = ROW_LEVEL_ADJUST_PATTERN.match(row)
        if not match:
            continue

        from_id = resolve_species_id(
            match.group("from"), species_name_to_id, "Level Adjustments"
        )
        to_id = resolve_species_id(
            match.group("to"), species_name_to_id, "Level Adjustments"
        )

        if from_id is None or to_id is None:
            continue

        overrides.append({
            "fromSpeciesId": from_id,
            "fromSpecies": match.group("from"),
            "toSpeciesId": to_id,
            "toSpecies": match.group("to"),
            "mode": "replace",
            "methodKey": "LevelUp",
            "level": int(match.group("new_level")),
            "argument": 0,
        })

    output = {
        "_source": (
            "Rising Ruby / Sinking Sapphire (Drayano), "
            "EvolutionChanges.txt -- parseado 09/09/2026 por "
            "build_evolution_changes_hackroom.py."
        ),
        "overrides": overrides,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"Listo: {len(overrides)} overrides escritos en {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()

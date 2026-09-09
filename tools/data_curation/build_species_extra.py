"""
Curación de una sola vez: altura, peso, categoría ("genus", ej.
"Pokémon Pincho") y descripción tipo Pokédex de cada especie, en
español -- para el modal Pokédex de especie (roadmap 07/09/2026, a
pedido del usuario: "quiero que quede exacto al mockup").

Mismo repositorio CSV de PokeAPI/pokeapi de siempre. A diferencia de
movimientos/habilidades/ítems (que solo necesitaban un archivo de
flavor_text), acá hacen falta 3 CSV distintos:

    - `pokemon.csv`: altura (decímetros) / peso (hectogramos) --
      NO se pidió a PKHeX.Core a propósito: son texto/datos tipo
      Pokédex (igual que descripciones de movimiento/habilidad),
      la misma categoría que ya confirmamos que PKHeX no trae
      confiable -- mismo criterio de siempre, no arriesgar con una
      propiedad de API sin confirmar cuando ya hay una fuente
      probada.
    - `pokemon_species_names.csv`: `genus` (categoría, ej. "Seed
      Pokémon" -> "Pokémon Semilla") en español.
    - `pokemon_species_flavor_text.csv`: descripción completa tipo
      Pokédex, en español, prefiriendo el version_group más
      cercano a ORAS (mismo mecanismo exacto que
      build_move_descriptions.py/build_item_descriptions.py).

Altura/peso se guardan ya convertidos a metros/kg (decímetros/10,
hectogramos/10) -- son los que PokeAPI expone en decímetros/
hectogramos por convención interna del juego, no hace falta que el
frontend haga la conversión.

USO:
    python -m tools.data_curation.build_species_extra
"""

import json

from app.core import paths
from tools.data_curation.build_move_data import (
    fetch_csv_rows,
    VERSION_GROUP_ORDER,
    TARGET_VERSION_GROUP_ORDER,
)


POKEMON_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/pokemon.csv"
)

SPECIES_NAMES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/pokemon_species_names.csv"
)

SPECIES_FLAVOR_TEXT_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/pokemon_species_flavor_text.csv"
)

LANGUAGES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/languages.csv"
)

VERSION_GROUPS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/version_groups.csv"
)

VERSIONS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/versions.csv"
)

OUTPUT_PATH = paths.path("data", "species_extra.json")

# Hasta Kalos/Gen 6 inclusive -- mismo límite que ya usa
# recolectar_evolution_method_keys.py. No hace falta curar
# especies posteriores que ORAS nunca va a mostrar.
LAST_SPECIES_ID_UP_TO_KALOS = 721


def _require_columns(rows, expected_columns, csv_label):

    if not rows:
        return

    real_columns = set(rows[0].keys())
    missing = expected_columns - real_columns

    if missing:
        raise RuntimeError(
            f"{csv_label}: faltan columnas esperadas {missing}. "
            f"Columnas reales: {sorted(real_columns)}"
        )


def _resolve_spanish_language_id(language_rows):

    for row in language_rows:
        if row["identifier"] == "es":
            return row["id"]

    raise RuntimeError(
        "No se encontró 'es' en languages.csv -- columnas reales: "
        f"{sorted(language_rows[0].keys()) if language_rows else []}"
    )


def _build_version_group_name_by_id(version_group_rows):

    return {
        row["id"]: row["identifier"]
        for row in version_group_rows
    }


def _build_version_group_name_by_version_id(
    version_rows, version_group_name_by_id
):
    """
    pokemon_species_flavor_text.csv (a diferencia de
    move_flavor_text.csv/ability_flavor_text.csv/
    item_flavor_text.csv) está indexado por `version_id`
    (versión INDIVIDUAL del juego, ej. "omega-ruby") en vez de
    `version_group_id` (el par, ej. "omega-ruby-alpha-sapphire") --
    bug real corregido (07/09/2026, reportado por el usuario vía el
    autodiagnóstico de columnas): el texto de Pokédex puede
    diferir entre las dos versiones de un mismo par, a diferencia
    de movimientos/habilidades/ítems.

    Esto arma version_id -> nombre de version_group (vía
    versions.csv, que sí tiene `version_group_id`), para poder
    reusar la misma tabla VERSION_GROUP_ORDER de siempre.
    """

    return {
        row["id"]: version_group_name_by_id.get(
            row["version_group_id"]
        )
        for row in version_rows
    }


def _closest_es_flavor_text(rows, version_group_name_by_version_id):
    """
    Mismo criterio exacto que build_move_descriptions.py, salvo que
    acá cada fila trae `version_id` (versión individual), no
    `version_group_id` -- ver el comentario largo en
    _build_version_group_name_by_version_id() para el porqué.
    """

    if not rows:
        return None

    def distance(row):

        version_group_name = version_group_name_by_version_id.get(
            row["version_id"]
        )
        order = VERSION_GROUP_ORDER.get(version_group_name)

        if order is None:
            return (2, float("inf"))

        is_before_target = order < TARGET_VERSION_GROUP_ORDER

        return (
            1 if is_before_target else 0,
            abs(order - TARGET_VERSION_GROUP_ORDER),
        )

    best_row = min(rows, key=distance)

    text = best_row.get("flavor_text")

    if not text:
        return None

    return text.replace("\n", " ").replace("\x0c", " ").strip()


def main():
    print("=====================================")
    print("   CURAR ALTURA/PESO/CATEGORÍA/DESCRIPCIÓN")
    print("   (español, hasta Gen 6 inclusive)")
    print("=====================================")
    print()

    print("Descargando pokemon.csv...")
    pokemon_rows = fetch_csv_rows(POKEMON_CSV_URL)
    _require_columns(
        pokemon_rows,
        {"id", "species_id", "height", "weight", "is_default"},
        "pokemon.csv",
    )

    print("Descargando pokemon_species_names.csv...")
    species_names_rows = fetch_csv_rows(SPECIES_NAMES_CSV_URL)
    _require_columns(
        species_names_rows,
        {"pokemon_species_id", "local_language_id", "genus"},
        "pokemon_species_names.csv",
    )

    print("Descargando languages.csv...")
    language_rows = fetch_csv_rows(LANGUAGES_CSV_URL)
    spanish_language_id = _resolve_spanish_language_id(language_rows)
    print(f"  Id de español (es): {spanish_language_id}")

    print("Descargando version_groups.csv...")
    version_group_rows = fetch_csv_rows(VERSION_GROUPS_CSV_URL)
    version_group_name_by_id = _build_version_group_name_by_id(
        version_group_rows
    )

    print("Descargando versions.csv...")
    version_rows = fetch_csv_rows(VERSIONS_CSV_URL)
    _require_columns(
        version_rows,
        {"id", "version_group_id"},
        "versions.csv",
    )
    version_group_name_by_version_id = (
        _build_version_group_name_by_version_id(
            version_rows, version_group_name_by_id
        )
    )

    print("Descargando pokemon_species_flavor_text.csv (archivo grande, puede tardar)...")
    flavor_text_rows = fetch_csv_rows(SPECIES_FLAVOR_TEXT_CSV_URL)
    _require_columns(
        flavor_text_rows,
        {"species_id", "version_id", "language_id", "flavor_text"},
        "pokemon_species_flavor_text.csv",
    )
    print()

    # Altura/peso: solo la forma "default" de cada especie (evita
    # duplicados de Mega/formas regionales para especies que ya
    # tienen una -- para 1-721 casi no aplica, pero no cuesta nada
    # ser explícito).
    height_weight_by_species = {}

    for row in pokemon_rows:

        if row["is_default"] != "1":
            continue

        species_id = int(row["species_id"])

        if species_id > LAST_SPECIES_ID_UP_TO_KALOS:
            continue

        height_weight_by_species[species_id] = {
            "heightM": int(row["height"]) / 10,
            "weightKg": int(row["weight"]) / 10,
        }

    genus_by_species = {}

    for row in species_names_rows:

        if row["local_language_id"] != spanish_language_id:
            continue

        species_id = int(row["pokemon_species_id"])

        if species_id > LAST_SPECIES_ID_UP_TO_KALOS:
            continue

        if row.get("genus"):
            genus_by_species[species_id] = row["genus"]

    flavor_text_rows_by_species = {}

    for row in flavor_text_rows:

        if row["language_id"] != spanish_language_id:
            continue

        species_id = int(row["species_id"])

        if species_id > LAST_SPECIES_ID_UP_TO_KALOS:
            continue

        flavor_text_rows_by_species.setdefault(
            species_id, []
        ).append(row)

    result = {}

    missing_height_weight = []
    missing_genus = []
    missing_description = []

    for species_id in range(1, LAST_SPECIES_ID_UP_TO_KALOS + 1):

        height_weight = height_weight_by_species.get(species_id)

        if height_weight is None:
            missing_height_weight.append(species_id)
            height_weight = {"heightM": None, "weightKg": None}

        genus = genus_by_species.get(species_id)

        if genus is None:
            missing_genus.append(species_id)

        description = _closest_es_flavor_text(
            flavor_text_rows_by_species.get(species_id, []),
            version_group_name_by_version_id,
        )

        if description is None:
            missing_description.append(species_id)

        result[species_id] = {
            "heightM": height_weight["heightM"],
            "weightKg": height_weight["weightKg"],
            "genus": genus,
            "description": description,
        }

    print(f"Especies totales: {len(result)}")
    print(f"  Sin altura/peso: {len(missing_height_weight)}")
    print(f"  Sin categoría (genus): {len(missing_genus)}")
    print(f"  Sin descripción: {len(missing_description)}")

    if missing_height_weight:
        print(f"    ids sin altura/peso: {missing_height_weight}")
    if missing_genus:
        print(f"    ids sin categoría: {missing_genus}")
    if missing_description:
        print(f"    ids sin descripción: {missing_description}")

    print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"Guardado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

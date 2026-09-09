"""
Curación de una sola vez: descripción de texto de cada ítem, en
español, para el modal de evolución (roadmap 07/09/2026 -- varios
de los 33 methodKey confirmados dependen de un objeto puntual, ver
app/services/evolution_translations.py) y para cuando haga falta
en cualquier otro lado (ej. la página Herramientas, si en algún
momento se agregan más ítems además del Caramelo Raro).

FUENTE: mismo repositorio CSV de PokeAPI/pokeapi de siempre --
`item_flavor_text.csv`, confirmado que existe en el repo (mismo
listado que ya trae `move_flavor_text.csv`/`ability_flavor_text.csv`).
Mismo mecanismo EXACTO que build_move_descriptions.py: preferir el
version_group más cercano a ORAS, sin filtrar por generación (un
ítem de generación posterior simplemente no se va a necesitar,
tenerlo en el dataset no hace daño).

Los NOMBRES de ítem NO se curan acá -- salen gratis del bridge
(PKHeX.item_list(), ver Program.cs/HandleItemList()), porque viven
en el mismo paquete de GameStrings que especies/movimientos/
habilidades. Este script es solo para las DESCRIPCIONES, que sí
hace falta un dataset aparte (mismo motivo que movimientos: texto
tipo Pokédex, no dato mecánico que PKHeX ya tenga).

Si un ítem no tiene ninguna fila en español: `descriptionEs` queda
en `null` explícito -- nunca se cae al inglés en silencio.

USO:
    python -m tools.data_curation.build_item_descriptions
"""

import json

from app.core import paths
from tools.data_curation.build_move_data import (
    fetch_csv_rows,
    VERSION_GROUP_ORDER,
    TARGET_VERSION_GROUP_ORDER,
)


ITEMS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/items.csv"
)

ITEM_FLAVOR_TEXT_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/item_flavor_text.csv"
)

LANGUAGES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/languages.csv"
)

VERSION_GROUPS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/version_groups.csv"
)

OUTPUT_PATH = paths.path("data", "item_descriptions.json")


def _require_columns(rows, expected_columns, csv_label):
    """
    Mismo autodiagnóstico que ya usan los otros scripts de curación
    de esta carpeta: si el CSV real no trae las columnas esperadas,
    imprime las columnas reales en vez de reventar con un KeyError
    críptico más adelante.
    """

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


def resolve_spanish_description(
    item_id,
    flavor_text_by_item,
    version_group_name_by_id,
):
    """
    Resuelve la descripción en español de UN ítem, prefiriendo el
    version_group más cercano a ORAS -- misma lógica exacta que
    resolve_spanish_description() en build_move_descriptions.py
    (reusar hubiera significado importar entre dos scripts
    hermanos por una función de 15 líneas; se prefiere la pequeña
    duplicación explícita, mismo criterio ya usado entre
    build_ability_descriptions.py y build_move_descriptions.py).

    Devuelve (texto, "item_flavor_text") o (None, None).
    """

    rows = flavor_text_by_item.get(item_id, [])

    if not rows:
        return None, None

    def distance(row):

        version_group_name = version_group_name_by_id.get(
            row["version_group_id"]
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
        return None, None

    return text.replace("\n", " ").strip(), "item_flavor_text"


def main():
    print("=====================================")
    print("   CURAR DESCRIPCIONES DE ÍTEM")
    print("   (español, lo más cercano a ORAS)")
    print("=====================================")
    print()

    print("Descargando items.csv...")
    item_rows = fetch_csv_rows(ITEMS_CSV_URL)
    _require_columns(
        item_rows, {"id", "identifier"}, "items.csv"
    )
    print(f"  {len(item_rows)} ítems encontrados en total.")

    print("Descargando languages.csv...")
    language_rows = fetch_csv_rows(LANGUAGES_CSV_URL)
    _require_columns(
        language_rows, {"id", "identifier"}, "languages.csv"
    )
    spanish_language_id = _resolve_spanish_language_id(language_rows)
    print(f"  Id de español (es): {spanish_language_id}")

    print("Descargando version_groups.csv...")
    version_group_rows = fetch_csv_rows(VERSION_GROUPS_CSV_URL)
    _require_columns(
        version_group_rows, {"id", "identifier"}, "version_groups.csv"
    )
    version_group_name_by_id = _build_version_group_name_by_id(
        version_group_rows
    )

    print("Descargando item_flavor_text.csv...")
    flavor_text_rows = fetch_csv_rows(ITEM_FLAVOR_TEXT_CSV_URL)
    _require_columns(
        flavor_text_rows,
        {"item_id", "version_group_id", "language_id", "flavor_text"},
        "item_flavor_text.csv",
    )
    print()

    flavor_text_by_item = {}

    for row in flavor_text_rows:

        if row["language_id"] != spanish_language_id:
            continue

        flavor_text_by_item.setdefault(
            row["item_id"], []
        ).append(row)

    items = {}

    resolved = 0
    missing_spanish = []

    for row in item_rows:

        item_id = row["id"]

        description, source = resolve_spanish_description(
            item_id,
            flavor_text_by_item,
            version_group_name_by_id,
        )

        if source == "item_flavor_text":
            resolved += 1
        else:
            missing_spanish.append(row["identifier"])

        items[item_id] = {
            "name": row["identifier"],
            "descriptionEs": description,
            "source": source,
        }

    print(f"Ítems totales: {len(items)}")
    print(f"  Resueltos desde item_flavor_text.csv (es): {resolved}")
    print(
        f"  SIN español disponible (quedan en null): "
        f"{len(missing_spanish)}"
    )

    if missing_spanish:
        print()
        print(
            "  Lista de los que faltan (revisar el patrón antes "
            "de asumir que hay que completar algo a mano -- ver "
            "el bug real de ids >= 10000 en "
            "build_ability_descriptions.py como referencia):"
        )
        for name in missing_spanish:
            print(f"    - {name}")

    print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)

    print(f"Guardado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

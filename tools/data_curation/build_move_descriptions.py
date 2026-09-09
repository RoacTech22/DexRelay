"""
Curación de una sola vez: descripción de texto de cada movimiento,
en español, para el modal de movimiento (roadmap 06/09/2026,
sección 4.1 -- pregunta abierta #1, última pieza pendiente: ya
resuelta potencia/precisión/categoría en move_data.json y
descripciones de habilidad en build_ability_descriptions.py, esto
cierra el trío).

FUENTE: mismo repositorio CSV de PokeAPI/pokeapi que ya usan
build_move_data.py (moves.csv/move_damage_classes.csv) y
build_ability_descriptions.py (abilities.csv/ability_prose.csv/
etc.) -- acá se suma `move_flavor_text.csv`. Estructura confirmada
contra el código fuente real del serializer de PokéAPI (no solo
inferida): columnas `move_id, version_group_id, language_id,
flavor_text` (mismo patrón exacto que `ability_flavor_text.csv`,
ya usado y confirmado en el script hermano).

A diferencia de habilidades (cobertura de español pareja, con
muchas sin traducir), los MOVIMIENTOS tienen excelente cobertura en
español -- confirmado en vivo con Rayo/Thunderbolt (07/09/2026, ver
build_move_data.py): trae texto en español para varios
version_group, incluyendo `omega-ruby-alpha-sapphire` exacto. Por
eso este script NO necesita una prioridad "prose mecánico primero"
como el de habilidades -- alcanza con `move_flavor_text.csv` solo,
prefiriendo el version_group más cercano a ORAS.

Alcance: a diferencia de build_ability_descriptions.py, este script
NO filtra por generación -- mismo criterio que ya usa
build_move_data.py (moves.csv se procesa completo, los 937
movimientos, sin filtrar por generation_id). Los movimientos
posteriores a Gen 6 simplemente no van a tener una entrada cercana
a ORAS y van a resolver con lo que haya disponible más cercano (o
quedar en null) -- no hace daño tenerlos en el dataset, ORAS nunca
los va a necesitar igual.

Si un movimiento no tiene ninguna fila en español en
`move_flavor_text.csv`: `descriptionEs` queda en `null` explícito
-- nunca se cae al inglés en silencio (mismo criterio de siempre).

USO:
    python -m tools.data_curation.build_move_descriptions
"""

import json

from app.core import paths
from tools.data_curation.build_move_data import (
    fetch_csv_rows,
    VERSION_GROUP_ORDER,
    TARGET_VERSION_GROUP_ORDER,
)


MOVES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/moves.csv"
)

MOVE_FLAVOR_TEXT_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/move_flavor_text.csv"
)

LANGUAGES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/languages.csv"
)

VERSION_GROUPS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/version_groups.csv"
)

OUTPUT_PATH = paths.path("data", "move_descriptions.json")


def _require_columns(rows, expected_columns, csv_label):
    """
    Mismo autodiagnóstico que ya usan build_move_data.py y
    build_ability_descriptions.py: si el CSV real no trae las
    columnas esperadas, imprime las columnas reales en vez de
    reventar con un KeyError críptico más adelante.
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
    move_id,
    flavor_text_by_move,
    version_group_name_by_id,
):
    """
    Resuelve la descripción en español de UN movimiento a partir de
    sus filas de move_flavor_text.csv ya filtradas a español --
    prefiriendo el version_group más cercano a ORAS (mismo criterio
    que _closest_es_flavor_text() en build_ability_descriptions.py,
    reusado acá con la misma lógica de distancia).

    Devuelve (texto, "move_flavor_text") o (None, None) si no hay
    ninguna fila en español para este movimiento.
    """

    rows = flavor_text_by_move.get(move_id, [])

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

    return text.replace("\n", " ").strip(), "move_flavor_text"


def main():
    print("=====================================")
    print("   CURAR DESCRIPCIONES DE MOVIMIENTO")
    print("   (español, lo más cercano a ORAS)")
    print("=====================================")
    print()

    print("Descargando moves.csv...")
    move_rows = fetch_csv_rows(MOVES_CSV_URL)
    _require_columns(
        move_rows, {"id", "identifier"}, "moves.csv"
    )
    print(f"  {len(move_rows)} movimientos encontrados en total.")

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

    print("Descargando move_flavor_text.csv...")
    flavor_text_rows = fetch_csv_rows(MOVE_FLAVOR_TEXT_CSV_URL)
    _require_columns(
        flavor_text_rows,
        {"move_id", "version_group_id", "language_id", "flavor_text"},
        "move_flavor_text.csv",
    )
    print()

    flavor_text_by_move = {}

    for row in flavor_text_rows:

        if row["language_id"] != spanish_language_id:
            continue

        flavor_text_by_move.setdefault(
            row["move_id"], []
        ).append(row)

    moves = {}

    resolved = 0
    missing_spanish = []

    for row in move_rows:

        move_id = row["id"]

        description, source = resolve_spanish_description(
            move_id,
            flavor_text_by_move,
            version_group_name_by_id,
        )

        if source == "move_flavor_text":
            resolved += 1
        else:
            missing_spanish.append(row["identifier"])

        moves[move_id] = {
            "name": row["identifier"],
            "descriptionEs": description,
            "source": source,
        }

    print(f"Movimientos totales: {len(moves)}")
    print(f"  Resueltos desde move_flavor_text.csv (es): {resolved}")
    print(
        f"  SIN español disponible (quedan en null): "
        f"{len(missing_spanish)}"
    )

    if missing_spanish:
        print()
        print(
            "  Lista de los que faltan (probablemente movimientos "
            "de generaciones posteriores a ORAS, sin traducción "
            "vieja disponible -- revisar si alguno importa de "
            "verdad antes de completar a mano):"
        )
        for name in missing_spanish:
            print(f"    - {name}")

    print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(moves, file, ensure_ascii=False, indent=2)

    print(f"Guardado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

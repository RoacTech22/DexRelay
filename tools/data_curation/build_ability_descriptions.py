"""
Curación de una sola vez: descripción de texto de cada habilidad,
en español, para el modal "Pokédex" de detalle de especie (roadmap
06/09/2026, sección 4.1/4.2 -- pregunta abierta #1, resuelta el
07/09/2026: dataset propio, mismo criterio que build_move_data.py).

FUENTE (07/09/2026, a pedido del usuario -- pregunta real: "¿Veekun
no serviría?"): los CSV masivos de PokeAPI/pokeapi en GitHub
(`data/v2/csv/`) son literalmente el mismo dataset que ya usa
build_move_data.py para moves.csv/move_damage_classes.csv -- NO es
una fuente nueva con su propia licencia, es EL MISMO repositorio,
solo que acá se usa para habilidades en vez de movimientos. Sirve
mejor que pedir la API REST individualmente (que era el enfoque
original de este script, reemplazado acá): una sola descarga de
`ability_prose.csv` (traducciones curadas por PokéAPI, columnas
confirmadas contra el archivo real en GitHub:
`ability_id, local_language_id, short_effect, effect`) trae de una
sola vez lo que antes costaba ~310 llamadas HTTP individuales.

A diferencia de movimientos (excelente cobertura de texto en
español en PokéAPI, confirmado con Rayo/Thunderbolt), las
HABILIDADES tienen cobertura más pareja: algunas sí traen
traducción en `ability_prose.csv`/`ability_flavor_text.csv`, otras
no. Decisión (07/09/2026): usar lo que SÍ está traducido, dejar en
`null` lo que no -- esas quedan pendientes para completar a mano
(mismo criterio de "nunca mostrar un valor no confirmado").

Alcance: solo habilidades hasta Generación 6 (ORAS) inclusive --
191 habilidades reales en el juego (76 Gen3 + 47 Gen4 + 41 Gen5 +
24 Gen6 X/Y + 3 exclusivas de ORAS). Se filtra por `generation_id`
de `abilities.csv` -- PokéAPI tiene ~310 habilidades contando
generaciones posteriores, que se descartan sin pedirles nada.

Prioridad de resolución por habilidad:

    1. `ability_prose.csv`, fila en español -- texto MECÁNICO (cómo
       funciona realmente), la fuente más confiable cuando existe.
       Se usa `short_effect` si no está vacío, si no `effect`
       completo.
    2. `ability_flavor_text.csv`, fila(s) en español -- texto más
       "Pokédex", menos preciso mecánicamente pero mejor que nada.
       Entre varias filas en español (una por version_group), se
       prefiere la más cercana a ORAS (reusa VERSION_GROUP_ORDER de
       build_move_data.py).
    3. Si ninguna de las dos existe en español: `descriptionEs`
       queda en `null` explícitamente, con `source: null`.

USO:
    python -m tools.data_curation.build_ability_descriptions

Rápido (unas pocas descargas de CSV, no cientos de llamadas
individuales) -- se corre UNA vez, con internet real. El resultado
(data/ability_descriptions.json) queda commiteado como dataset
estático.
"""

import json

from app.core import paths
from tools.data_curation.build_move_data import (
    fetch_csv_rows,
    VERSION_GROUP_ORDER,
    TARGET_VERSION_GROUP_ORDER,
)


ABILITIES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/abilities.csv"
)

ABILITY_PROSE_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/ability_prose.csv"
)

ABILITY_FLAVOR_TEXT_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/ability_flavor_text.csv"
)

LANGUAGES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/languages.csv"
)

VERSION_GROUPS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/version_groups.csv"
)

OUTPUT_PATH = paths.path("data", "ability_descriptions.json")

# generation_id de abilities.csv/generations.csv -- estos SÍ son
# estructurales y estables (las generaciones ya cerradas no se
# renumeran, mismo criterio que las tablas de version_group de
# build_move_data.py): 3=Gen3, 4=Gen4, 5=Gen5, 6=Gen6(ORAS).
GENERATION_IDS_UP_TO_ORAS = {3, 4, 5, 6}


def _require_columns(rows, expected_columns, csv_label):
    """
    Mismo criterio de autodiagnóstico que ya usa build_move_data.py
    (el bug real de "damage_class_id" vs "move_damage_class_id"):
    si el CSV real no trae las columnas esperadas, imprime las
    columnas reales en vez de reventar con un KeyError críptico más
    adelante.
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
    """
    Resuelve el id de PokéAPI para español buscando `identifier ==
    "es"` en languages.csv -- NO se hardcodea el número a ciegas
    (mismo criterio que build_category_key_by_id() en
    build_move_data.py: nunca asumir un ID sin confirmarlo contra
    la fuente real), aunque ya se vio en vivo que es 7 (confirmado
    07/09/2026 contra pokeapi.co/api/v2/language/7/).
    """

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
    ability_id,
    prose_by_ability,
    flavor_text_by_ability,
    version_group_name_by_id,
):
    """
    Resuelve la descripción en español de una habilidad, con la
    prioridad documentada en el docstring del módulo. Devuelve
    (texto, fuente) -- fuente es "ability_prose",
    "ability_flavor_text" o None (nada disponible en español).
    """

    prose_row = prose_by_ability.get(ability_id)

    if prose_row is not None:

        text = (
            prose_row.get("short_effect")
            or prose_row.get("effect")
        )

        if text:
            return text.replace("\n", " ").strip(), "ability_prose"

    flavor_rows = flavor_text_by_ability.get(ability_id, [])

    if not flavor_rows:
        return None, None

    def distance(row):

        version_group_name = version_group_name_by_id.get(
            row["version_group_id"]
        )

        order = VERSION_GROUP_ORDER.get(version_group_name)

        if order is None:
            return (2, float("inf"))

        is_before_target = order < TARGET_VERSION_GROUP_ORDER

        # Mismo criterio que _closest_es_flavor_text() de la
        # versión anterior de este script: en caso de empate en
        # distancia, preferir la entrada POSTERIOR a ORAS (más
        # probable que refleje ajustes acumulados) por sobre una
        # muy vieja.
        return (
            1 if is_before_target else 0,
            abs(order - TARGET_VERSION_GROUP_ORDER),
        )

    best_row = min(flavor_rows, key=distance)

    text = best_row.get("flavor_text")

    if not text:
        return None, None

    return text.replace("\n", " ").strip(), "ability_flavor_text"


def main():
    print("=====================================")
    print("   CURAR DESCRIPCIONES DE HABILIDAD")
    print("   (español, hasta ORAS inclusive)")
    print("=====================================")
    print()

    print("Descargando abilities.csv...")
    ability_rows = fetch_csv_rows(ABILITIES_CSV_URL)
    _require_columns(
        ability_rows,
        {"id", "identifier", "generation_id"},
        "abilities.csv",
    )
    print(f"  {len(ability_rows)} habilidades encontradas en total.")

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

    print("Descargando ability_prose.csv...")
    prose_rows = fetch_csv_rows(ABILITY_PROSE_CSV_URL)
    _require_columns(
        prose_rows,
        {"ability_id", "local_language_id", "short_effect", "effect"},
        "ability_prose.csv",
    )

    print("Descargando ability_flavor_text.csv...")
    flavor_text_rows = fetch_csv_rows(ABILITY_FLAVOR_TEXT_CSV_URL)
    _require_columns(
        flavor_text_rows,
        {"ability_id", "version_group_id", "language_id", "flavor_text"},
        "ability_flavor_text.csv",
    )
    print()

    prose_by_ability = {
        row["ability_id"]: row
        for row in prose_rows
        if row["local_language_id"] == spanish_language_id
    }

    flavor_text_by_ability = {}

    for row in flavor_text_rows:

        if row["language_id"] != spanish_language_id:
            continue

        flavor_text_by_ability.setdefault(
            row["ability_id"], []
        ).append(row)

    abilities = {}

    skipped_future_generation = 0
    resolved_from_prose = 0
    resolved_from_flavor = 0
    missing_spanish = []

    for row in ability_rows:

        generation_id = int(row["generation_id"])

        if generation_id not in GENERATION_IDS_UP_TO_ORAS:
            skipped_future_generation += 1
            continue

        ability_id = row["id"]

        description, source = resolve_spanish_description(
            ability_id,
            prose_by_ability,
            flavor_text_by_ability,
            version_group_name_by_id,
        )

        if source == "ability_prose":
            resolved_from_prose += 1
        elif source == "ability_flavor_text":
            resolved_from_flavor += 1
        else:
            missing_spanish.append(row["identifier"])

        abilities[ability_id] = {
            "name": row["identifier"],
            "descriptionEs": description,
            "source": source,
        }

    print(f"Habilidades hasta ORAS incluidas: {len(abilities)}")
    print(
        f"  Descartadas por ser de Gen 7+: "
        f"{skipped_future_generation}"
    )
    print(f"  Resueltas desde ability_prose.csv (es): {resolved_from_prose}")
    print(
        f"  Resueltas desde ability_flavor_text.csv (es): "
        f"{resolved_from_flavor}"
    )
    print(
        f"  SIN español disponible (quedan en null, a completar "
        f"a mano): {len(missing_spanish)}"
    )

    if missing_spanish:
        print()
        print("  Lista de las que faltan completar a mano:")
        for name in missing_spanish:
            print(f"    - {name}")

    print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(abilities, file, ensure_ascii=False, indent=2)

    print(f"Guardado en: {OUTPUT_PATH}")
    print(
        "Listo -- revisar la lista de 'SIN español disponible' de "
        "arriba y completar esas a mano en el JSON antes de darlo "
        "por terminado."
    )


if __name__ == "__main__":
    main()


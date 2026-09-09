"""
Valida tools/data_curation/build_ability_descriptions.py contra
casos sintéticos -- no necesita red (a diferencia del script real,
que sí la necesita para descargar los CSV). Mismo criterio de
siempre: probar la lógica de resolución antes de confiar en ella
para las 191 habilidades reales.

    python -m tools.probes.test_ability_descriptions
"""

from tools.data_curation.build_ability_descriptions import (
    resolve_spanish_description,
)


# Id de español sintético para los tests -- no importa cuál sea
# mientras sea consistente entre las filas de prueba (el filtrado
# real por idioma ya lo hace el caller antes de armar estos dicts).
ES = "7"


def test_prefiere_ability_prose_por_sobre_flavor_text():
    """
    Si hay una fila de ability_prose.csv en español, esa gana -- es
    el texto mecánico, más confiable que el flavor text tipo
    Pokédex.
    """

    prose_by_ability = {
        "65": {
            "ability_id": "65",
            "local_language_id": ES,
            "short_effect": "Efecto corto en español.",
            "effect": "Efecto completo en español.",
        },
    }

    flavor_text_by_ability = {
        "65": [
            {
                "ability_id": "65",
                "version_group_id": "16",
                "language_id": ES,
                "flavor_text": "Texto de Pokédex en español.",
            },
        ],
    }

    version_group_name_by_id = {
        "16": "omega-ruby-alpha-sapphire",
    }

    description, source = resolve_spanish_description(
        "65",
        prose_by_ability,
        flavor_text_by_ability,
        version_group_name_by_id,
    )

    assert source == "ability_prose", (
        f"Debería resolver desde ability_prose, dio {source!r}."
    )
    assert description == "Efecto corto en español.", (
        f"Debería usar short_effect, dio {description!r}."
    )

    print(
        "OK - ability_prose.csv en español gana por sobre "
        "ability_flavor_text.csv"
    )


def test_usa_flavor_text_cuando_no_hay_prose_en_espanol():
    """
    Sin fila de ability_prose.csv en español, cae a
    ability_flavor_text.csv -- y entre varias opciones, prefiere la
    más cercana a ORAS (omega-ruby-alpha-sapphire), no la más
    vieja.
    """

    prose_by_ability = {}

    flavor_text_by_ability = {
        "65": [
            {
                "ability_id": "65",
                "version_group_id": "5",
                "language_id": ES,
                "flavor_text": "Descripción vieja de Rubí/Zafiro.",
            },
            {
                "ability_id": "65",
                "version_group_id": "16",
                "language_id": ES,
                "flavor_text": "Descripción de ORAS.",
            },
        ],
    }

    version_group_name_by_id = {
        "5": "ruby-sapphire",
        "16": "omega-ruby-alpha-sapphire",
    }

    description, source = resolve_spanish_description(
        "65",
        prose_by_ability,
        flavor_text_by_ability,
        version_group_name_by_id,
    )

    assert source == "ability_flavor_text", (
        f"Debería resolver desde ability_flavor_text, dio "
        f"{source!r}."
    )
    assert description == "Descripción de ORAS.", (
        f"Debería preferir la entrada de ORAS por sobre la de "
        f"Rubí/Zafiro, dio {description!r}."
    )

    print(
        "OK - ability_flavor_text.csv en español, prefiriendo la "
        "entrada más cercana a ORAS"
    )


def test_null_cuando_no_hay_nada_en_espanol():
    """
    Sin ninguna fila en español (ni prose ni flavor text) para esta
    habilidad, la descripción queda en None -- nunca cae al inglés
    en silencio.
    """

    description, source = resolve_spanish_description(
        "999",
        prose_by_ability={},
        flavor_text_by_ability={},
        version_group_name_by_id={},
    )

    assert description is None, (
        f"Sin español disponible, la descripción debería ser "
        f"None, dio {description!r}."
    )
    assert source is None, (
        f"Sin español disponible, la fuente debería ser None, "
        f"dio {source!r}."
    )

    print(
        "OK - sin texto en español disponible, queda en None "
        "(nunca cae al inglés en silencio)"
    )


if __name__ == "__main__":
    test_prefiere_ability_prose_por_sobre_flavor_text()
    test_usa_flavor_text_cuando_no_hay_prose_en_espanol()
    test_null_cuando_no_hay_nada_en_espanol()

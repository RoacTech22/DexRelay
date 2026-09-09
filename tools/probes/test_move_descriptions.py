"""
Valida tools/data_curation/build_move_descriptions.py contra casos
sintéticos -- no necesita red. Mismo criterio de siempre.

    python -m tools.probes.test_move_descriptions
"""

from tools.data_curation.build_move_descriptions import (
    resolve_spanish_description,
)


def test_prefiere_version_group_mas_cercano_a_oras():
    """
    Caso real (Rayo/Thunderbolt, ver build_move_data.py): entre
    varias filas en español, se prefiere omega-ruby-alpha-sapphire
    por sobre una más vieja.
    """

    flavor_text_by_move = {
        "85": [
            {
                "move_id": "85",
                "version_group_id": "5",
                "language_id": "7",
                "flavor_text": "Descripción vieja de Rubí/Zafiro.",
            },
            {
                "move_id": "85",
                "version_group_id": "16",
                "language_id": "7",
                "flavor_text": "Descripción de ORAS.",
            },
        ],
    }

    version_group_name_by_id = {
        "5": "ruby-sapphire",
        "16": "omega-ruby-alpha-sapphire",
    }

    description, source = resolve_spanish_description(
        "85", flavor_text_by_move, version_group_name_by_id
    )

    assert source == "move_flavor_text", (
        f"Debería resolver desde move_flavor_text, dio {source!r}."
    )
    assert description == "Descripción de ORAS.", (
        f"Debería preferir la entrada de ORAS, dio {description!r}."
    )

    print(
        "OK - prefiere la entrada de move_flavor_text.csv más "
        "cercana a ORAS"
    )


def test_null_cuando_no_hay_filas_en_espanol():
    """
    Sin ninguna fila para este move_id (ya filtradas a español por
    el caller), la descripción queda en None.
    """

    description, source = resolve_spanish_description(
        "999",
        flavor_text_by_move={},
        version_group_name_by_id={},
    )

    assert description is None, (
        f"Sin español disponible, debería dar None, dio "
        f"{description!r}."
    )
    assert source is None

    print(
        "OK - sin filas en español disponibles, queda en None"
    )


if __name__ == "__main__":
    test_prefiere_version_group_mas_cercano_a_oras()
    test_null_cuando_no_hay_filas_en_espanol()

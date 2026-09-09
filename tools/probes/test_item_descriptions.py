"""
Valida tools/data_curation/build_item_descriptions.py contra casos
sintéticos -- no necesita red.

    python -m tools.probes.test_item_descriptions
"""

from tools.data_curation.build_item_descriptions import (
    resolve_spanish_description,
)


def test_prefiere_version_group_mas_cercano_a_oras():

    flavor_text_by_item = {
        "83": [
            {
                "item_id": "83",
                "version_group_id": "5",
                "language_id": "7",
                "flavor_text": "Descripción vieja de Rubí/Zafiro.",
            },
            {
                "item_id": "83",
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
        "83", flavor_text_by_item, version_group_name_by_id
    )

    assert source == "item_flavor_text", (
        f"Debería resolver desde item_flavor_text, dio {source!r}."
    )
    assert description == "Descripción de ORAS.", (
        f"Debería preferir la entrada de ORAS, dio {description!r}."
    )

    print(
        "OK - prefiere la entrada de item_flavor_text.csv más "
        "cercana a ORAS"
    )


def test_null_cuando_no_hay_filas_en_espanol():

    description, source = resolve_spanish_description(
        "999",
        flavor_text_by_item={},
        version_group_name_by_id={},
    )

    assert description is None
    assert source is None

    print("OK - sin filas en español disponibles, queda en None")


if __name__ == "__main__":
    test_prefiere_version_group_mas_cercano_a_oras()
    test_null_cuando_no_hay_filas_en_espanol()

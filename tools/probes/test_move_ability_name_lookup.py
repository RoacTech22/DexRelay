"""
Valida MoveDescriptionCatalog.get_id_by_name()/
AbilityDescriptionCatalog.get_id_by_name() (07/09/2026, a pedido
del usuario: "en donde haya una habilidad o movimiento se debería
poder acceder a su información" -- la ventana de líder de gimnasio
solo tiene el nombre en inglés, sin id).

Corre contra los datasets REALES ya generados (data/move_descriptions.json/
data/ability_descriptions.json), con nombres tal como aparecen en
data/gym_leaders.json (ej. "Rock Tomb", "Magnet Pull").

    python -m tools.probes.test_move_ability_name_lookup
"""

from app.services.move_description import MoveDescriptionCatalog
from app.services.ability_description import AbilityDescriptionCatalog


def test_resuelve_nombres_reales_de_gym_leaders_json():
    """
    Casos tomados directo de data/gym_leaders.json (Geodude de
    Roxanne: movimientos "Tackle"/"Defense Curl"/"Rock Tomb",
    habilidad "Sturdy"; Nosepass: habilidad "Magnet Pull").
    """

    catalog = MoveDescriptionCatalog()

    move_names = ["Tackle", "Defense Curl", "Rock Tomb"]

    for name in move_names:
        move_id = catalog.get_id_by_name(name)
        assert move_id is not None, (
            f"No se resolvió id para el movimiento {name!r} -- "
            f"revisar la normalización o el dataset."
        )
        description = catalog.get(move_id)
        print(f"OK - {name!r} -> id {move_id}, {description}")


def test_resuelve_habilidades_reales_de_gym_leaders_json():

    catalog = AbilityDescriptionCatalog()

    ability_names = ["Sturdy", "Magnet Pull"]

    for name in ability_names:
        ability_id = catalog.get_id_by_name(name)
        assert ability_id is not None, (
            f"No se resolvió id para la habilidad {name!r} -- "
            f"revisar la normalización o el dataset."
        )
        description = catalog.get(ability_id)
        print(f"OK - {name!r} -> id {ability_id}, {description}")


def test_nombre_inexistente_devuelve_none():

    catalog = MoveDescriptionCatalog()

    assert catalog.get_id_by_name("Este Movimiento No Existe") is None

    print("OK - un nombre que no existe devuelve None, no inventa un id")


if __name__ == "__main__":
    test_resuelve_nombres_reales_de_gym_leaders_json()
    test_resuelve_habilidades_reales_de_gym_leaders_json()
    test_nombre_inexistente_devuelve_none()

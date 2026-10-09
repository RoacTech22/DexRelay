"""
Pruebas de la lógica pura de comparar_datos_xy_oras.py (sin bridge ni
red): comparación de especies, lectura del changelog y el informe.
"""

import comparar_datos_xy_oras as probe


def _detalle(**cambios):
    base = {
        "id": 25,
        "name": "Pikachu",
        "type1Key": "Electric",
        "type2Key": "",
        "baseStats": {
            "hp": 35,
            "attack": 55,
            "defense": 40,
            "spAttack": 50,
            "spDefense": 50,
            "speed": 90,
        },
        "ability1Id": 9,
        "ability1Name": "Elec. Estática",
        "ability2Id": 0,
        "ability2Name": "",
        "abilityHiddenId": 31,
        "abilityHiddenName": "Pararrayos",
        "evolutions": [
            {
                "toSpeciesId": 26,
                "methodKey": "UseItem",
                "level": 0,
                "argument": 83,
            }
        ],
    }
    base.update(cambios)
    return base


def test_especies_iguales_no_dan_diferencias():
    assert probe.diferencias_especie(_detalle(), _detalle()) == []


def test_detecta_stat_tipo_habilidad_y_evolucion():
    distinto = _detalle(
        type2Key="Fairy",
        baseStats={**_detalle()["baseStats"], "speed": 95},
        ability1Id=10,
        evolutions=[],
    )

    campos = {d["campo"] for d in probe.diferencias_especie(_detalle(), distinto)}

    assert campos == {
        "type2Key",
        "baseStats.speed",
        "ability1Id",
        "evolutions",
    }


def test_el_orden_de_las_evoluciones_no_cuenta():
    a = _detalle(
        evolutions=[
            {"toSpeciesId": 1, "methodKey": "A", "level": 1, "argument": 0},
            {"toSpeciesId": 2, "methodKey": "B", "level": 2, "argument": 0},
        ]
    )
    b = _detalle(evolutions=list(reversed(a["evolutions"])))

    assert probe.diferencias_especie(a, b) == []


def test_comparar_especies_cuenta_y_marca_sin_datos():
    oras = {1: _detalle(id=1), 2: _detalle(id=2), 3: {"error": "x"}}
    xy = {
        1: _detalle(id=1),
        2: _detalle(id=2, type1Key="Fire"),
        3: _detalle(id=3),
        4: _detalle(id=4),
    }

    resultado = probe.comparar_especies(oras, xy)

    assert resultado["iguales"] == 1
    assert [e["id"] for e in resultado["distintas"]] == [2]
    assert resultado["sin_datos"] == [3, 4]
    assert resultado["comparadas"] == 2


GRUPOS = [
    {"id": "15", "identifier": "x-y"},
    {"id": "16", "identifier": "omega-ruby-alpha-sapphire"},
    {"id": "17", "identifier": "sun-moon"},
]


def test_changelog_separa_xy_de_oras():
    filas = [
        {"move_id": "85", "changed_in_version_group_id": "15", "power": "95"},
        {"move_id": "22", "changed_in_version_group_id": "15", "power": "35", "pp": "15"},
        {"move_id": "99", "changed_in_version_group_id": "16", "power": "40"},
        {"move_id": "7", "changed_in_version_group_id": "17", "pp": "10"},
    ]

    resultado = probe.analizar_changelog(filas, GRUPOS, {99: "rage"})

    assert resultado["id_xy"] == "15" and resultado["id_oras"] == "16"
    assert resultado["cantidad_cambiados_en_xy_gen5_a_gen6"] == 2
    assert resultado["cambios_entre_xy_y_oras"] == [
        {
            "move_id": 99,
            "name": "rage",
            "valores_anteriores": {"power": "40"},
        }
    ]


def test_changelog_sin_grupos_conocidos_informa_error():
    resultado = probe.analizar_changelog([], [{"id": "1", "identifier": "red-blue"}])

    assert "error" in resultado


def test_informe_sin_cambios_entre_xy_y_oras():
    especies = probe.comparar_especies({1: _detalle()}, {1: _detalle()})
    movimientos = probe.analizar_changelog([], GRUPOS)

    texto = probe.formatear(especies, movimientos)

    assert "distintas=0" in texto
    assert "ENTRE X/Y y ORAS: 0" in texto


def test_informe_lista_las_diferencias():
    especies = probe.comparar_especies(
        {1: _detalle(name="Bulbasaur")},
        {1: _detalle(name="Bulbasaur", ability1Id=65)},
    )

    texto = probe.formatear(especies, None)

    assert "#1 Bulbasaur" in texto
    assert "ability1Id" in texto

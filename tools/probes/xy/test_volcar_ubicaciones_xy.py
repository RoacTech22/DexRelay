"""
Pruebas de la lógica pura de volcar_ubicaciones_xy.py (sin bridge):
comparación X/Y/AS, clasificación de IDs e informe.
"""

import volcar_ubicaciones_xy as probe


def _lista(*pares):
    return [{"id": i, "name": n} for i, n in pares]


BASE = _lista(
    (0, "(Ningún objeto)"),
    (8, "Ruta 1"),
    (10, "Pueblo Acuarela"),
    (170, "Villa Raíz"),
    (30001, "Intercambio (NPC)"),
    (40021, "Campeonato Mundial"),
    (60002, "Pareja de la Guardería"),
)


def test_clasificar_ids():
    assert probe.clasificar(0) == "cero"
    assert probe.clasificar(2) == "kalos(<=169)"
    assert probe.clasificar(169) == "kalos(<=169)"
    assert probe.clasificar(170) == "hoenn(170-354)"
    assert probe.clasificar(354) == "hoenn(170-354)"
    assert probe.clasificar(30010) == "transferencia(30000+)"
    assert probe.clasificar(40073) == "evento(40000+)"
    assert probe.clasificar(60002) == "regalo(60000+)"


def test_x_igual_a_y():
    h = probe.analizar(BASE, list(BASE))

    assert h["x_igual_a_y"] is True
    assert h["solo_en_x"] == [] and h["solo_en_y"] == []
    assert h["kalos_cantidad"] == 2
    assert (h["kalos_min"], h["kalos_max"]) == (8, 10)
    assert h["hoenn_en_lista_x"] == 1


def test_x_distinto_de_y_se_reporta():
    y = _lista((8, "Ruta 1"), (10, "Otro nombre"), (12, "Ruta 2"))
    h = probe.analizar(BASE, y)

    assert h["x_igual_a_y"] is False
    assert 12 in h["solo_en_y"]
    assert {"id": 10, "x": "Pueblo Acuarela", "y": "Otro nombre"} in h[
        "nombre_distinto_xy"
    ]


def test_nombres_repetidos_y_huecos():
    x = _lista((2, "A"), (6, "B"), (8, "B"))
    h = probe.analizar(x, x)

    assert h["nombres_repetidos_en_kalos"] == {"B": [6, 8]}
    assert h["kalos_ids_pares_ausentes"] == [4]


def test_comparacion_con_as():
    as_ = _lista((8, "Ruta 1"), (10, "Pueblo Acuarela"), (12, "Ruta 2"))
    h = probe.analizar(BASE, BASE, as_)

    cmp_as = h["kalos_x_vs_as"]
    assert cmp_as["mismos_ids"] is False
    assert cmp_as["solo_en_as"] == [12]
    assert cmp_as["solo_en_x"] == []


def test_entradas_rotas_se_ignoran():
    h = probe.analizar([{"name": "sin id"}, None, {"id": "x"}], [])

    assert h["total_x"] == 0
    assert h["kalos_min"] is None


def test_informe_incluye_lista_de_kalos():
    h = probe.analizar(BASE, BASE, BASE)
    texto = probe.formatear(h, BASE)

    assert "MISMA lista: SÍ" in texto
    assert "Ruta 1" in texto and "Pueblo Acuarela" in texto
    assert "Villa Raíz" not in texto.split("Kalos según X")[1]

"""Pruebas de la lógica pura de bolsa_xy.py (sin Azahar)."""

import json
import struct

import bolsa_xy as probe

BASE = 0x1000


def _data(*slots, total=20):
    data = bytearray(total * 4)
    for i, (item_id, cantidad) in enumerate(slots):
        struct.pack_into("<HH", data, i * 4, item_id, cantidad)
    return bytes(data)


def test_leer_casilleros_asigna_direcciones():
    c = probe.leer_casilleros(_data((4, 50), (0, 0), (50, 7), total=3), BASE)
    assert c == {BASE: (4, 50), BASE + 4: (0, 0), BASE + 8: (50, 7)}
    assert probe.leer_casilleros(b"", BASE) == {}
    assert probe.leer_casilleros(None, BASE) == {}


def test_tramos_separa_por_rachas_de_vacios():
    c = probe.leer_casilleros(
        _data((4, 5), (3, 2), (0, 0), (0, 0), (0, 0), (0, 0), (17, 9), (50, 1)), BASE
    )
    t = probe.tramos(c)
    assert [(x["inicio"], x["fin"], x["n"]) for x in t] == [
        (BASE, BASE + 4, 2),
        (BASE + 24, BASE + 28, 2),
    ]


def test_tramos_hueco_corto_no_corta():
    c = probe.leer_casilleros(_data((4, 5), (0, 0), (0, 0), (17, 9), total=4), BASE)
    t = probe.tramos(c)
    assert len(t) == 1 and t[0]["n"] == 2


def test_tramos_sin_datos():
    assert probe.tramos(probe.leer_casilleros(_data(total=6), BASE)) == []


def test_tramo_de_y_diferencias():
    antes = probe.leer_casilleros(_data((17, 5), (28, 3), total=6), BASE)
    despues = probe.leer_casilleros(_data((17, 5), (28, 2), total=6), BASE)
    assert probe.diferencias(antes, despues) == [(BASE + 4, (28, 3), (28, 2))]
    lista = probe.tramos(antes)
    assert probe.tramo_de(BASE + 4, lista)["inicio"] == BASE
    assert probe.tramo_de(BASE + 16, lista) is None


def test_diferencias_item_que_se_agota():
    antes = {BASE: (28, 1)}
    despues = {BASE: (0, 0)}
    assert probe.diferencias(antes, despues) == [(BASE, (28, 1), (0, 0))]


def test_formatear_incluye_nombres_y_desplazamiento():
    c = probe.leer_casilleros(_data((17, 5), total=2), BASE)
    lista = probe.tramos(c)
    texto = probe.formatear_tramos(lista, {17: "Poción"}, base=BASE)
    assert "Poción" in texto and "+0x0" in texto
    eventos = [{"direccion": BASE, "antes": [17, 5], "despues": [17, 4], "t": 1.0}]
    cambios = probe.formatear_cambios(eventos, lista, {17: "Poción"}, base=BASE)
    assert "Poción" in cambios and "0x00001000" in cambios


def test_cargar_nombres_y_fallo(tmp_path):
    p = tmp_path / "items.json"
    p.write_text(json.dumps([{"id": 50, "name": "Caramelo Raro"}]), encoding="utf-8")
    assert probe.cargar_nombres(p) == {50: "Caramelo Raro"}
    assert probe.cargar_nombres(tmp_path / "no.json") == {}


def test_guardar_json(tmp_path):
    out = tmp_path / "s" / "b.json"
    c = probe.leer_casilleros(_data((17, 5), total=2), BASE)
    probe.guardar(BASE, c, probe.tramos(c), [], path=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["base"] == BASE and data["tramos"][0]["n"] == 1

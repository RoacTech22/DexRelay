"""Pruebas de la lógica pura de fosil_bolsa_xy.py (sin Azahar)."""

import struct

import fosil_bolsa_xy as probe


def _bolsillo(*slots, total=8):
    data = bytearray(total * 4)
    for i, (item_id, cantidad) in enumerate(slots):
        struct.pack_into("<HH", data, i * 4, item_id, cantidad)
    return bytes(data)


def _pokemon(t, met=44, especie=696):
    return {"t": t, "tipo": "pokemon", "campos": {
        "especie": especie, "apodo": "x", "met_location": met,
        "nivel_encuentro": 20,
    }}


def _bolsa(t, item_id, antes, despues):
    return {"t": t, "tipo": "bolsa", "id": item_id, "antes": antes, "despues": despues}


def test_leer_bolsillo_ignora_casilleros_vacios_y_suma_repetidos():
    assert probe.leer_bolsillo(_bolsillo((4, 50), (0, 0), (570, 2), (4, 3))) == {4: 53, 570: 2}
    assert probe.leer_bolsillo(b"") == {}
    assert probe.leer_bolsillo(None) == {}


def test_diferencias_detecta_bajas_altas_y_objetos_que_aparecen_o_se_agotan():
    antes = {4: 50, 570: 2, 99: 1}
    despues = {4: 49, 570: 2, 77: 1}

    assert probe.diferencias(antes, despues) == [(4, 50, 49), (77, 0, 1), (99, 1, 0)]
    assert probe.diferencias(antes, antes) == []


def test_correlaciona_la_baja_del_fosil_con_el_pokemon_y_distingue_la_bola():
    eventos = [
        _bolsa(10.0, 570, 2, 1),       # fósil: baja ANTES del Pokémon
        _pokemon(12.5),
        _bolsa(300.0, 4, 50, 49),      # Poké Ball de una captura aparte
        _pokemon(301.0, met=44, especie=691),
    ]

    pares = probe.correlacionar(eventos, ventana=60)

    assert [b["id"] for b in pares[0]["bajas"]] == [570]
    assert pares[0]["bajas"][0]["segundos"] == -2.5
    assert [b["id"] for b in pares[1]["bajas"]] == [4]


def test_la_baja_puede_ocurrir_despues_del_pokemon():
    pares = probe.correlacionar([_pokemon(10.0), _bolsa(13.0, 570, 1, 0)], ventana=60)

    assert pares[0]["bajas"][0]["segundos"] == 3.0


def test_subidas_y_bajas_fuera_de_la_ventana_no_cuentan():
    eventos = [_bolsa(0, 570, 1, 2), _bolsa(1, 4, 5, 4), _pokemon(500)]

    assert probe.correlacionar(eventos, ventana=60)[0]["bajas"] == []


def test_filtra_por_lugar():
    eventos = [_pokemon(1, met=44), _pokemon(2, met=62)]

    assert len(probe.correlacionar(eventos, lugares={44})) == 1
    assert len(probe.correlacionar(eventos)) == 2


def test_resumen_lista_cambios_y_pares():
    texto = probe.resumen([_bolsa(10.0, 570, 2, 1), _pokemon(12.5)], {44})

    assert "objeto 570: 2 -> 1" in texto
    assert "objeto 570 -1 a -2.5 s" in texto
    assert "(ningún Pokémon nuevo)" in probe.resumen([])


def test_guardar_escribe_json(tmp_path):
    ruta = tmp_path / "salida" / "f.json"
    probe.guardar([_bolsa(1, 570, 2, 1)], ruta)

    assert '"id": 570' in ruta.read_text(encoding="utf-8")

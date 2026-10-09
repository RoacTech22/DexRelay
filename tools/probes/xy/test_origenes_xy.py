"""
Pruebas de la lógica pura de origenes_xy.py (sin Azahar ni bridge):
decodificación de los campos de origen del PK6, seguimiento de nuevos/
cambios/idos y el resumen con el solape frente a capturas salvajes.
"""

import struct

import origenes_xy as probe


def _raw(pid=1, species=25, nick="Pika", egg=False, met=0, egg_loc=0,
         ball=4, met_level=5, version=24, ot="Ash"):
    data = bytearray(232)
    struct.pack_into("<I", data, 0, pid)
    struct.pack_into("<H", data, 0x08, species)
    data[0x40:0x40 + 24] = nick.encode("utf-16le")[:24].ljust(24, b"\x00")
    struct.pack_into("<I", data, probe.IV32_OFFSET, (1 << 30) if egg else 0)
    data[0xB0:0xB0 + 24] = ot.encode("utf-16le")[:24].ljust(24, b"\x00")
    struct.pack_into("<H", data, probe.EGG_LOCATION_OFFSET, egg_loc)
    struct.pack_into("<H", data, probe.MET_LOCATION_OFFSET, met)
    data[probe.BALL_OFFSET] = ball
    data[probe.MET_LEVEL_OFFSET] = met_level | 0x80  # bit 7 = género del OT
    data[probe.ORIGIN_GAME_OFFSET] = version
    return bytes(data)


def _scan(*raws, origen="equipo 1"):
    return {probe.pid_of(r): {"raw": r, "origen": origen} for r in raws}


def test_decodifica_campos_de_origen():
    c = probe.decodificar_origen(
        _raw(pid=77, species=696, nick="Rex", met=106, egg_loc=60002,
             ball=4, met_level=20, version=24, ot="Ronald")
    )

    assert c["pid"] == 77
    assert c["especie"] == 696
    assert c["apodo"] == "Rex"
    assert c["es_huevo"] is False
    assert c["met_location"] == 106
    assert c["egg_location"] == 60002
    assert c["nivel_encuentro"] == 20   # el bit de género del OT no cuenta
    assert c["bola"] == 4
    assert c["juego_origen"] == 24
    assert c["ot"] == "Ronald"
    assert probe.decodificar_origen(_raw(egg=True))["es_huevo"] is True
    assert probe.decodificar_origen(b"\x00" * 10) is None
    assert probe.decodificar_origen(None) is None


def test_linea_base_no_genera_eventos_y_un_pokemon_nuevo_si():
    seg = probe.Seguimiento()
    seg.linea_base(_scan(_raw(pid=1)), now=0)

    assert seg.alimentar(_scan(_raw(pid=1)), now=1) == []

    nuevos = seg.alimentar(_scan(_raw(pid=1), _raw(pid=2, species=696)), now=2, zona=266)

    assert [e["tipo"] for e in nuevos] == ["nuevo"]
    assert nuevos[0]["pid"] == 2
    assert nuevos[0]["zona"] == 266
    assert len(nuevos[0]["raw_hex"]) == 232 * 2


def test_seguimiento_ve_el_paso_de_placeholder_a_nombre_real():
    seg = probe.Seguimiento()
    seg.linea_base({}, now=0)

    seg.alimentar(_scan(_raw(pid=5, nick="Egg", egg=True)), now=1)
    cambios = seg.alimentar(
        _scan(_raw(pid=5, nick="Tyra", egg=False, met=106)), now=2
    )

    assert cambios[0]["tipo"] == "cambio"
    assert cambios[0]["cambios"]["apodo"] == ["Egg", "Tyra"]
    assert cambios[0]["cambios"]["es_huevo"] == [True, False]
    assert cambios[0]["cambios"]["met_location"] == [0, 106]
    assert probe.estados_previos(seg.eventos, 5)


def test_pokemon_ausente_se_da_por_ido_solo_pasado_el_plazo():
    seg = probe.Seguimiento()
    seg.linea_base(_scan(_raw(pid=1), _raw(pid=2)), now=0)

    assert seg.alimentar(_scan(_raw(pid=1)), now=2) == []
    ido = seg.alimentar(_scan(_raw(pid=1)), now=probe.VANISH_SECONDS + 1)

    assert [(e["tipo"], e["pid"]) for e in ido] == [("ido", 2)]
    # No se repite.
    assert seg.alimentar(_scan(_raw(pid=1)), now=probe.VANISH_SECONDS + 2) == []


def test_resumen_marca_el_solape_del_lugar_con_los_salvajes():
    seg = probe.Seguimiento()
    seg.linea_base({}, now=0)
    seg.alimentar(_scan(_raw(pid=1, species=129, nick="Magikarp", met=106, met_level=22)), now=1)
    seg.alimentar(_scan(_raw(pid=1), _raw(pid=2, species=696, nick="Tyra", met=106, met_level=20)), now=2)
    seg.alimentar(_scan(_raw(pid=1), _raw(pid=2), _raw(pid=3, species=133, nick="Eevee", met=500, egg_loc=60002)), now=3)

    assert seg.etiquetar(1, "salvaje")
    assert seg.etiquetar(2, "fosil")
    assert seg.etiquetar(3, "regalo")
    assert not seg.etiquetar(99, "huevo")

    texto = probe.resumen(seg.eventos)

    assert "== fosil (1) ==" in texto
    assert "SOLAPAN con salvajes en [106]" in texto
    assert "regalo: lugares [500]; sin solape" in texto


def test_resumen_sin_salvajes_avisa_que_no_es_concluyente():
    seg = probe.Seguimiento()
    seg.linea_base({}, now=0)
    seg.alimentar(_scan(_raw(pid=2, species=696, met=106)), now=1)
    seg.etiquetar(2, "fosil")

    assert "no es concluyente" in probe.resumen(seg.eventos)


def test_guardar_y_cargar_ida_y_vuelta(tmp_path):
    seg = probe.Seguimiento()
    seg.linea_base({}, now=0)
    seg.alimentar(_scan(_raw(pid=2, met=106)), now=1)
    seg.etiquetar(2, "fosil")
    path = tmp_path / "salida" / "o.json"

    probe.guardar(seg.eventos, path)

    assert probe.cargar(path)[0]["etiqueta"] == "fosil"
    assert probe.cargar(tmp_path / "no_existe.json") == []


def test_preguntar_acepta_solo_etiquetas_validas():
    evento = {"campos": {"especie": 1, "apodo": "x", "met_location": 1,
                         "egg_location": 0, "nivel_encuentro": 5}, "origen": "equipo 1"}

    assert probe.preguntar(evento, input_fn=lambda _: "Fosil") == "fosil"
    assert probe.preguntar(evento, input_fn=lambda _: "") is None
    assert probe.preguntar(evento, input_fn=lambda _: "bananas") is None
    assert probe.preguntar(evento, input_fn=lambda _: "salir") == "salir"


def test_inventario_filtra_por_especie_y_ordena():
    escaneo = {
        1: {"raw": _raw(pid=1, species=131, nick="Lapras", met=24, met_level=40), "origen": "caja 1.1"},
        2: {"raw": _raw(pid=2, species=25, nick="Pika", met=8), "origen": "equipo 1"},
        3: {"raw": _raw(pid=3, species=1, nick="Bulba", met=18, met_level=10), "origen": "caja 2.5"},
    }

    filas = probe.inventario(escaneo, {1, 131})

    assert [f["campos"]["especie"] for f in filas] == [1, 131]
    assert filas[0]["origen"] == "caja 2.5"
    assert len(filas[0]["raw_hex"]) == 232 * 2
    assert "ot='Ash'" in probe.texto_inventario(filas)
    assert probe.texto_inventario([]).startswith("(ninguno")


def test_inventario_por_defecto_cubre_regalos_y_fosiles_de_kalos():
    for especie in (1, 4, 7, 447, 448, 131, 696, 698):
        assert especie in probe.INVENTARIO_ESPECIES

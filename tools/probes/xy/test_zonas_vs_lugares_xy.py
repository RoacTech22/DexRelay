"""
Pruebas de la lógica pura de zonas_vs_lugares_xy.py (sin Azahar ni
bridge): estabilización de zona, detección de captura, pares y veredicto.
"""

import struct

import zonas_vs_lugares_xy as probe


def _raw(pid=1, species=25, met=0):
    data = bytearray(232)
    struct.pack_into("<I", data, 0, pid)
    struct.pack_into("<H", data, 0x08, species)
    struct.pack_into("<H", data, probe.MET_LOCATION_OFFSET, met)
    return bytes(data)


def _scan(*entries):
    return {
        pid: {"species": sp, "met_raw": met, "met_bridge": bridge}
        for pid, sp, met, bridge in entries
    }


def test_campos_del_pk6():
    raw = _raw(pid=0xDEADBEEF, species=10, met=258)

    assert probe.pid_of(raw) == 0xDEADBEEF
    assert probe.met_location_raw(raw) == 258
    assert probe.met_location_raw(b"\x00" * 10) is None
    assert probe.met_location_raw(None) is None


def test_zona_se_asienta_tras_varias_lecturas_iguales():
    obs = probe.Observador()

    assert obs.feed_zone(258) is None
    assert obs.feed_zone(258) is None
    assert "258" in obs.feed_zone(258)
    assert obs.stable_zone == 258
    # Sin cambio: no repite.
    assert obs.feed_zone(258) is None
    # Una lectura suelta distinta (cruce) no cambia la zona asentada.
    assert obs.feed_zone(259) is None
    assert obs.feed_zone(258) is None
    assert obs.stable_zone == 258
    assert obs.feed_zone(None) is None
    assert obs.zones_seen == [258]


def test_captura_genera_par_zona_lugar():
    obs = probe.Observador()
    obs.baseline_pids = {1: 25}
    obs.stable_zone = 258

    assert obs.feed_counter(10, now=0) is None
    assert "captura detectada" in obs.feed_counter(11, now=1)

    # Aún no aparece el Pokémon nuevo.
    sin_nuevos = obs.feed_scan(_scan((1, 25, 8, 8)), now=2)
    assert len(sin_nuevos) == 1 and "0 nuevo(s)" in sin_nuevos[0]
    assert obs.pending is not None

    events = obs.feed_scan(_scan((1, 25, 8, 8), (2, 16, 8, 8)), now=4)

    assert len(events) == 1 and "zona 258 -> lugar 8" in events[0]
    assert obs.pairs[0]["zona"] == 258 and obs.pairs[0]["lugar"] == 8
    assert obs.pending is None
    assert 2 in obs.baseline_pids


def test_captura_espera_a_que_el_lugar_este_escrito():
    obs = probe.Observador()
    obs.baseline_pids = {}
    obs.stable_zone = 10
    obs.feed_counter(1, now=0)
    obs.feed_counter(2, now=0)

    # El Pokémon ya está pero el juego aún no escribió el lugar.
    sin_lugar = obs.feed_scan(_scan((5, 16, 0, None)), now=1)
    assert len(sin_lugar) == 1 and "campo0xDA=0" in sin_lugar[0]
    assert obs.pairs == [] and obs.pending is not None
    assert obs.feed_scan(_scan((5, 16, 12, 12)), now=3)
    assert obs.pairs[0]["lugar"] == 12


def test_captura_sin_par_por_timeout():
    obs = probe.Observador()
    obs.baseline_pids = {}
    obs.stable_zone = 10
    obs.feed_counter(1, now=0)
    obs.feed_counter(2, now=0)

    events = obs.feed_scan({}, now=probe.CAPTURE_TIMEOUT + 1)

    assert any("SIN par" in e for e in events)
    assert obs.pending is None and obs.pairs == []


def test_la_primera_lectura_del_contador_no_es_captura():
    obs = probe.Observador()

    assert obs.feed_counter(821, now=0) is None
    assert obs.pending is None
    assert obs.feed_counter(None, now=1) is None


def _pair(zona, lugar, fuente="captura", bridge=None, raw=None):
    return {
        "fuente": fuente,
        "zona": zona,
        "lugar": lugar,
        "lugar_bridge": bridge,
        "lugar_campo_0xDA": raw if raw is not None else lugar,
    }


def test_veredicto_sin_datos():
    assert probe.analizar([])["veredicto"] == "SIN_DATOS"
    # Lugar 0 (no escrito) no cuenta.
    assert probe.analizar([_pair(258, 0)])["veredicto"] == "SIN_DATOS"


def test_veredicto_offset_fijo():
    pares = [_pair(258, 8), _pair(260, 10), _pair(262, 12)]
    r = probe.analizar(pares)

    assert r["veredicto"] == "OFFSET_FIJO"
    assert r["deltas_zona_menos_lugar"] == [250]


def test_veredicto_mapeo_consistente_con_varias_zonas_por_lugar():
    pares = [_pair(258, 8), _pair(8, 10), _pair(259, 12), _pair(260, 12)]
    r = probe.analizar(pares, zones_seen=[258, 8, 259, 260, 53])

    assert r["veredicto"] == "MAPEO_CONSISTENTE"
    assert r["lugar_a_zonas"][12] == [259, 260]
    assert r["zonas_vistas_sin_par"] == [53]


def test_veredicto_conflictos():
    r = probe.analizar([_pair(258, 8), _pair(258, 10)])

    assert r["veredicto"] == "CONFLICTOS"
    assert r["conflictos"] == {258: [8, 10]}


def test_rival_con_y_sin_lugar_y_desacuerdo_con_bridge():
    obs = probe.Observador()
    obs.stable_zone = 258
    obs.feed_rival(16, 0, 0.6)
    obs.feed_rival(16, 8, 4.0)

    r = probe.analizar(obs.pairs)

    assert r["rival_con_lugar"] == "1/2"
    assert r["pares_por_fuente"] == {"rival": 1}

    r = probe.analizar([_pair(258, 8, bridge=9, raw=8)])
    assert r["campo_0xDA_distinto_del_bridge"] == 1


def test_resumen_legible():
    r = probe.analizar([_pair(258, 8), _pair(8, 10)], zones_seen=[258, 8])
    texto = probe.format_summary(r)

    assert "MAPEO_CONSISTENTE" in texto
    assert "Ruta 1" in texto and "Pueblo Acuarela" in texto


def test_diagnostico_de_nuevos_sin_lugar_no_se_repite():
    obs = probe.Observador()
    obs.baseline_pids = {1: 25}
    obs.stable_zone = 258
    obs.feed_counter(1, now=0)
    obs.feed_counter(2, now=0)

    scan = _scan((1, 25, 8, None), (2, 16, 0, None))

    primero = obs.feed_scan(scan, now=2)
    segundo = obs.feed_scan(scan, now=4)

    assert len(primero) == 1 and "1 nuevo(s)" in primero[0]
    assert "campo0xDA=0" in primero[0]
    assert segundo == []
    assert obs.pending is not None


def test_agrupar_por_lugar():
    scan = _scan((1, 25, 8, None), (2, 16, 8, None), (3, 4, 0, None))

    assert probe.agrupar_por_lugar(scan) == {0: [3], 8: [1, 2]}


class _FakeMemory:
    def __init__(self, size, base):
        self.base = base
        self.data = bytearray(size)

    def put(self, address, chunk):
        offset = address - self.base
        self.data[offset:offset + len(chunk)] = chunk

    def read(self, address, size):
        offset = address - self.base
        return bytes(self.data[offset:offset + size])


class _FakeReader:
    STRIDE = 0xE8
    SLOTS = 30
    BOX_BASE = 0x1000
    LAST = 0x0F00

    def __init__(self):
        self.memory = _FakeMemory(0x1000 + 31 * 30 * 0xE8, 0)

    def read_pokemon_raw_for_slot(self, slot):
        return None

    def _box_geometry(self):
        return (self.BOX_BASE, self.STRIDE, self.SLOTS)

    def _box_address(self, index):
        return self.BOX_BASE + (index - 1) * self.SLOTS * self.STRIDE

    def _field(self, name):
        return self.LAST if name == "wild_rival_copy_address" else None


def test_escaneo_incluye_cajas_altas_y_ultimo_capturado():
    from test_buscar_party_xy import make_encrypted_pk6

    reader = _FakeReader()
    reader.memory.put(reader._box_address(1), make_encrypted_pk6(25, pv=111))
    # Una caja más allá de la 7ª, slot 3.
    reader.memory.put(
        reader._box_address(12) + 2 * reader.STRIDE,
        make_encrypted_pk6(16, pv=222),
    )
    reader.memory.put(reader.LAST, make_encrypted_pk6(41, pv=333))

    scan = probe.scan_party_and_boxes(reader, None, boxes=31)
    origen = {pid: d["origen"] for pid, d in scan.items()}

    assert origen == {111: "caja 1.1", 222: "caja 12.3", 333: "ultimo_capturado"}

    # Con solo 7 cajas la caja 12 no se ve.
    scan7 = probe.scan_party_and_boxes(reader, None, boxes=7)
    assert 222 not in scan7 and 111 in scan7

    # Sin copia del último capturado.
    sin = probe.scan_party_and_boxes(reader, None, boxes=31, include_last=False)
    assert 333 not in sin


def test_pokemon_en_caja_y_en_ultimo_no_se_duplica():
    from test_buscar_party_xy import make_encrypted_pk6

    reader = _FakeReader()
    reader.memory.put(reader._box_address(8), make_encrypted_pk6(25, pv=555))
    reader.memory.put(reader.LAST, make_encrypted_pk6(25, pv=555))

    scan = probe.scan_party_and_boxes(reader, None, boxes=31)

    assert list(scan) == [555]
    assert scan[555]["origen"] == "caja 8.1"

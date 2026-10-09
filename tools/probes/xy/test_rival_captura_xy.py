"""Lógica pura de rival_captura_xy.py."""

import rival_captura_xy as probe
from test_buscar_party_xy import make_encrypted_pk6


def _window(entries, size=0x1000):
    data = bytearray(size)

    for offset, species in entries:
        raw = make_encrypted_pk6(species)
        data[offset:offset + len(raw)] = raw

    return bytes(data)


BASE = 0x08800000


def test_encuentra_la_especie_pedida_y_ninguna_otra():
    from buscar_party_xy import find_pk6_candidates

    snapshot = _window([(0x100, 661), (0x400, 25)])
    candidates = find_pk6_candidates(snapshot, BASE)

    assert probe.addresses_for_species(candidates, 661) == {BASE + 0x100}
    assert probe.addresses_for_species(candidates, 25) == {BASE + 0x400}


def test_excluye_party_y_cajas_conocidas():
    candidates = [
        (0x08C86200, {"species": 661}),
        (0x08CE1D00, {"species": 661}),
        (0x08800100, {"species": 661}),
    ]

    assert probe.addresses_for_species(candidates, 661) == {0x08800100}


def test_la_interseccion_deja_solo_lo_que_coincide_siempre():
    samples = [
        (661, {0x100, 0x200, 0x300}),
        (25, {0x100, 0x300}),
        (16, {0x100, 0x500}),
    ]

    assert probe.intersect_samples(samples) == [0x100]
    assert probe.intersect_samples([]) == []


def test_comandos():
    assert probe.parse_command("b 661") == ("b", 661)
    assert probe.parse_command("  C 25 ") == ("c", 25)
    assert probe.parse_command("fin") == ("fin", None)
    assert probe.parse_command("borrar") == ("borrar", None)
    assert probe.parse_command("b 9999") is None
    assert probe.parse_command("b Fletchling") is None
    assert probe.parse_command("x 5") is None


def test_el_avance_se_guarda_y_se_retoma(tmp_path):
    path = tmp_path / "estado.json"
    state = {"b": [(661, {0x100, 0x200})], "c": [(25, {0x100})]}

    probe.save_state(state, path)

    assert probe.load_state(path) == state
    assert probe.load_state(tmp_path / "no_existe.json") == {"b": [], "c": []}


def test_el_resumen_avisa_si_rival_y_capturado_comparten_buffer():
    state = {"b": [(661, {0x100, 0x200})], "c": [(25, {0x100})]}

    text = probe.summarize(state)

    assert "0x00000100" in text
    assert "Coinciden en rival y capturado" in text

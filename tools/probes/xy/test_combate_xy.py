"""Lógica pura de combate_xy.py."""

import struct

import combate_xy as probe

BASE = 0x08000000
SIZE = 0x10000


def _battle(cell, struct_base, hp, hp_offset=0x404, extra=()):
    data = bytearray(SIZE)
    struct.pack_into("<H", data, struct_base - BASE + hp_offset, hp)
    struct.pack_into("<I", data, cell - BASE, struct_base)

    for position, value in extra:
        struct.pack_into("<H", data, position - BASE, value)

    return bytes(data)


def test_encuentra_la_celda_y_el_desplazamiento_del_hp():
    snapshot = _battle(0x08000100, 0x08003000, 187)

    found = probe.find_hp_pointers(snapshot, BASE, 187)

    assert found[(0x08000100, 0x404)] == 0x08003000


def test_la_interseccion_deja_el_mismo_desplazamiento_con_base_distinta():
    first = probe.find_hp_pointers(
        _battle(0x08000100, 0x08003000, 187), BASE, 187
    )
    second = probe.find_hp_pointers(
        _battle(0x08000100, 0x08005000, 233), BASE, 233
    )

    common = probe.intersect_samples([(187, first), (233, second)])

    assert (0x08000100, 0x404) in common


def test_una_celda_que_solo_coincide_en_un_combate_se_descarta():
    first = probe.find_hp_pointers(
        _battle(0x08000100, 0x08003000, 187), BASE, 187
    )
    second = probe.find_hp_pointers(
        _battle(0x08000200, 0x08005000, 233), BASE, 233
    )

    common = probe.intersect_samples([(187, first), (233, second)])

    assert (0x08000100, 0x404) not in common
    assert (0x08000200, 0x404) not in common


def test_se_excluye_la_tabla_del_equipo():
    snapshot = bytearray(0x20000)
    start = 0x08CE0000
    struct.pack_into("<H", snapshot, 0x3000 + 0x130, 150)
    struct.pack_into("<I", snapshot, 0x1C6C, start + 0x3000)

    found = probe.find_hp_pointers(bytes(snapshot), start, 150)

    assert all(not (0x08CE1C60 <= cell < 0x08CE1CF0) for cell, _ in found)


def test_un_hp_demasiado_comun_se_rechaza(monkeypatch):
    monkeypatch.setattr(probe, "MAX_HP_HITS", 2)
    snapshot = struct.pack("<HHH", 5, 5, 5) + bytes(0x100)

    try:
        probe.find_hp_pointers(snapshot, BASE, 5)
    except ValueError:
        return

    raise AssertionError("debía rechazar el HP común")


def test_comandos():
    assert probe.parse_command("h 187") == ("h", 187)
    assert probe.parse_command(" H 5 ") == ("h", 5)
    assert probe.parse_command("fin") == ("fin", None)
    assert probe.parse_command("borrar") == ("borrar", None)
    assert probe.parse_command("h 0") is None
    assert probe.parse_command("h abc") is None
    assert probe.parse_command("x 5") is None


def test_el_avance_se_guarda_y_se_retoma(tmp_path):
    path = tmp_path / "estado.json"
    samples = [(187, {(0x08000100, 0x404): 0x08003000})]

    probe.save_state(samples, path)

    assert probe.load_state(path) == samples
    assert probe.load_state(tmp_path / "no_existe.json") == []

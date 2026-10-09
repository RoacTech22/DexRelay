"""Lógica pura de snapshots_xy.py (medallas, zona, contador)."""

import struct

import pytest

import snapshots_xy as probe

START = 0x08C60000
SIZE = 0x400


def _snap(patches, size=SIZE):
    data = bytearray(size)

    for offset, value in patches.items():
        if isinstance(value, bytes):
            data[offset:offset + len(value)] = value
        else:
            data[offset] = value

    return (START, bytes(data))


def test_medallas_encuentra_el_byte_cuyos_bits_crecen():
    snaps = [
        (*_snap({0x10: 0b00000111, 0x20: 0b00000111}), 3),
        (*_snap({0x10: 0b00001111, 0x20: 0b11111110}), 4),
        (*_snap({0x10: 0b00001111, 0x20: 0b11111110}), 4),
    ]

    rows = probe.badge_candidates(snaps)

    assert [address for address, _ in rows] == [START + 0x10]


def test_medallas_descarta_el_byte_que_cambia_en_la_foto_de_control():
    snaps = [
        (*_snap({0x10: 0b0111}), 3),
        (*_snap({0x10: 0b1111}), 4),
        (*_snap({0x10: 0b1011}), 4),
    ]

    assert probe.badge_candidates(snaps) == []


def test_medallas_sin_senal_si_todas_son_cero():
    snaps = [(*_snap({}), 0), (*_snap({}), 0)]

    with pytest.raises(ValueError):
        probe.badge_candidates(snaps)


def test_zona_exige_mismo_valor_en_el_mismo_lugar_y_distinto_en_otro():
    def zone(a, b):
        return _snap({0x30: struct.pack("<H", a), 0x40: struct.pack("<H", b)})

    snaps = [
        (*zone(5, 9), "R5"),
        (*zone(8, 9), "Lumiose"),   # 0x40 no distingue lugares
        (*zone(5, 9), "R5"),
        (*zone(11, 9), "R6"),
    ]

    rows = probe.zone_candidates(snaps, 2)

    assert [address for address, _ in rows] == [START + 0x30]
    assert rows[0][1] == [5, 8, 5, 11]


def test_zona_necesita_un_lugar_repetido():
    snaps = [(*_snap({}), "A"), (*_snap({}), "B")]

    with pytest.raises(ValueError):
        probe.zone_candidates(snaps, 2)


def test_contador_sube_igual_que_el_dato_y_no_cambia_en_el_control():
    def counter(value, noise):
        return _snap({
            0x20: struct.pack("<I", value),
            0x40: struct.pack("<I", noise),
        })

    snaps = [
        (*counter(10, 100), 0),
        (*counter(11, 250), 1),
        (*counter(11, 400), 1),
    ]

    rows = probe.counter_candidates(snaps)

    assert [address for address, _ in rows] == [START + 0x20]
    assert rows[0][1] == [10, 11, 11]


def test_ventanas_distintas_se_rechazan():
    snaps = [(*_snap({}), 1), (*_snap({}, size=SIZE * 2), 2)]

    with pytest.raises(ValueError):
        probe.badge_candidates(snaps)


def test_foto_ida_y_vuelta(tmp_path):
    path = tmp_path / "foto.bin"
    probe.save_snapshot(path, START, b"\x01\x02\x03")

    assert probe.load_snapshot(path) == (START, b"\x01\x02\x03")


def _bag(slots, offset=0x100, size=0x600):
    data = bytearray(size)

    for index, (item_id, quantity) in enumerate(slots):
        struct.pack_into("<HH", data, offset + index * 4, item_id, quantity)

    # lo que hay antes del bolsillo no parece un casillero
    struct.pack_into("<HH", data, offset - 4, 0xFFFF, 0xFFFF)
    return (START, bytes(data))


def test_bolsa_encuentra_los_objetos_juntos_y_el_inicio_del_bolsillo():
    start, data = _bag([(4, 25), (17, 5), (3, 12), (2, 3), (0, 0)])

    rows = probe.bag_candidates(start, data, [(4, 25), (3, 12), (2, 3)])

    assert len(rows) == 1
    assert rows[0]["hits"] == {
        4: START + 0x100,
        3: START + 0x108,
        2: START + 0x10C,
    }
    assert rows[0]["inicio"] == START + 0x100


def test_bolsa_descarta_si_falta_un_objeto_o_esta_lejos():
    start, data = _bag([(4, 25), (3, 12)], size=0x3000)
    far = bytearray(data)
    struct.pack_into("<HH", far, 0x2000, 2, 3)

    assert probe.bag_candidates(start, data, [(4, 25), (2, 3)]) == []
    assert probe.bag_candidates(start, bytes(far), [(4, 25), (2, 3)]) == []


def test_bolsa_exige_cantidad_exacta():
    start, data = _bag([(4, 25)])

    assert probe.bag_candidates(start, data, [(4, 24)]) == []


def _battle_snap(*, hp=None, cell=0, wild_flag=0, hp_at=0x80, cell_at=0x20,
                 flag_at=0x200, size=0x400):
    data = bytearray(size)

    if hp is not None:
        struct.pack_into("<H", data, hp_at, hp)

    struct.pack_into("<I", data, cell_at, cell)
    data[flag_at] = wild_flag
    return (START, bytes(data))


def test_combate_encuentra_hp_fijo_celda_de_combate_y_bandera_salvaje():
    ptr = 0x08203000
    snaps = [
        (*_battle_snap(), ("fuera", None)),
        (*_battle_snap(), ("fuera", None)),
        (*_battle_snap(hp=187, cell=ptr, wild_flag=0), ("entrenador", 187)),
        (*_battle_snap(hp=233, cell=ptr, wild_flag=0), ("entrenador", 233)),
        (*_battle_snap(hp=204, cell=ptr, wild_flag=20), ("salvaje", 204)),
        (*_battle_snap(hp=210, cell=ptr, wild_flag=227), ("salvaje", 210)),
    ]

    result = probe.combat_analysis(snaps)

    assert result["hp"] == [START + 0x80]
    assert result["activo"][0][0] == START + 0x20
    assert result["activo"][0][1] == [ptr] * 4
    assert result["salvaje"] == [(START + 0x200, None)]


def test_combate_descarta_la_celda_que_no_vale_cero_fuera():
    snaps = [
        (*_battle_snap(cell=0x08203000), ("fuera", None)),
        (*_battle_snap(hp=187, cell=0x08203000), ("entrenador", 187)),
    ]

    assert probe.combat_analysis(snaps)["activo"] == []


def test_combate_exige_fotos_fuera_y_de_combate():
    with pytest.raises(ValueError):
        probe.combat_analysis([(*_battle_snap(), ("fuera", None))])


def test_etiquetas_de_combate():
    assert probe.parse_combat_label("fuera") == ("fuera", None)
    assert probe.parse_combat_label("salvaje:204") == ("salvaje", 204)
    assert probe.parse_combat_label("entrenador") == ("entrenador", None)

    for bad in ("fuera:5", "raro", "salvaje:x"):
        with pytest.raises(ValueError):
            probe.parse_combat_label(bad)


def test_combate_celda_con_base_distinta_por_tipo_de_combate():
    # el HP vive en base+0x10 y la bandera en base+0x30 (0 entrenador, !=0 salvaje)
    def snap(base, hp, flag, cell=0x20):
        data = bytearray(0x4000)
        struct.pack_into("<I", data, cell, base)
        struct.pack_into("<H", data, base - START + 0x10, hp)
        data[base - START + 0x30] = flag
        return (START, bytes(data))

    fuera = (START, bytes(0x4000))
    snaps = [
        (*fuera, ("fuera", None)),
        (*snap(0x08C61000, 187, 0), ("entrenador", 187)),
        (*snap(0x08C61000, 233, 0), ("entrenador", 233)),
        (*snap(0x08C62000, 204, 20), ("salvaje", 204)),
        (*snap(0x08C62400, 210, 9), ("salvaje", 210)),
    ]

    result = probe.combat_analysis(snaps)

    assert result["hp"] == []
    address, values, hp_offsets, flag_offsets = result["base"][0]
    assert address == START + 0x20
    assert hp_offsets == [0x10]
    assert [off for off, _ in flag_offsets] == [0x30]

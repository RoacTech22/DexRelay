"""Lógica pura de investigar_trainer_xy.py (clasificación de coincidencias)."""

import struct

import investigar_trainer_xy as probe
from tools.probes.memory.investigar_trainer_id import find_id_and_name_pairs


def _card(tid, sid, name, base=0x100, size=0x400):
    data = bytearray(size)
    struct.pack_into("<HH", data, base, tid, sid)
    encoded = name.encode("utf-16le") + b"\x00\x00"
    data[base + 0x48:base + 0x48 + len(encoded)] = encoded
    return data


def test_encuentra_la_tarjeta_con_nombre_72_bytes_despues_del_id():
    data = _card(58557, 32925, "Mattia")
    hits = find_id_and_name_pairs(bytes(data), 58557, 32925, "Mattia")
    candidates, pk6_like = probe.classify_hits(hits)

    assert candidates == [(0x100, 0x148, 72)]
    assert pk6_like == 0


def test_descarta_las_coincidencias_con_firma_de_pk6():
    data = bytearray(0x400)
    struct.pack_into("<HH", data, 0x40, 58557, 32925)  # TID en 0x0C de un PK6
    encoded = "Mattia".encode("utf-16le") + b"\x00\x00"
    data[0x40 + 0xA4:0x40 + 0xA4 + len(encoded)] = encoded  # OT en 0xB0

    hits = find_id_and_name_pairs(bytes(data), 58557, 32925, "Mattia")
    candidates, pk6_like = probe.classify_hits(hits)

    assert candidates == []
    assert pk6_like == 1


def test_busca_la_tarjeta_sin_conocer_el_sid():
    data = _card(12345, 777, "Ana")

    assert probe.find_card_by_name_and_tid(bytes(data), 12345, "Ana") == [
        (0x100, 0x148, 777)
    ]
    assert probe.find_card_by_name_and_tid(bytes(data), 999, "Ana") == []

"""
Bloque 5 (guía siguiente versión, 23/09/2026): la lógica pura del
probe tools/probes/memory/investigar_trainer_id.py -- extracción de
TID/SID/OT de un PK6 ya descifrado, voto por mayoría y búsqueda de
pares ID+nombre en un volcado de memoria. Los offsets del formato PK6
los usa el probe; que estos tests pasen NO confirma nada sobre la
memoria real de Azahar -- eso lo confirma Ronald corriendo el probe
contra su partida y comparando con la Tarjeta de Entrenador.
"""

import struct

from tools.probes.memory.investigar_trainer_id import (
    PK6_OT_NAME_OFFSET,
    PK6_TID_OFFSET,
    extract_trainer_fields,
    find_id_and_name_pairs,
    vote_trainer,
)


def _fake_pk6(tid, sid, ot, ht=""):
    raw = bytearray(232)
    struct.pack_into("<H", raw, 0x0C, tid)
    struct.pack_into("<H", raw, 0x0E, sid)
    raw[0xB0:0xB0 + 24] = ot.encode("utf-16le").ljust(24, b"\x00")
    raw[0x78:0x78 + 24] = ht.encode("utf-16le").ljust(24, b"\x00")
    raw[0xDF] = 27
    return bytes(raw)


def test_extrae_tid_sid_y_nombre_del_entrenador():
    fields = extract_trainer_fields(_fake_pk6(12345, 54321, "Ronald"))

    assert fields["tid"] == 12345
    assert fields["sid"] == 54321
    assert fields["ot"] == "Ronald"
    assert fields["ht"] == ""
    assert fields["tid7"] == ((54321 << 16) | 12345) % 1_000_000


def test_estructura_demasiado_corta_devuelve_none():
    assert extract_trainer_fields(b"\x00" * 10) is None


def test_voto_prefiere_el_entrenador_mas_repetido():
    mine = extract_trainer_fields(_fake_pk6(111, 222, "Ronald"))
    traded = extract_trainer_fields(_fake_pk6(999, 888, "Otro", "Ronald"))

    winner, votes, total = vote_trainer([mine, mine, traded, mine])

    assert winner == (111, 222, "Ronald")
    assert votes == 3
    assert total == 4


def test_voto_sin_pokemon_devuelve_none():
    assert vote_trainer([]) is None
    assert vote_trainer([None]) is None


def test_busca_par_id_nombre_y_distingue_la_firma_de_un_pk6():
    data = bytearray(0x400)

    # Una "tarjeta de entrenador" hipotética: ID en 0x100 y nombre a
    # +0x48 (no confirmado, solo un caso de prueba).
    struct.pack_into("<HH", data, 0x100, 111, 222)
    data[0x148:0x148 + 14] = "Ronald".encode("utf-16le") + b"\x00\x00"

    # Un PK6 suelto (firma: nombre a +0xA4 del TID).
    struct.pack_into("<HH", data, 0x200 + PK6_TID_OFFSET, 111, 222)
    name_at = 0x200 + PK6_OT_NAME_OFFSET
    data[name_at:name_at + 14] = "Ronald".encode("utf-16le") + b"\x00\x00"

    hits = find_id_and_name_pairs(bytes(data), 111, 222, "Ronald")
    distances = sorted(name - ident for ident, name in hits)

    assert 0x48 in distances
    assert PK6_OT_NAME_OFFSET - PK6_TID_OFFSET in distances

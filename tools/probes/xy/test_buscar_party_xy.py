"""
Pruebas de la lógica pura de buscar_party_xy.py (sin Azahar): el
escaneo por checksum PK6, el agrupado por stride y la búsqueda de
punteros. Para armar un PK6 cifrado de prueba se invierte
decrypt_data() (checksum = suma de las palabras de los 4 bloques,
que no depende del orden; el cifrado es un XOR con un LCG).
"""

import struct

import buscar_party_xy as probe
from app.memory.structures import BLOCK_SIZE, crypt_array, decrypt_data, shuffle_array


def _permutation(sv):
    """Qué bloque físico va a cada posición lógica, para el valor `sv`."""
    marked = b"".join(bytes([i]) * BLOCK_SIZE for i in range(4))
    shuffled = shuffle_array(marked, sv, BLOCK_SIZE)
    return [shuffled[i * BLOCK_SIZE] for i in range(4)]


def make_encrypted_pk6(species, nickname="TEST", tid=1234, sid=5678, pv=0x12345678):
    blocks = bytearray(4 * BLOCK_SIZE)
    struct.pack_into("<H", blocks, 0x08 - 8, species)
    struct.pack_into("<HH", blocks, 0x0C - 8, tid, sid)
    name = nickname.encode("utf-16le")
    blocks[0x40 - 8:0x40 - 8 + len(name)] = name

    checksum = sum(struct.unpack("<112H", bytes(blocks))) & 0xFFFF
    header = struct.pack("<IHH", pv, 0, checksum)

    sv = ((pv >> 0xD) & 0x1F) % 24
    permutation = _permutation(sv)
    physical = bytearray(4 * BLOCK_SIZE)

    for logical, source in enumerate(permutation):
        physical[source * BLOCK_SIZE:(source + 1) * BLOCK_SIZE] = blocks[
            logical * BLOCK_SIZE:(logical + 1) * BLOCK_SIZE
        ]

    encrypted_blocks = crypt_array(header + bytes(physical), pv, 8, 8 + 4 * BLOCK_SIZE)
    return header + encrypted_blocks


def test_el_pk6_de_prueba_se_descifra_con_el_decoder_real():
    raw = make_encrypted_pk6(species=650, nickname="Chespin")
    decrypted = decrypt_data(raw)

    assert decrypted
    assert probe.decode_candidate(decrypted)["species"] == 650
    assert probe.decode_candidate(decrypted)["nickname"] == "Chespin"


def test_encuentra_pokemon_dentro_de_memoria_con_ruido():
    pk = make_encrypted_pk6(species=653, nickname="Fennekin", pv=0x0BADF00D)
    noise = bytes((i * 31 + 7) & 0xFF for i in range(0x400))
    snapshot = noise + pk + noise

    found = probe.find_pk6_candidates(snapshot, 0x08000000)

    assert [(a, d["species"], d["nickname"]) for a, d in found] == [
        (0x08000000 + len(noise), 653, "Fennekin")
    ]


def test_ignora_checksum_invalido_y_especie_fuera_de_gen6():
    corrupto = bytearray(make_encrypted_pk6(species=650))
    corrupto[0x20] ^= 0xFF
    fuera_de_rango = make_encrypted_pk6(species=900)

    assert probe.find_pk6_candidates(bytes(corrupto), 0) == []
    assert probe.find_pk6_candidates(fuera_de_rango, 0) == []


def test_grupo_con_stride_constante_de_party_contigua():
    base = 0x08CE0000
    party = [base + i * 0x104 for i in range(6)]
    suelto = [base - 0x5000, base + 0x9000]

    groups = probe.group_by_stride(party + suelto)

    assert groups == [(0x104, party)]


def test_no_agrupa_menos_de_tres():
    assert probe.group_by_stride([0x1000, 0x1104]) == []


def test_busca_punteros_a_la_estructura_y_a_estructura_menos_0x40():
    target_a, target_b = 0x08F00100, 0x08F00300
    snapshot = bytearray(0x100)
    struct.pack_into("<I", snapshot, 0x10, target_a - 0x40)  # convención ORAS
    struct.pack_into("<I", snapshot, 0x14, target_b)  # puntero directo
    struct.pack_into("<I", snapshot, 0x31, target_a - 0x40)  # desalineado: se ignora

    refs = probe.find_pointer_refs(bytes(snapshot), 0x08000000, [target_a, target_b])

    assert refs[target_a] == [(0x08000010, 0x40)]
    assert refs[target_b] == [(0x08000014, 0x0)]


def test_tabla_de_punteros_consecutivos():
    table = [0x08000100 + i * 4 for i in range(6)]

    assert probe.group_consecutive_pointers(table) == [(4, table)]
    assert probe.group_consecutive_pointers([0x08000100, 0x08005000, 0x08009000]) == []

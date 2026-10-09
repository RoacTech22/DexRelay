"""P5: escritura del Caramelo Raro en X/Y (bolsillo de Medicina medido)."""

import struct

from app.games.registry import get_profile
from app.services.bag_service import (
    RARE_CANDY_ITEM_ID,
    BagService,
    BagWriteError,
)

MED = 0x08C67ECC
BERRIES = 0x08C67FCC


class _Mem:
    def __init__(self, base, data):
        self.base, self.data = base, bytearray(data)

    def read(self, addr, size):
        o = addr - self.base
        return bytes(self.data[o:o + size])


class _Citra:
    def __init__(self, mem):
        self.mem, self.writes = mem, []

    def write_memory(self, addr, content):
        o = addr - self.mem.base
        self.mem.data[o:o + len(content)] = content
        self.writes.append(addr)
        return True


class _Reader:
    process_name = "kujira-2"

    def __init__(self, medicine, berries_first=(149, 995)):
        base = MED
        data = bytearray(0x100 + 0x40)
        for i, (item, qty) in enumerate(medicine):
            struct.pack_into("<HH", data, i * 4, item, qty)
        struct.pack_into("<HH", data, 0x100, *berries_first)
        self.memory = _Mem(base, data)
        self.citra = _Citra(self.memory)
        self.profile = get_profile("kujira-2")

    def is_connected(self):
        return True


def _slot(reader, addr):
    return struct.unpack("<HH", reader.memory.read(addr, 4))


def test_perfil_xy_tiene_medicina_de_64_casilleros_que_termina_en_bayas():
    for key in ("kujira-1", "kujira-2"):
        p = get_profile(key)
        assert p.capabilities.has_bag_writing is True
        m = p.memory_map
        assert m.medicine_pocket_start_address == MED
        assert m.medicine_pocket_slot_count == 64
        assert MED + 64 * 4 == BERRIES


def test_suma_a_caramelo_existente():
    r = _Reader([(17, 5), (RARE_CANDY_ITEM_ID, 10)])
    res = BagService(r).add_medicine_item(RARE_CANDY_ITEM_ID, 3)
    assert res == {"address": MED + 4, "item_id": 50, "new_quantity": 13}
    assert _slot(r, MED + 4) == (50, 13)


def test_usa_primer_casillero_vacio_del_bolsillo():
    r = _Reader([(17, 5), (28, 2)])
    res = BagService(r).add_medicine_item(RARE_CANDY_ITEM_ID, 1)
    assert res["address"] == MED + 8
    assert _slot(r, MED + 8) == (50, 1)
    assert _slot(r, BERRIES) == (149, 995)


def test_bolsillo_lleno_no_cruza_a_las_bayas():
    lleno = [(100 + i, 1) for i in range(64)]
    r = _Reader(lleno)
    try:
        BagService(r).add_medicine_item(RARE_CANDY_ITEM_ID, 1)
        assert False, "debía fallar"
    except BagWriteError:
        pass
    assert r.citra.writes == []
    assert _slot(r, BERRIES) == (149, 995)


def test_oras_conserva_ventana_legada():
    p = get_profile("sango-2")
    assert p.memory_map.medicine_pocket_slot_count is None
    assert p.capabilities.has_bag_writing is True

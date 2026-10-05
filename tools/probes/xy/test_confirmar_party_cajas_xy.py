"""
Prueba de confirmar_party_cajas_xy.py sin Azahar: una memoria falsa con la
MISMA disposición que mostró X (tabla de 6 punteros a Pokémon-0x40, buffer
de stride 0x1E4, cajas contiguas de stride 0xE8) y el reader real leyendo
con un perfil temporal.
"""

import struct

import confirmar_party_cajas_xy as probe
from app.games import registry
from app.readers.azahar_reader import AzaharReader
from test_buscar_party_xy import make_encrypted_pk6

TABLE = 0x08CE1C6C
BUFFER = 0x08CE1CF8
BOX_BASE = 0x08C861C8
SPECIES = [658, 663, 673, 681, 706, 716]


class FakeMemory:
    def __init__(self):
        self.mem = {}

    def write(self, address, data):
        for i, byte in enumerate(data):
            self.mem[address + i] = byte

    def read(self, address, size):
        return bytes(self.mem.get(address + i, 0) for i in range(size))


def _world(party_count=6):
    memory = FakeMemory()

    for slot, species in enumerate(SPECIES):
        pokemon_address = BUFFER + slot * 0x1E4
        memory.write(TABLE + slot * 4, struct.pack("<I", pokemon_address - 0x40))
        pk = make_encrypted_pk6(species, nickname=f"P{slot}", pv=0x1000 + slot)
        stats = bytes([0] * 0x10 + [50 + slot]) + bytes(5)  # relleno, nivel en 0x10
        memory.write(pokemon_address, pk + stats)

    memory.write(TABLE + 0x18, bytes([party_count]))

    for index in range(70):  # Cajas 1..3 llenas, contiguas sin padding
        address = BOX_BASE + index * probe.BOX_SLOT_STRIDE
        memory.write(address, make_encrypted_pk6(650 + index % 70, nickname=f"B{index}", pv=0x2000 + index))

    return memory


def _reader(monkeypatch, memory):
    profile = probe.build_temp_profile(
        "kujira-test", TABLE, TABLE + 0x18, BOX_BASE
    )
    monkeypatch.setitem(registry._PROFILES, profile.key, profile)

    class NoCitra:
        def process_list(self):
            return {}

    reader = AzaharReader(
        citra=NoCitra(),
        species_resolver=object(),
        location_resolver=object(),
        process_name="kujira-test",
    )
    reader.memory = memory
    return reader


def test_la_party_se_lee_por_la_tabla_de_punteros(monkeypatch):
    reader = _reader(monkeypatch, _world())

    assert [p.species_id() for p in map(reader.read_pokemon, reader.read_party_order())] == SPECIES


def test_la_cantidad_candidata_vacia_los_slots_sobrantes(monkeypatch):
    reader = _reader(monkeypatch, _world(party_count=2))
    pointers = reader.read_party_order()

    assert [bool(p) for p in pointers] == [True, True, False, False, False, False]


def test_las_cajas_son_contiguas_sin_padding_entre_cajas(monkeypatch):
    reader = _reader(monkeypatch, _world())

    caja2_slot1 = probe.read_box_slot(reader, 2, 1)
    caja1_slot30 = probe.read_box_slot(reader, 1, 30)

    assert caja1_slot30.nickname() == "B29"
    assert caja2_slot1.nickname() == "B30"  # inmediatamente después del slot 30


def test_read_state_describe_party_cantidad_y_cajas(monkeypatch):
    reader = _reader(monkeypatch, _world())
    text = "\n".join(probe.read_state(reader, TABLE + 0x18, TABLE))

    assert "slot 1: puntero 0x08CE1CB8" in text
    assert "#658" in text and "#716" in text
    assert "Cantidad candidata en 0x08CE1C84: 6" in text
    assert "Caja 2 slot  1" in text

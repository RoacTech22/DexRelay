"""
Bloque 12 (ruta multijuego, 04/10/2026): AzaharReader lee TODAS sus
direcciones del perfil del juego conectado y trata un juego sin perfil
(o un campo sin confirmar) como lectura fallida, en vez de caer en
silencio a las direcciones de Alpha Sapphire.
"""

import struct

import pytest

from app.games import registry
from app.games.base import GameCapabilities, GameContent, GameProfile, MemoryMap
from app.games.oras.profile import ALPHA_SAPPHIRE
from app.memory.structures import Pokemon6
from app.readers.azahar_reader import AzaharReader
from app.readers.base import EmulatorTransport
from app.readers.citra import Citra


class FakeCitra:
    def __init__(self, processes=None):
        self._processes = processes or {}

    def process_list(self):
        return self._processes


class FakeMemory:
    """Memoria sparse {dirección: bytes}; registra cada lectura."""

    def __init__(self, regions=None):
        self.regions = regions or {}
        self.reads = []

    def read(self, address, size):
        self.reads.append((address, size))
        region = self.regions.get(address)

        if region is None:
            return None

        return region[:size].ljust(size, b"\x00")


def _reader(process_name, regions=None):
    reader = AzaharReader(citra=FakeCitra(), process_name=process_name)
    reader.memory = FakeMemory(regions)
    return reader


def _trainer_card(tid=23756, sid=50341, name="Ronii"):
    card = bytearray(0x60)
    struct.pack_into("<HH", card, 0x00, tid, sid)
    encoded = name.encode("utf-16le")
    card[0x48:0x48 + len(encoded)] = encoded
    return bytes(card)


def test_citra_cumple_el_contrato_de_transporte():
    assert isinstance(Citra(), EmulatorTransport)


@pytest.mark.parametrize("process_name", ["sango-1", "sango-2"])
def test_oras_lee_con_las_direcciones_de_su_perfil(process_name):
    m = ALPHA_SAPPHIRE.memory_map
    reader = _reader(
        process_name,
        {
            m.trainer_card_address: _trainer_card(),
            m.current_zone_id_address: bytes([42]),
            m.total_caught_address: struct.pack("<I", 9),
        },
    )

    assert reader.read_trainer_identity() == {
        "tid": 23756,
        "sid": 50341,
        "ot": "Ronii",
    }
    assert reader.read_current_zone_id() == 42
    assert reader.read_total_caught_count() == 9


def test_oras_cajas_usan_la_geometria_del_perfil():
    m = ALPHA_SAPPHIRE.memory_map
    reader = _reader("sango-1", {m.box_base_address: b"\x00" * (7 * 30 * 232)})

    assert reader.read_boxes_range() == []
    assert reader.memory.reads == [(0x08C9E134, 7 * 30 * 232)]
    assert reader._box_address(2) == 0x08C9E134 + 30 * 232


def test_oras_detecta_pokeballs_en_el_bolsillo_de_objetos():
    m = ALPHA_SAPPHIRE.memory_map
    pocket = bytearray(m.items_pocket_slot_count * 4)
    struct.pack_into("<HH", pocket, 8, 4, 5)  # Poké Ball x5
    reader = _reader("sango-2", {m.items_pocket_start_address: bytes(pocket)})

    assert reader.read_has_pokeballs() is True


@pytest.mark.parametrize("process_name", ["juego-desconocido", "momiji", None])
def test_juego_sin_perfil_no_lee_memoria_ni_cae_a_alpha_sapphire(process_name):
    reader = _reader(process_name)

    assert reader.profile is None
    assert reader.read_party_order() == []
    assert reader.read_trainer_identity() is None
    assert reader.read_current_zone_id() is None
    assert reader.read_total_caught_count() is None
    assert reader.read_has_pokeballs() is None
    assert reader.read_last_caught() is None
    assert reader.read_wild_rival_species() is None
    assert reader.read_boxes_range() == []
    assert reader.read_box_raw(1) is None
    assert reader.read_box_slot_raw(1, 1) is None
    assert reader.memory.reads == []


def test_campo_sin_confirmar_se_trata_como_lectura_fallida(monkeypatch):
    perfil = GameProfile(
        key="juego-de-prueba",
        display_name="Juego de prueba",
        reader_kind="azahar",
        pokemon_format=Pokemon6,
        memory_map=MemoryMap(
            trainer_card_address=0x08000000,
            trainer_card_read_size=0x60,
            trainer_card_id_offset=0,
            trainer_card_name_offset=0x48,
            trainer_card_name_bytes=24,
        ),
        capabilities=GameCapabilities(),
        content=GameContent(),
    )
    monkeypatch.setitem(registry._PROFILES, perfil.key, perfil)

    reader = _reader(perfil.key, {0x08000000: _trainer_card()})

    assert reader.read_trainer_identity()["tid"] == 23756
    assert reader.read_current_zone_id() is None
    assert reader.read_total_caught_count() is None
    assert reader.read_party_order() == []
    assert reader.read_boxes_range() == []
    # solo se leyó la tarjeta de entrenador: ninguna otra dirección
    assert reader.memory.reads == [(0x08000000, 0x60)]


def test_diagnostico_juego_reconocido_sin_perfil():
    # Pokémon Sun: reconocido por Title ID, todavía sin perfil.
    citra = FakeCitra({11: (0x0004000000164800, "momiji")})
    result = AzaharReader(citra=citra, process_name=None).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_UNSUPPORTED_GAME
    assert result["game_name"] == "Pokémon Sun"
    assert result["process_name"] == "momiji"


def test_diagnostico_con_un_juego_soportado_tiene_prioridad():
    citra = FakeCitra(
        {
            1: (0x0004000000164800, "momiji"),
            2: (0x000400000011C400, "sango-1"),
        }
    )
    result = AzaharReader(citra=citra, process_name=None).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_GAME_FOUND
    assert result["process_name"] == "sango-1"


def test_diagnostico_proceso_desconocido_sigue_siendo_no_game():
    citra = FakeCitra({1: (0x0004001000021000, "otra-cosa")})
    result = AzaharReader(citra=citra, process_name=None).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_NO_GAME
    assert result["processes"] == ["otra-cosa"]

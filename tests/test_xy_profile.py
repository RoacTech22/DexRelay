"""
Bloque 15 (ruta multijuego): perfiles de Pokémon X e Y.

Comprueba que el reader y el servicio de combate usan los valores de X/Y
(zona u16, celda de combate que vale 0 fuera de combate, HP en +0x10,
tipo de combate por el valor de la celda) y que nada de eso afecta a ORAS.
"""

import struct

import pytest

from app.games.oras.profile import ALPHA_SAPPHIRE
from app.games.registry import get_profile
from app.games.xy.profile import POKEMON_X, POKEMON_Y
from app.services.combat_service import LECTURA_DESCARTADA, CombatService
from app.services.kalos_zone_names import resolve_zone_name
from tests.test_reader_profile import _reader, _trainer_card


class Memory:
    def __init__(self, cells):
        self.cells = cells

    def read(self, address, size):
        data = self.cells.get(address)

        if data is None:
            return b"\x00" * size

        return data[:size].ljust(size, b"\x00")


def _combat(profile, cells):
    return CombatService(Memory(cells), profile_provider=lambda: profile)


WILD_BASE = 0x08203EC8
TRAINER_BASE = 0x082059D8


def _cells(base, hp=274, phase=0):
    m = POKEMON_X.memory_map

    return {
        m.combat_pointer_address: struct.pack("<I", base),
        # Byte de fase (+0xFF7): cambia durante el combate y NO decide el tipo.
        base + 0xFF7: bytes([phase]),
        base + m.combat_hp_offset: struct.pack("<H", hp),
    }


def test_valores_de_x_y_investigados():
    m = POKEMON_X.memory_map

    assert m.trainer_card_address == 0x08C79C3C
    assert (m.party_order_address, m.party_count_address) == (0x08CE1C6C, 0x08CE1C84)
    assert (m.box_base_address, m.box_slot_stride, m.box_slot_count) == (
        0x08C861C8, 0xE8, 30,
    )
    assert m.badges_address == 0x08C6A6B0
    assert (m.current_zone_id_address, m.current_zone_id_width) == (0x08C670AE, 2)
    assert m.total_caught_address == 0x08C82AC0
    assert m.last_caught_address == 0x08805614
    assert m.wild_rival_addresses == (0x081FEBA0, 0x081FF744, 0x08805614)
    assert m.combat_pointer_address == 0x081FB304
    assert m.combat_hp_offset == 0x10
    assert m.wild_battle_flag_offset is None
    assert m.wild_battle_pointers == frozenset({0x08203EC8})
    assert m.trainer_battle_pointers == frozenset({0x082059D8})
    assert m.combat_inactive_pointers == (0,)
    assert POKEMON_X.memory_map == POKEMON_Y.memory_map


def test_oras_conserva_su_ancho_de_zona_y_valores_inactivos():
    m = ALPHA_SAPPHIRE.memory_map

    assert m.current_zone_id_width == 1
    assert m.combat_inactive_pointers == (0, 0x083F8658 - 4)


@pytest.mark.parametrize("process_name", ["kujira-1", "kujira-2"])
def test_zona_de_xy_se_lee_como_u16(process_name):
    address = get_profile(process_name).memory_map.current_zone_id_address
    reader = _reader(process_name, {address: struct.pack("<H", 0x0123)})

    assert reader.read_current_zone_id() == 0x0123
    assert reader.memory.reads == [(address, 2)]


def test_zona_de_oras_sigue_leyendo_un_byte():
    address = ALPHA_SAPPHIRE.memory_map.current_zone_id_address
    reader = _reader("sango-2", {address: bytes([23])})

    assert reader.read_current_zone_id() == 23
    assert reader.memory.reads == [(address, 1)]


@pytest.mark.parametrize("process_name", ["kujira-1", "kujira-2"])
def test_tarjeta_de_entrenador_de_xy(process_name):
    address = get_profile(process_name).memory_map.trainer_card_address
    reader = _reader(process_name, {address: _trainer_card(58557, 32925, "Mattia")})

    assert reader.read_trainer_identity() == {
        "tid": 58557,
        "sid": 32925,
        "ot": "Mattia",
    }


def test_combate_fuera_de_combate_la_celda_vale_cero():
    service = _combat(POKEMON_X, {})

    assert service.read() is None
    assert service.read_wild_flag() is None


def test_combate_salvaje_y_de_entrenador_de_xy():
    salvaje = _combat(POKEMON_X, _cells(WILD_BASE, hp=274))
    entrenador = _combat(POKEMON_X, _cells(TRAINER_BASE, hp=238))

    assert salvaje.read() == 274
    assert salvaje.read_wild_flag() is True
    assert entrenador.read() == 238
    assert entrenador.read_wild_flag() is False


def test_el_tipo_se_conoce_desde_el_primer_instante_sin_importar_la_fase():
    # Reproduce lo visto en vivo: durante la animación el byte de fase vale
    # 0 (o basura como 169/17) y el tipo ya debe ser el correcto.
    for phase in (0, 17, 128, 169, 192):
        assert _combat(POKEMON_X, _cells(WILD_BASE, phase=phase)).read_wild_flag() is True
        assert _combat(POKEMON_X, _cells(TRAINER_BASE, phase=phase)).read_wild_flag() is False


def test_base_desconocida_no_se_clasifica():
    # Horda, doble, Safari de Amigos...: si la base no está en el perfil no
    # se adivina (devolver "entrenador" o "salvaje" sería inventar).
    service = _combat(POKEMON_X, _cells(0x08209999))

    assert service.read_wild_flag() is LECTURA_DESCARTADA
    assert service.read() == 274  # el HP sí se lee: es un combate real


def test_combate_de_xy_no_usa_el_valor_inactivo_de_oras():
    # En ORAS (celda - 4) significa "sin combate"; en X/Y es un puntero
    # normal si algún día la celda lo tuviera.
    inactivo_oras = 0x083F8658 - 4
    cells = _cells(inactivo_oras)

    assert _combat(POKEMON_X, cells).read() == 274


def test_sin_perfil_o_sin_combate_confirmado_no_hay_combate():
    assert _combat(None, {}).read() is None
    assert _combat(None, {}).read_wild_flag() is None
    assert _combat(None, {}).read_combat_base_pointer() is None

    from app.games.base import GameProfile, MemoryMap
    from app.memory.structures import Pokemon6

    sin_combate = GameProfile(
        key="x", display_name="x", reader_kind="azahar",
        pokemon_format=Pokemon6, memory_map=MemoryMap(),
    )

    assert _combat(sin_combate, {}).read() is None
    assert _combat(sin_combate, {}).read_wild_flag() is None


def test_lectura_inconsistente_se_descarta_tambien_en_xy():
    class Cambiante(Memory):
        def __init__(self, cells):
            super().__init__(cells)
            self.n = 0

        def read(self, address, size):
            if address == POKEMON_X.memory_map.combat_pointer_address:
                self.n += 1
                return struct.pack("<I", 0x082059D8 + (self.n % 2) * 4)
            return super().read(address, size)

    service = CombatService(Cambiante({}), profile_provider=lambda: POKEMON_X)

    assert service.read() is LECTURA_DESCARTADA


def test_xy_con_arte_catalogo_y_zonas_pero_sin_resto_del_contenido_de_kalos():
    caps = POKEMON_X.capabilities

    assert caps.has_badge_art is True
    assert caps.has_location_catalog is True
    assert caps.has_zone_names is True
    assert caps.has_leader_data is False
    assert caps.has_bag_writing is False
    assert caps.has_hackroom is False
    assert POKEMON_X.content.locations is not None
    assert POKEMON_X.content.zone_name_resolver is resolve_zone_name
    assert POKEMON_Y.content.zone_name_resolver is resolve_zone_name
    assert ALPHA_SAPPHIRE.capabilities.has_badge_art is True

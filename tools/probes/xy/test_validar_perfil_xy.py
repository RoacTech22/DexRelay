"""Lógica pura de validar_perfil_xy.py (sin Azahar)."""

import struct

import validar_perfil_xy as probe
from app.services.combat_service import LECTURA_DESCARTADA


def test_describe_el_estado_de_combate():
    assert probe.describe_combat(None) == "sin combate"
    assert probe.describe_combat(True) == "SALVAJE"
    assert probe.describe_combat(False) == "ENTRENADOR"
    assert probe.describe_combat(LECTURA_DESCARTADA) == "lectura descartada"


def test_lee_u16_o_none():
    class Reader:
        class memory:
            @staticmethod
            def read(address, size):
                return struct.pack("<H", 0x0123) if address == 0x10 else None

    assert probe.read_u16(Reader, 0x10) == 0x0123
    assert probe.read_u16(Reader, 0x20) is None
    assert probe.read_u16(Reader, None) is None

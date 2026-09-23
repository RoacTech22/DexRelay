"""
Bug real reportado por Ronald el 23/09/2026: un "perdido" se
registró solo (flag salvaje = SALVAJE) con el jugador ni siquiera
dentro de una partida cargada. El puntero de combate real logueado
fue 0x01023445 -- muy por debajo de 0x08000000, donde caen TODAS
las direcciones ya confirmadas de este proyecto (ver el comentario
junto a MIN_PLAUSIBLE_COMBAT_POINTER en combat_service.py).
"""

import struct

from app.services.combat_service import (
    COMBAT_HP_OFFSET,
    COMBAT_POINTER_ADDRESS,
    MIN_PLAUSIBLE_COMBAT_POINTER,
    WILD_BATTLE_FLAG_OFFSET,
    CombatService,
)


class FakeMemoryReader:
    """Memoria en un dict {dirección: bytes}, sin Azahar real."""

    def __init__(self, memory: dict):
        self.memory = memory

    def read(self, address, size):
        data = self.memory.get(address)

        if data is None:
            return b"\x00" * size

        return data[:size]


def _memory_with_pointer(base_address, flag_byte=0x01, hp_value=50):
    return {
        COMBAT_POINTER_ADDRESS: struct.pack("<I", base_address),
        base_address + WILD_BATTLE_FLAG_OFFSET: bytes([flag_byte]),
        base_address + COMBAT_HP_OFFSET: struct.pack("<H", hp_value),
    }


def test_puntero_implausible_como_el_reportado_se_trata_como_sin_combate():
    # El valor real logueado por Ronald (0x01023445).
    memory = _memory_with_pointer(0x01023445, flag_byte=0x01, hp_value=50)
    service = CombatService(FakeMemoryReader(memory))

    assert service.read_wild_flag() is None
    assert service.read() is None


def test_puntero_plausible_con_flag_salvaje_se_lee_normal():
    base_address = MIN_PLAUSIBLE_COMBAT_POINTER + 0x1000
    memory = _memory_with_pointer(base_address, flag_byte=0x01, hp_value=77)
    service = CombatService(FakeMemoryReader(memory))

    assert service.read_wild_flag() is True
    assert service.read() == 77


def test_puntero_plausible_con_flag_entrenador_se_lee_normal():
    base_address = MIN_PLAUSIBLE_COMBAT_POINTER + 0x1000
    memory = _memory_with_pointer(base_address, flag_byte=0x00, hp_value=30)
    service = CombatService(FakeMemoryReader(memory))

    assert service.read_wild_flag() is False
    assert service.read() == 30


def test_el_piso_es_inclusivo():
    memory = _memory_with_pointer(MIN_PLAUSIBLE_COMBAT_POINTER, flag_byte=0x01)
    service = CombatService(FakeMemoryReader(memory))

    assert service.read_wild_flag() is True


def test_un_valor_menos_que_el_piso_se_rechaza():
    memory = _memory_with_pointer(MIN_PLAUSIBLE_COMBAT_POINTER - 1, flag_byte=0x01)
    service = CombatService(FakeMemoryReader(memory))

    assert service.read_wild_flag() is None


def test_read_combat_base_pointer_devuelve_el_valor_crudo_sin_filtrar():
    # A propósito NO aplica el guard de plausibilidad -- es
    # diagnóstico puro, tiene que devolver el valor tal cual esté
    # en memoria, plausible o no, para poder verlo en el log.
    memory = {COMBAT_POINTER_ADDRESS: struct.pack("<I", 0x01023445)}
    service = CombatService(FakeMemoryReader(memory))

    assert service.read_combat_base_pointer() == 0x01023445


if __name__ == "__main__":
    test_puntero_implausible_como_el_reportado_se_trata_como_sin_combate()
    test_puntero_plausible_con_flag_salvaje_se_lee_normal()
    test_puntero_plausible_con_flag_entrenador_se_lee_normal()
    test_el_piso_es_inclusivo()
    test_un_valor_menos_que_el_piso_se_rechaza()
    test_read_combat_base_pointer_devuelve_el_valor_crudo_sin_filtrar()
    print("OK - todos los tests del guard de plausibilidad del puntero de combate pasaron")

"""
Etapa 0 de la ruta multijuego (03/10/2026): prueba "golden" de
direcciones y constantes de ORAS.

Congela las direcciones y constantes de ORAS para Omega Ruby
(sango-1) y Alpha Sapphire (sango-2), más los slugs de
almacenamiento y el Title ID usado para ubicar el save. Los valores
se generaron leyendo el código ANTES del refactor del Bloque 11; si
algún bloque posterior cambia cualquiera de ellos, esta prueba falla.

P9 (09/10/2026): app/memory/pointers.py se retiró (queda archivado
como tools/probes/legacy_pointers.py solo para los probes). Los mismos
valores históricos ahora se comprueban contra el MemoryMap de cada
perfil; ya no existe el comportamiento "proceso desconocido cae a
Alpha Sapphire".

Por qué existe: mover estas direcciones a app/games/oras/profile.py
no debe cambiar ni un byte de lo que lee DexRelay en ORAS, y los
slugs de almacenamiento no deben cambiar nunca (los archivos
nuzlocke_alpha_sapphire_<tid>_<sid>.json de los usuarios dependen
de ellos).
"""

from app.games.registry import get_profile
import app.services.combat_service as combat_service
import app.services.nuzlocke_storage as nuzlocke_storage
import app.services.save_file_locator as save_file_locator
from app.readers.azahar_reader import KNOWN_PROCESS_NAMES

ORAS_PROCESSES = ("sango-1", "sango-2")

# Campo del MemoryMap -> valor congelado (igual en sango-1 y sango-2).
MEMORY_MAP = {
    "badges_address": 0x8c71dc4,
    "bag_end_address": 0x8c6f800,
    "bag_start_address": 0x8c6ec70,
    "box_base_address": 0x8c9e134,
    "box_slot_stride": 232,
    "box_slot_count": 30,
    "capture_buffer_address": 0x8804a94,
    "capture_buffer_entry_stride": 484,
    "current_zone_id_address": 0x8c6e7a2,
    "current_zone_id_mirror_address": 0x8c6e884,
    "items_pocket_start_address": 0x8c6ec70,
    "items_pocket_slot_count": 400,
    "wild_rival_copy_address": 0x8805638,
    "medicine_pocket_start_address": 0x8c6f5e0,
    "party_count_address": 0x8cfb1f8,
    "party_order_address": 0x8cfb1e0,
    "total_caught_address": 0x8c8b28c,
    "trainer_card_address": 0x8c81340,
    "trainer_card_read_size": 96,
    "trainer_card_id_offset": 0,
    "trainer_card_name_offset": 72,
    "trainer_card_name_bytes": 24,
    "wild_rival_addresses": (0x81feec8, 0x81ffa6c, 0x8805638),
    "pokeball_item_ids": frozenset(range(1, 17)),
}
COMBAT = {
    "COMBAT_POINTER_ADDRESS": 0x83f8658,
    "COMBAT_HP_OFFSET": 1028,
    "WILD_BATTLE_FLAG_OFFSET": 2175,
    "COMBAT_INACTIVE_POINTER": 0x83f8654,
    "MIN_PLAUSIBLE_COMBAT_POINTER": 0x8000000,
}


def test_direcciones_de_oras_no_cambian():
    for process in ORAS_PROCESSES:
        memory_map = get_profile(process).memory_map

        for name, value in MEMORY_MAP.items():
            assert getattr(memory_map, name) == value, (process, name)


def test_ventana_de_medicina_de_oras_sigue_siendo_la_legada():
    # P5: la capacidad medida es solo de X/Y; ORAS conserva la ventana de
    # 100 casilleros de BagService.
    from app.services.bag_service import (
        BAG_MAX_QUANTITY,
        BAG_SLOT_SIZE,
        MEDICINE_POCKET_SCAN_SLOTS,
        RARE_CANDY_ITEM_ID,
    )

    assert (BAG_SLOT_SIZE, BAG_MAX_QUANTITY) == (4, 999)
    assert (MEDICINE_POCKET_SCAN_SLOTS, RARE_CANDY_ITEM_ID) == (100, 50)

    for process in ORAS_PROCESSES:
        assert get_profile(process).memory_map.medicine_pocket_slot_count is None


def test_constantes_de_combate_no_cambian():
    for name, value in COMBAT.items():
        assert getattr(combat_service, name) == value, name

    for process in ORAS_PROCESSES:
        m = get_profile(process).memory_map
        assert m.combat_pointer_address == 0x83f8658
        assert m.combat_hp_offset == 1028
        assert m.wild_battle_flag_offset == 2175
        assert m.combat_inactive_pointers == (0, 0x83f8654)


def test_slugs_de_almacenamiento_de_oras_no_cambian_nunca():
    slugs = nuzlocke_storage._GAME_STORAGE_SLUGS

    assert slugs["sango-2"] == "alpha_sapphire"
    assert slugs["sango-1"] == "omega_ruby"
    # Juegos agregados después (X/Y, Bloque 15).
    assert slugs["kujira-1"] == "pokemon_x"
    assert slugs["kujira-2"] == "pokemon_y"
    assert set(slugs) == {"sango-1", "sango-2", "kujira-1", "kujira-2"}


def test_title_id_bajo_para_ubicar_el_save_no_cambia():
    ids = save_file_locator._TITLE_ID_LOW_BY_PROCESS

    assert ids["sango-2"] == "0011c500"
    assert ids["sango-1"] == "0011c400"
    assert ids["kujira-1"] == "00055d00"
    assert ids["kujira-2"] == "00055e00"
    assert set(ids) == {"sango-1", "sango-2", "kujira-1", "kujira-2"}


def test_procesos_conocidos_de_oras():
    assert set(ORAS_PROCESSES) <= set(KNOWN_PROCESS_NAMES)
    assert set(KNOWN_PROCESS_NAMES) == set(ORAS_PROCESSES) | {
        "kujira-1",
        "kujira-2",
    }


def test_formato_de_la_tabla_del_equipo_no_cambia():
    from app.readers import azahar_reader

    assert azahar_reader.ORDER_ENTRY_SIZE == 4
    assert azahar_reader.POKEMON_POINTER_OFFSET == 64
    assert azahar_reader.SLOT_DATA_SIZE == 232
    assert azahar_reader.STAT_DATA_OFFSET == 112
    assert azahar_reader.STAT_DATA_SIZE == 22

"""
Etapa 0 de la ruta multijuego (03/10/2026): prueba "golden" de
direcciones y constantes de ORAS.

Congela TODO lo que hoy vive en app/memory/pointers.py y
app/services/combat_service.py para Omega Ruby (sango-1) y Alpha
Sapphire (sango-2), más los slugs de almacenamiento y el Title ID
usado para ubicar el save. Los valores se generaron leyendo el
código ANTES del refactor del Bloque 11; si algún bloque posterior
cambia cualquiera de ellos, esta prueba falla.

Por qué existe: mover estas direcciones a app/games/oras/profile.py
no debe cambiar ni un byte de lo que lee DexRelay en ORAS, y los
slugs de almacenamiento no deben cambiar nunca (los archivos
nuzlocke_alpha_sapphire_<tid>_<sid>.json de los usuarios dependen
de ellos).

LEGACY_UNKNOWN_FALLBACK documenta el comportamiento histórico de los
getters de pointers.py con un proceso desconocido (caen a Alpha
Sapphire). Es compatibilidad temporal: el Bloque 12 hace estricto el
reader y ese fallback deja de usarse; en ese bloque se borra esa
sección de la prueba, no el resto.
"""

import app.memory.pointers as pointers
import app.services.combat_service as combat_service
import app.services.nuzlocke_storage as nuzlocke_storage
import app.services.save_file_locator as save_file_locator
from app.readers.azahar_reader import KNOWN_PROCESS_NAMES

ORAS_PROCESSES = ("sango-1", "sango-2")

GETTERS = {
    "get_badges_address": {
        "sango-1": 0x8c71dc4,
        "sango-2": 0x8c71dc4,
    },
    "get_bag_end_address": {
        "sango-1": 0x8c6f800,
        "sango-2": 0x8c6f800,
    },
    "get_bag_start_address": {
        "sango-1": 0x8c6ec70,
        "sango-2": 0x8c6ec70,
    },
    "get_box_address": {
        "sango-1": [0x8c9e134, 0x8c9fc64, 0x8ca8454],
        "sango-2": [0x8c9e134, 0x8c9fc64, 0x8ca8454],
    },
    "get_box_base_address": {
        "sango-1": 0x8c9e134,
        "sango-2": 0x8c9e134,
    },
    "get_current_zone_id_address": {
        "sango-1": 0x8c6e7a2,
        "sango-2": 0x8c6e7a2,
    },
    "get_items_pocket_start_address": {
        "sango-1": 0x8c6ec70,
        "sango-2": 0x8c6ec70,
    },
    "get_medicine_pocket_start_address": {
        "sango-1": 0x8c6f5e0,
        "sango-2": 0x8c6f5e0,
    },
    "get_party_count_address": {
        "sango-1": 0x8cfb1f8,
        "sango-2": 0x8cfb1f8,
    },
    "get_party_order_address": {
        "sango-1": 0x8cfb1e0,
        "sango-2": 0x8cfb1e0,
    },
    "get_total_caught_address": {
        "sango-1": 0x8c8b28c,
        "sango-2": 0x8c8b28c,
    },
    "get_trainer_card_address": {
        "sango-1": 0x8c81340,
        "sango-2": 0x8c81340,
    },
    "get_wild_rival_addresses": {
        "sango-1": (0x81feec8, 0x81ffa6c, 0x8805638,),
        "sango-2": (0x81feec8, 0x81ffa6c, 0x8805638,),
    },
}
CONSTANTS = {
    "BAG_END_ADDRESS": 0x8c6f800,
    "BAG_MAX_QUANTITY": 999,
    "BAG_SLOT_SIZE": 4,
    "BAG_START_ADDRESS": 0x8c6ec70,
    "BLOCK_SIZE": 56,
    "BOX_BASE_ADDRESS": 0x8c9e134,
    "BOX_BLOCK_SIZE": 6960,
    "BOX_COUNT": 7,
    "BOX_SLOT_COUNT": 30,
    "BOX_SLOT_STRIDE": 232,
    "CAPTURE_BUFFER_ADDRESS": 0x8804a94,
    "CAPTURE_BUFFER_ENTRY_STRIDE": 484,
    "CURRENT_ZONE_ID_ADDRESS": 0x8c6e7a2,
    "CURRENT_ZONE_ID_MIRROR_ADDRESS": 0x8c6e884,
    "ITEMS_POCKET_SLOT_COUNT": 400,
    "LAST_CAUGHT_ADDRESS": 0x8805638,
    "MEDICINE_POCKET_SCAN_SLOTS": 100,
    "ORDER_ENTRY_SIZE": 4,
    "PARTY_COUNT_ADDRESS": 0x8cfb1f8,
    "PARTY_ORDER_ADDRESS": 0x8cfb1e0,
    "POKEBALL_ITEM_IDS": frozenset([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]),
    "POKEMON_POINTER_OFFSET": 64,
    "PROCESS_NAME_ALPHA_SAPPHIRE": 'sango-2',
    "PROCESS_NAME_OMEGA_RUBY": 'sango-1',
    "RARE_CANDY_ITEM_ID": 50,
    "SLOT_DATA_SIZE": 232,
    "STAT_DATA_OFFSET": 112,
    "STAT_DATA_SIZE": 22,
    "TRAINER_CARD_ADDRESS": 0x8c81340,
    "TRAINER_CARD_ID_OFFSET": 0,
    "TRAINER_CARD_NAME_BYTES": 24,
    "TRAINER_CARD_NAME_OFFSET": 72,
    "TRAINER_CARD_READ_SIZE": 96,
}
COMBAT = {
    "COMBAT_POINTER_ADDRESS": 0x83f8658,
    "COMBAT_HP_OFFSET": 1028,
    "WILD_BATTLE_FLAG_OFFSET": 2175,
    "COMBAT_INACTIVE_POINTER": 0x83f8654,
    "MIN_PLAUSIBLE_COMBAT_POINTER": 0x8000000,
}

LEGACY_UNKNOWN_FALLBACK = {
    "get_badges_address": 0x8c71dc4,
    "get_bag_end_address": 0x8c6f800,
    "get_bag_start_address": 0x8c6ec70,
    "get_box_address": [0x8c9e134, 0x8c9fc64, 0x8ca8454],
    "get_box_base_address": 0x8c9e134,
    "get_current_zone_id_address": 0x8c6e7a2,
    "get_items_pocket_start_address": 0x8c6ec70,
    "get_medicine_pocket_start_address": 0x8c6f5e0,
    "get_party_count_address": 0x8cfb1f8,
    "get_party_order_address": 0x8cfb1e0,
    "get_total_caught_address": 0x8c8b28c,
    "get_trainer_card_address": 0x8c81340,
    "get_wild_rival_addresses": (0x81feec8, 0x81ffa6c, 0x8805638,),
}


def _get(name, process, *extra):
    return getattr(pointers, name)(process, *extra)


def test_getters_de_direcciones_por_juego_no_cambian():
    for name, expected in GETTERS.items():
        for process, value in expected.items():
            if name == "get_box_address":
                actual = [_get(name, process, i) for i in (1, 2, 7)]
            else:
                actual = _get(name, process)
            assert actual == value, (name, process)


def test_todos_los_getters_publicos_estan_cubiertos():
    publicos = {n for n in dir(pointers) if n.startswith("get_")}
    assert publicos == set(GETTERS)


def test_constantes_de_pointers_no_cambian():
    for name, value in CONSTANTS.items():
        assert getattr(pointers, name) == value, name


def test_no_aparecen_constantes_nuevas_sin_cubrir():
    actuales = {
        n for n in dir(pointers)
        if n.isupper()
        and not n.startswith("_")
        and n != "ARCHIVO_DIRECCIONES_AS_BASE"
    }
    assert actuales == set(CONSTANTS)


def test_constantes_de_combate_no_cambian():
    for name, value in COMBAT.items():
        assert getattr(combat_service, name) == value, name


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


def test_fallback_legacy_de_proceso_desconocido():
    for name, value in LEGACY_UNKNOWN_FALLBACK.items():
        if name == "get_box_address":
            actual = [_get(name, "juego-desconocido", i) for i in (1, 2, 7)]
        else:
            actual = _get(name, "juego-desconocido")
        assert actual == value, name

"""
Bloque 11 (ruta multijuego, 03/10/2026): registro de perfiles de juego.

Verifica lo que el golden test (test_pointers_golden.py) no cubre: que el
registro sea ESTRICTO (a diferencia de los getters históricos de
pointers.py, un juego desconocido no cae a Alpha Sapphire) y que los
perfiles sean coherentes entre sí.
"""

from dataclasses import fields

from app.games.base import GameProfile, MemoryMap
from app.games.registry import all_profiles, get_profile, process_names
from app.memory.structures import Pokemon6


def test_juego_desconocido_no_tiene_perfil():
    assert get_profile("juego-desconocido") is None
    assert get_profile(None) is None
    assert get_profile("") is None


def test_oras_registrado_por_process_name():
    alpha = get_profile("sango-2")
    omega = get_profile("sango-1")

    assert alpha.display_name == "Pokémon Alpha Sapphire"
    assert omega.display_name == "Pokémon Omega Ruby"
    assert alpha.key != omega.key


def test_process_names_por_reader():
    assert set(process_names("azahar")) == {
        "sango-1",
        "sango-2",
        "kujira-1",
        "kujira-2",
    }
    assert process_names("otro-emulador") == ()
    assert set(process_names()) == {p.key for p in all_profiles()}


def test_las_llaves_son_unicas():
    keys = [p.key for p in all_profiles()]
    assert len(keys) == len(set(keys))


def test_oras_usa_pk6_y_generacion_6():
    for profile in all_profiles():
        assert isinstance(profile, GameProfile)
        assert profile.pokemon_format is Pokemon6
        assert profile.capabilities.generation == 6
        assert profile.reader_kind == "azahar"


def test_oras_tiene_confirmado_todo_el_mapa_de_memoria():
    # ORAS es el juego de referencia: ningún campo del MemoryMap puede
    # quedar en None. (Un juego nuevo SÍ puede tener campos en None =
    # "no confirmado todavía"; ORAS no.)
    # Los métodos de clasificar el combate son excluyentes: ORAS usa la
    # bandera de un byte, X/Y el valor de la celda.
    solo_xy = {"wild_battle_pointers", "trainer_battle_pointers"}
    # Capacidad medida solo en X/Y (P5); ORAS conserva su ventana legada.
    solo_xy_p5 = {"medicine_pocket_slot_count"}

    for profile in (get_profile("sango-1"), get_profile("sango-2")):
        for campo in fields(MemoryMap):
            if campo.name in solo_xy | solo_xy_p5:
                assert getattr(profile.memory_map, campo.name) is None
                continue

            assert getattr(profile.memory_map, campo.name) is not None, (
                profile.key,
                campo.name,
            )


def test_slugs_y_title_id_son_unicos_por_juego():
    slugs = [p.content.storage_slug for p in all_profiles()]
    title_ids = [p.content.title_id_low for p in all_profiles()]

    assert len(slugs) == len(set(slugs))
    assert len(title_ids) == len(set(title_ids))
    assert all(slugs) and all(title_ids)


def test_el_formato_pk6_no_depende_de_pointers():
    # structures.py ya no debe importar el módulo de direcciones de
    # ORAS (Bloque 11): las constantes del formato viven con el decoder.
    import inspect

    import app.memory.structures as structures

    assert "app.memory.pointers" not in inspect.getsource(structures)


def test_xy_declara_explicitamente_lo_que_no_esta_investigado():
    # X/Y arrancan con None en lo no investigado (la función se apaga) y
    # NUNCA heredan una dirección de ORAS.
    oras = get_profile("sango-2").memory_map
    for key in ("kujira-1", "kujira-2"):
        m = get_profile(key).memory_map

        assert m.capture_buffer_address is None
        assert m.bag_start_address is None
        # P5: la Medicina de X/Y se midió (no hereda la de ORAS).
        assert m.medicine_pocket_start_address == 0x08C67ECC

        for campo in fields(MemoryMap):
            valor = getattr(m, campo.name)
            if isinstance(valor, int) and not isinstance(valor, bool):
                assert valor != getattr(oras, campo.name) or valor in (
                    0, 1, 2, 0xE8, 30, 400, 0x60, 0x48, 24,
                ), campo.name


def test_xy_comparten_mapa_y_ya_no_son_experimentales():
    x = get_profile("kujira-1")
    y = get_profile("kujira-2")

    assert x.memory_map == y.memory_map
    assert not x.capabilities.experimental
    assert not y.capabilities.experimental
    assert not get_profile("sango-2").capabilities.experimental
    assert x.display_name == "Pokémon X" and y.display_name == "Pokémon Y"
    assert x.content.title_id_low == "00055d00"
    assert y.content.title_id_low == "00055e00"

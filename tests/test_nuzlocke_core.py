"""
Bloque 2 (guía siguiente versión, 22/09/2026): casos mínimos de la
suite de tests automatizada sobre NuzlockeService.update() --
identidad por nickname, sin necesitar Azahar ni el bridge PKHeX
(FakeStorage en memoria, igual que los probes existentes en
tools/probes/memory/).

Cubre, de la lista de "casos mínimos" del Bloque 2:
  - inicial: siempre el primer Pokémon, nunca se reasigna
  - muerte: permanente, no vuelve al roster aunque el HP suba
  - evolución: actualiza el mismo registro, no duplica
  - reordenamiento de party: no se lee como captura/evolución nueva
  - species clause: no registra un segundo encuentro, pero el
    Pokémon sigue vivo en el roster

Los otros dos casos de la lista (huevo -> especie/nickname
resueltos; diferencias vanilla vs. overrides del hackroom) ya
tienen cobertura o quedan fuera a propósito -- ver el comentario
al final de este archivo.
"""

from app.services.nuzlocke_service import NuzlockeService


class FakeStorage:
    """
    Mismo patrón que las probes existentes (ver
    tools/probes/memory/test_starter_rename_reconciliation.py):
    guarda el último estado en memoria, sin tocar disco.
    """

    def __init__(self):
        self.saved = None

    def load(self):
        return {
            "roster": [],
            "graveyard": [],
            "encounters": [],
            "pending_encounters": [],
            "starter_assigned": False,
        }

    def save(self, data):
        self.saved = data


def _mon(
    slot,
    nickname,
    species,
    species_id,
    level,
    hp=50,
    met_location="Ruta 101",
):
    """Un Pokémon de party mínimo pero completo (mismas claves que
    build_pokemon_data() en azahar_reader.py)."""

    return {
        "slot": slot,
        "empty": False,
        "nickname": nickname,
        "species": species,
        "speciesId": species_id,
        "level": level,
        "hp": hp,
        "maxHp": max(hp, 1),
        "shiny": False,
        "metLocation": met_location,
        "genderId": 0,
    }


def _team(*mons):
    """Rellena hasta los 6 slots con vacíos, como reporta Azahar."""

    filled = list(mons)

    while len(filled) < 6:
        filled.append({"slot": len(filled) + 1, "empty": True})

    return filled


# ---------------------------------------------------------------
# Inicial
# ---------------------------------------------------------------

def test_primer_captura_es_inicial_sin_importar_metlocation():
    service = NuzlockeService(FakeStorage())

    boti = _mon(1, "Boti", "Torchic", 255, 5, met_location="")

    state = service.update(_team(boti))

    encounters = state["encounters"]

    assert len(encounters) == 1
    assert encounters[0]["location"] == "Inicial"
    assert encounters[0]["nickname"] == "Boti"
    assert state["starter_assigned"] is True


def test_inicial_nunca_se_reasigna_aunque_el_primero_muera():
    service = NuzlockeService(FakeStorage())

    boti = _mon(1, "Boti", "Torchic", 255, 5, met_location="")
    service.update(_team(boti))

    # Boti muere Y aparece una captura nueva en el mismo ciclo --
    # el orden de asignación del inicial ya quedó fijado antes, no
    # tiene que "liberarse" porque el primero haya muerto.
    boti_muerto = _mon(1, "Boti", "Torchic", 255, 5, hp=0)
    segundo = _mon(2, "Rocko", "Geodude", 74, 4, met_location="Ruta 102")

    state = service.update(_team(boti_muerto, segundo))

    inicial_encounters = [
        e for e in state["encounters"] if e["location"] == "Inicial"
    ]

    assert len(inicial_encounters) == 1
    assert inicial_encounters[0]["nickname"] == "Boti"

    rocko_encounter = next(
        e for e in state["encounters"] if e["nickname"] == "Rocko"
    )
    assert rocko_encounter["location"] == "Ruta 102"


# ---------------------------------------------------------------
# Muerte permanente
# ---------------------------------------------------------------

def test_muerte_es_permanente_no_vuelve_al_roster_aunque_el_hp_suba():
    service = NuzlockeService(FakeStorage())

    ash = _mon(1, "Ash", "Pikachu", 25, 10, hp=30)
    state = service.update(_team(ash))

    assert len(state["roster"]) == 1
    assert len(state["graveyard"]) == 0

    ash_muerto = _mon(1, "Ash", "Pikachu", 25, 10, hp=0)
    state = service.update(_team(ash_muerto))

    assert len(state["roster"]) == 0
    assert len(state["graveyard"]) == 1
    assert state["graveyard"][0]["nickname"] == "Ash"

    encounter = next(
        e for e in state["encounters"] if e["nickname"] == "Ash"
    )
    assert encounter["status"] == "muerto"

    # HP vuelve a subir (ej. Revivir en la Caja PC, o una lectura
    # transitoria) -- la muerte ya es historial permanente, no
    # tiene que reaparecer en el roster.
    ash_revivido = _mon(1, "Ash", "Pikachu", 25, 12, hp=30)
    state = service.update(_team(ash_revivido))

    assert len(state["roster"]) == 0
    assert len(state["graveyard"]) == 1


# ---------------------------------------------------------------
# Evolución
# ---------------------------------------------------------------

def test_evolucion_actualiza_el_mismo_registro_sin_duplicar():
    service = NuzlockeService(FakeStorage())

    bola = _mon(1, "Bola", "Voltorb", 100, 5, met_location="")
    state = service.update(_team(bola))

    assert len(state["roster"]) == 1
    assert len(state["encounters"]) == 1

    bola_evolucionada = _mon(1, "Bola", "Electrode", 101, 16)
    state = service.update(_team(bola_evolucionada))

    assert len(state["roster"]) == 1
    assert len(state["graveyard"]) == 0
    assert state["roster"][0]["nickname"] == "Bola"
    assert state["roster"][0]["speciesId"] == 101
    assert state["roster"][0]["level"] == 16

    # No se duplica el encuentro ("Inicial") ni cambia de ubicación
    # -- solo se actualiza el nombre de especie mostrado.
    assert len(state["encounters"]) == 1
    assert state["encounters"][0]["location"] == "Inicial"
    assert state["encounters"][0]["species"] == "Electrode"


# ---------------------------------------------------------------
# Reordenamiento de party
# ---------------------------------------------------------------

def test_reordenar_party_no_crea_captura_ni_evolucion():
    service = NuzlockeService(FakeStorage())

    uno = _mon(1, "Uno", "Zigzagoon", 263, 5, met_location="")
    dos = _mon(2, "Dos", "Poochyena", 261, 4, met_location="Ruta 101")

    state = service.update(_team(uno, dos))

    assert len(state["roster"]) == 2
    assert len(state["encounters"]) == 2

    # Mismos dos Pokémon, orden de slots invertido (ej. el jugador
    # los reordenó desde el menú del equipo) -- nada cambió de
    # verdad, no tiene que leerse como captura/evolución nueva.
    uno_reordenado = _mon(2, "Uno", "Zigzagoon", 263, 5, met_location="")
    dos_reordenado = _mon(1, "Dos", "Poochyena", 261, 4, met_location="Ruta 101")

    state = service.update(_team(dos_reordenado, uno_reordenado))

    assert len(state["roster"]) == 2
    assert len(state["encounters"]) == 2
    assert len(state["graveyard"]) == 0

    roster_by_nickname = {
        entry["nickname"]: entry for entry in state["roster"]
    }
    assert roster_by_nickname["Uno"]["speciesId"] == 263
    assert roster_by_nickname["Uno"]["level"] == 5
    assert roster_by_nickname["Dos"]["speciesId"] == 261
    assert roster_by_nickname["Dos"]["level"] == 4


# ---------------------------------------------------------------
# Species clause
# ---------------------------------------------------------------

def test_species_clause_no_registra_segundo_encuentro_pero_vive_en_roster():
    service = NuzlockeService(FakeStorage())

    inicial = _mon(1, "Starter", "Mudkip", 258, 5, met_location="")
    service.update(_team(inicial))

    uno = _mon(2, "Uno", "Zigzagoon", 263, 4, met_location="Ruta 101")
    state = service.update(_team(inicial, uno))

    assert len(state["encounters"]) == 2  # Inicial + Ruta 101

    # Segunda captura de la MISMA especie (Zigzagoon) mientras la
    # primera (Uno) sigue viva -- no debe generar un encuentro
    # nuevo ni quedar pendiente, pero sí debe existir en el roster.
    dos = _mon(3, "Dos", "Zigzagoon", 263, 3, met_location="Ruta 102")
    state = service.update(_team(inicial, uno, dos))

    assert len(state["roster"]) == 3
    assert any(entry["nickname"] == "Dos" for entry in state["roster"])

    # Sigue habiendo solo 2 encuentros (Inicial + Ruta 101) -- Ruta
    # 102 nunca se registró, ni en encounters ni en pendientes.
    assert len(state["encounters"]) == 2
    assert not any(
        e["location"] == "Ruta 102" for e in state["encounters"]
    )
    assert not any(
        p["nickname"] == "Dos" for p in state["pending_encounters"]
    )


# ---------------------------------------------------------------
# Casos de la lista del Bloque 2 que quedan fuera de este archivo:
#
# - "huevo -> especie/nickname resueltos": ya cubierto por
#   tools/probes/memory/test_egg_hatch_reconciliation.py y
#   test_egg_location_translation.py -- ver pytest.ini (testpaths
#   incluye tools/probes/ además de tests/), no se duplica acá.
# - "diferencias vanilla vs. overrides del hackroom": la lógica
#   vive en GymLeaderCatalog (app/services/gym_leaders.py) y
#   depende del bridge PKHeX real (AbilityCatalog/MoveCatalog/
#   ItemCatalog resuelven nombres en español vía el proceso .NET) 
#   -- un test unitario con un bridge fake no validaría nada real
#   sin haber confirmado antes cómo se comportan esos catálogos
#   sin bridge (regla 1 del Documento Maestro: no inventar sin
#   confirmar). Queda pendiente como test de integración con
#   Azahar/bridge corriendo, no como test unitario acá.
# ---------------------------------------------------------------


if __name__ == "__main__":
    test_primer_captura_es_inicial_sin_importar_metlocation()
    test_inicial_nunca_se_reasigna_aunque_el_primero_muera()
    test_muerte_es_permanente_no_vuelve_al_roster_aunque_el_hp_suba()
    test_evolucion_actualiza_el_mismo_registro_sin_duplicar()
    test_reordenar_party_no_crea_captura_ni_evolucion()
    test_species_clause_no_registra_segundo_encuentro_pero_vive_en_roster()
    print("OK - todos los casos mínimos de NuzlockeService pasaron")

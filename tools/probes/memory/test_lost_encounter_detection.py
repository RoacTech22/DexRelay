"""
Valida el diseño de detección automática del estado "perdido"
(27/08/2026, ver DexRelay_Contexto_Deteccion_Perdido.md):
Runtime._update_lost_encounter_tracking() usando las 3 piezas ya
confirmadas (CURRENT_ZONE_ID_ADDRESS, WILD_BATTLE_FLAG_OFFSET,
read_last_caught()) más TOTAL_CAUGHT_ADDRESS como confirmación de
captura.

No prueba las direcciones de memoria en sí (ya confirmadas en el
juego real, ver pointers.py / combat_service.py) -- prueba el
wiring y la máquina de estados edge-triggered de Runtime con
fakes, sin necesitar Azahar.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.services.combat_service import LECTURA_DESCARTADA


class FakeReader:
    def __init__(self):
        self.memory = None
        self._connected = True
        self.zone_id = 23  # Ruta 101, ver zone_names.py
        self.total_caught = 5
        self.last_caught_species = "Zigzagoon"

    def is_connected(self):
        return self._connected

    def connect(self):
        return True

    def read_party(self):
        return [{"slot": i + 1, "empty": True} for i in range(6)]

    def read_boxes_range(self, start_box_index=1, box_count=7):
        return []

    def read_current_zone_id(self):
        return self.zone_id

    def read_total_caught_count(self):
        return self.total_caught

    def read_last_caught(self):
        if self.last_caught_species is None:
            return None
        return {"species": self.last_caught_species}


class FakeNuzlockeService:
    def __init__(self):
        self.calls = []
        self.lost_calls = []
        self.registered_locations = set()

    def update(self, party, boxed_party=None):
        self.calls.append(party)
        return {"roster": [], "graveyard": []}

    def has_encounter_for_location(self, location):
        return location in self.registered_locations

    def register_lost_encounter(self, location, species):
        self.lost_calls.append((location, species))
        self.registered_locations.add(location)


def _make_runtime(wild_flag_sequence):
    """
    `wild_flag_sequence`: lista de valores que
    combat_service.read_wild_flag() devuelve, uno por cada
    llamada a runtime.update() (en orden).
    """

    reader = FakeReader()
    state = ApplicationState()
    nuzlocke = FakeNuzlockeService()

    runtime = Runtime(reader, state, nuzlocke_service=nuzlocke)
    runtime.badges_service.read_badges = lambda: {
        "value": 0,
        "count": 0,
        "badges": [False] * 8,
    }
    runtime.combat_service.read = lambda: None

    sequence = iter(wild_flag_sequence)
    runtime.combat_service.read_wild_flag = lambda: next(sequence)

    return runtime, reader, nuzlocke


def test_combate_salvaje_sin_captura_se_registra_perdido():
    """
    Caso principal: combate salvaje empieza, termina, el contador
    de capturas NO subió -- debe registrarse "perdido" en la
    ubicación actual con la especie rival como nickname/species.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [True, True, None]
    )

    runtime.update()  # inactivo -> salvaje: toma snapshot
    assert runtime._lost_encounter_snapshot == {
        "location": "Ruta 101",
        "species": "Zigzagoon",
        "total_caught": 5,
    }
    assert nuzlocke.lost_calls == []

    runtime.update()  # sigue salvaje: no debe re-tomar snapshot
    assert runtime._lost_encounter_snapshot["total_caught"] == 5

    runtime.update()  # salvaje -> inactivo, sin captura nueva
    assert nuzlocke.lost_calls == [("Ruta 101", "Zigzagoon")]
    assert runtime._lost_encounter_snapshot is None

    print(
        "OK - combate salvaje sin captura registra 'perdido' "
        "al terminar"
    )


def test_combate_salvaje_con_captura_no_registra_perdido():
    """
    Si el contador de capturas SÍ subió durante el combate, no
    debe registrarse nada -- la captura ya se registra sola por
    el camino normal de party/Caja PC.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [True, None]
    )

    runtime.update()  # toma snapshot con total_caught=5

    reader.total_caught = 6  # se capturó durante el combate

    runtime.update()  # termina el combate

    assert nuzlocke.lost_calls == []
    assert runtime._lost_encounter_snapshot is None

    print(
        "OK - combate salvaje con captura NO registra 'perdido'"
    )


def test_ruta_ya_registrada_no_toma_snapshot():
    """
    Si la ruta actual ya tiene un encuentro (de cualquier
    estado), no debe tomarse ningún snapshot -- evita pisar un
    encuentro real con un "perdido" viejo.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [True, None]
    )

    nuzlocke.registered_locations.add("Ruta 101")

    runtime.update()
    assert runtime._lost_encounter_snapshot is None

    runtime.update()
    assert nuzlocke.lost_calls == []

    print(
        "OK - ruta ya registrada no toma snapshot ni "
        "registra 'perdido'"
    )


def test_combate_entrenador_no_dispara_snapshot_pero_no_rompe_tracking():
    """
    Un combate de entrenador (wild_result == False) no debe
    disparar ningún snapshot nuevo, pero sí debe contarse como
    "combate activo" para no confundir la transición de fin de
    combate de un salvaje que ya estaba en curso.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [True, False, None]
    )

    runtime.update()  # salvaje: toma snapshot
    assert runtime._lost_encounter_snapshot is not None

    runtime.update()  # cambia a entrenador sin pasar por inactivo
    assert runtime._lost_encounter_snapshot is not None
    assert nuzlocke.lost_calls == []

    runtime.update()  # entrenador -> inactivo: recién ahí finaliza
    assert nuzlocke.lost_calls == [("Ruta 101", "Zigzagoon")]

    print(
        "OK - combate de entrenador no dispara snapshot nuevo "
        "ni rompe el tracking del salvaje en curso"
    )


def test_lectura_descartada_no_toca_el_estado():
    """
    LECTURA_DESCARTADA (puntero cambió a mitad de lectura) no
    debe tocar ningún estado de tracking -- se reintenta el
    próximo ciclo.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [True, LECTURA_DESCARTADA, None]
    )

    runtime.update()
    snapshot_after_first = dict(runtime._lost_encounter_snapshot)

    runtime.update()  # descartada: no debe cambiar nada
    assert runtime._lost_encounter_snapshot == snapshot_after_first
    assert runtime._combat_was_active is True

    runtime.update()  # inactivo real: ahora sí finaliza
    assert nuzlocke.lost_calls == [("Ruta 101", "Zigzagoon")]

    print(
        "OK - LECTURA_DESCARTADA no toca el estado de tracking"
    )


def test_zona_sin_mapear_usa_placeholder():
    """
    Una zona todavía no mapeada en zone_names.ZONE_ID_TO_NAME no
    debe bloquear la detección -- se usa el placeholder
    "Zona {id}".
    """

    runtime, reader, nuzlocke = _make_runtime(
        [True, None]
    )

    reader.zone_id = 999  # no está en la tabla

    runtime.update()
    assert (
        runtime._lost_encounter_snapshot["location"] == "Zona 999"
    )

    runtime.update()
    assert nuzlocke.lost_calls == [("Zona 999", "Zigzagoon")]

    print("OK - zona sin mapear usa placeholder 'Zona {id}'")


def test_flag_salvaje_tarda_varios_ciclos_en_poblarse():
    """
    Reproduce el bug real reportado el 28/08/2026: en el juego
    real, read_wild_flag() dio False (entrenador) en el primer
    ciclo de un combate que en realidad SÍ era salvaje -- el juego
    todavía no había terminado de escribir la tabla de datos del
    encuentro salvaje. Con la lógica edge-triggered original (que
    miraba el flag una sola vez, justo en la transición), esto
    dejaba el combate fijado como "entrenador" para siempre y
    nunca se tomaba snapshot.

    La detección tiene que seguir reintentando cada ciclo mientras
    el combate siga activo, no solo en el instante exacto de la
    transición.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [False, False, True, None]
    )

    runtime.update()  # ciclo 1: flag todavía en False (transitorio)
    assert runtime._lost_encounter_snapshot is None

    runtime.update()  # ciclo 2: sigue en False
    assert runtime._lost_encounter_snapshot is None

    runtime.update()  # ciclo 3: el juego ya escribió el flag salvaje
    assert runtime._lost_encounter_snapshot == {
        "location": "Ruta 101",
        "species": "Zigzagoon",
        "total_caught": 5,
    }

    runtime.update()  # fin de combate, sin captura
    assert nuzlocke.lost_calls == [("Ruta 101", "Zigzagoon")]

    print(
        "OK - un flag salvaje que tarda varios ciclos en "
        "poblarse igual se detecta (no se fija en el primer "
        "ciclo)"
    )


def test_entrenador_genuino_nunca_toma_snapshot():
    """
    Un combate de entrenador de verdad (el flag se queda en False
    toda la pelea) nunca debe tomar ningún snapshot, y
    _lost_tracking_resolved debe resetearse al terminar para no
    afectar al próximo combate.
    """

    runtime, reader, nuzlocke = _make_runtime(
        [False, False, False, None]
    )

    for _ in range(3):
        runtime.update()

    assert runtime._lost_encounter_snapshot is None

    runtime.update()  # fin de combate

    assert nuzlocke.lost_calls == []
    assert runtime._lost_tracking_resolved is False

    print(
        "OK - un combate de entrenador genuino nunca toma "
        "snapshot, y el estado se resetea al terminar"
    )


if __name__ == "__main__":
    test_combate_salvaje_sin_captura_se_registra_perdido()
    test_combate_salvaje_con_captura_no_registra_perdido()
    test_ruta_ya_registrada_no_toma_snapshot()
    test_combate_entrenador_no_dispara_snapshot_pero_no_rompe_tracking()
    test_lectura_descartada_no_toca_el_estado()
    test_zona_sin_mapear_usa_placeholder()
    test_flag_salvaje_tarda_varios_ciclos_en_poblarse()
    test_entrenador_genuino_nunca_toma_snapshot()

"""
Valida el diseño actual de detección de capturas en la Caja PC
(26-27/08/2026), que reemplaza al archivo
test_boxed_capture_baseline.py (borrado -- probaba el Intento 4,
la máquina de dos etapas por TOTAL_CAUGHT_ADDRESS +
LAST_CAUGHT_ADDRESS, que ya no existe en Runtime).

Direcciones confirmadas empíricamente (ver Documento Maestro,
sección 14, "Detección de capturas en la Caja PC"):
    BOX_BASE_ADDRESS = 0x08C9A144
    BOX_SLOT_STRIDE  = 0xE8 (232 bytes, == SLOT_DATA_SIZE exacto)

Dos cosas se prueban acá:
  1. AzaharReader.read_box() -- casos de ventana vacía y lectura
     fallida (los casos que se pueden probar sin fabricar bytes
     PK6 cifrados reales; el caso de un slot ocupado y válido ya
     se confirmó en el juego real con tools/probes/party/
     buscar_caja_pc.py, tres veces, incluyendo tras un reinicio
     completo de Azahar).
  2. Runtime.update() -- que efectivamente llama a
     reader.read_box() cada ciclo y pasa el resultado a
     NuzlockeService.update() como `boxed_party`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    BOX_BASE_ADDRESS,
    BOX_SLOT_STRIDE,
    BOX_SLOT_COUNT,
)


class FakeMemory:
    """Stub de MemoryReader -- sin red, devuelve lo que se le diga."""

    def __init__(self, response):
        self.response = response
        self.last_read = None

    def read(self, address, size):
        self.last_read = (address, size)
        return self.response


def _make_reader(memory_response):
    reader = AzaharReader()
    reader.memory = FakeMemory(memory_response)
    return reader


def test_read_box_ventana_vacia_devuelve_lista_vacia():
    """
    Una ventana entera en cero (caja realmente vacía, o los 30
    slots sin ocupar) no debe reportar ningún candidato -- cada
    chunk falla la comprobación de estructura vacía en
    Pokemon6.__init__ (primeros 8 bytes en cero).
    """
    window_size = BOX_SLOT_COUNT * BOX_SLOT_STRIDE
    reader = _make_reader(b"\x00" * window_size)

    box = reader.read_box()

    assert box == []
    assert reader.memory.last_read == (BOX_BASE_ADDRESS, window_size)

    print("OK - ventana vacía (todo ceros) devuelve lista vacía")


def test_read_box_lectura_incompleta_devuelve_lista_vacia():
    """
    Si la lectura de memoria devuelve menos bytes de los
    esperados (paquete UDP perdido, lectura parcial), read_box()
    no debe intentar interpretar nada a medias -- devuelve lista
    vacía, igual que un ciclo sin novedades. El dato real de la
    caja no se pierde: sigue ahí para el próximo ciclo.
    """
    window_size = BOX_SLOT_COUNT * BOX_SLOT_STRIDE
    reader = _make_reader(b"\x00" * (window_size - 10))

    box = reader.read_box()

    assert box == []

    print("OK - lectura incompleta devuelve lista vacía, sin excepción")


def test_read_box_sin_respuesta_devuelve_lista_vacia():
    reader = _make_reader(b"")

    box = reader.read_box()

    assert box == []

    print("OK - sin respuesta de memoria devuelve lista vacía")


class FakeReaderForRuntime:
    """
    Reader falso para probar el wiring de Runtime.update(), no la
    lógica interna de read_box() (ya cubierta arriba).
    """

    def __init__(self):
        self.memory = None
        self._connected = True
        self.box_to_return = []

    def is_connected(self):
        return self._connected

    def connect(self):
        return True

    def read_party(self):
        return [{"slot": i + 1, "empty": True} for i in range(6)]

    def read_box(self):
        return self.box_to_return


class FakeNuzlockeService:
    def __init__(self):
        self.calls = []

    def update(self, party, boxed_party=None):
        self.calls.append(
            {"party": party, "boxed_party": boxed_party}
        )
        return {"roster": [], "graveyard": []}


def test_runtime_pasa_boxed_party_a_nuzlocke_service():
    reader = FakeReaderForRuntime()
    state = ApplicationState()
    nuzlocke = FakeNuzlockeService()

    runtime = Runtime(reader, state, nuzlocke_service=nuzlocke)
    runtime.badges_service.read_badges = lambda: {
        "value": 0,
        "count": 0,
        "badges": [False] * 8,
    }
    runtime.combat_service.read = lambda: None

    box_contents = [
        {
            "slot": 1,
            "empty": False,
            "nickname": "Ziggy",
            "species": "Zigzagoon",
            "speciesId": 263,
            "level": 3,
            "hp": 0,
            "maxHp": 0,
            "shiny": False,
            "metLocation": "Ruta 101",
        }
    ]
    reader.box_to_return = box_contents

    runtime.update()

    assert len(nuzlocke.calls) == 1
    assert nuzlocke.calls[0]["boxed_party"] == box_contents

    # Caja vacía en el ciclo siguiente -- se sigue pasando (lista
    # vacía), no None ni se omite el argumento.
    reader.box_to_return = []
    runtime.update()

    assert nuzlocke.calls[1]["boxed_party"] == []

    print(
        "OK - Runtime.update() llama a reader.read_box() cada "
        "ciclo y lo pasa como boxed_party a NuzlockeService"
    )


if __name__ == "__main__":
    test_read_box_ventana_vacia_devuelve_lista_vacia()
    test_read_box_lectura_incompleta_devuelve_lista_vacia()
    test_read_box_sin_respuesta_devuelve_lista_vacia()
    test_runtime_pasa_boxed_party_a_nuzlocke_service()

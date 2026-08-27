"""
Valida el diseño final (Intento 4, 26/08/2026) de deteccion de
capturas nuevas via TOTAL_CAUGHT_ADDRESS + LAST_CAUGHT_ADDRESS --
ahora el UNICO metodo para toda captura real (no el Inicial), sin
importar si el Pokemon fue a la party o a la Caja PC.

Cubre el bug real del Intento 3 (descartado): la "primera lectura
tras el disparo" podia ser en realidad basura vieja de la captura
ANTERIOR (el buffer no se limpia entre capturas), asi que la
primera actualizacion real (todavia con nombre por defecto) ya se
veia "distinta" de esa basura y se confirmaba de una sin terminar
de escribir.

El Intento 4 corrige esto con dos etapas:
  ETAPA 1: esperar a que la lectura actual difiera del ULTIMO VALOR
    CONOCIDO DE ANTES de que se disparara la captura (no de la
    primera lectura DESPUES) -- eso confirma que el buffer ya
    refleja la captura nueva, aunque sea con nombre por defecto.
  ETAPA 2: igual que el Intento 3, pero con un baseline confiable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.runtime import Runtime
from app.core.state import ApplicationState


OLD_LEFTOVER = {
    "slot": 0,
    "nickname": "Zigzagoon",
    "species": "Zigzagoon",
    "speciesId": 263,
    "level": 4,
    "hp": 17,
    "maxHp": 17,
    "shiny": False,
    "metLocation": "Ruta 101",
}

DEFAULT_READ = {
    "slot": 0,
    "nickname": "Pancham",
    "species": "Pancham",
    "speciesId": 674,
    "level": 12,
    "hp": 30,
    "maxHp": 30,
    "shiny": False,
    "metLocation": "",
}

FINAL_READ = {
    **DEFAULT_READ,
    "nickname": "Pandy",
    "metLocation": "Ruta 101",
}


class FakeReader:
    def __init__(self):
        self.memory = None
        self._connected = True
        self.total_caught = 5
        self.last_caught_queue = []

    def is_connected(self):
        return self._connected

    def connect(self):
        return True

    def read_party(self):
        return [{"slot": i + 1, "empty": True} for i in range(6)]

    def read_total_caught_count(self):
        return self.total_caught

    def read_last_caught(self):
        if self.last_caught_queue:
            return self.last_caught_queue.pop(0)
        return None


class FakeNuzlockeService:
    def __init__(self):
        self.boxed_captures_received = []

    def update(self, party, boxed_capture=None):
        self.boxed_captures_received.append(boxed_capture)
        return {"roster": [], "graveyard": []}


def _make_runtime():
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
    return runtime, reader, nuzlocke


def test_ignora_basura_vieja_del_buffer_antes_de_confirmar():
    """
    Reproduce el bug real del Intento 3: el buffer todavia tiene la
    captura ANTERIOR cuando sube el contador de la NUEVA. El
    Intento 4 no debe confundir esa basura vieja con el baseline de
    la captura actual.
    """
    runtime, reader, nuzlocke = _make_runtime()

    # Antes de cualquier captura nueva, el buffer ya tiene basura
    # vieja de una captura anterior (se lee todos los ciclos, no
    # solo mientras se rastrea).
    reader.total_caught = 5
    reader.last_caught_queue = [OLD_LEFTOVER]
    runtime.update()
    assert runtime._last_seen_capture_read == OLD_LEFTOVER

    # Sube el contador -> nueva captura. ETAPA 1: la primera lectura
    # sigue mostrando la basura vieja (el buffer todavia no se
    # sobreescribió) -- no debe confirmarse con esto.
    reader.total_caught = 6
    reader.last_caught_queue = [OLD_LEFTOVER]
    runtime.update()
    assert runtime._capture_stage == 1
    assert nuzlocke.boxed_captures_received[-1] is None

    # Ahora el buffer se sobreescribe con la captura nueva (todavia
    # nombre por defecto) -- pasa a etapa 2, NO se confirma todavia
    # (la etapa 1 solo detecta que "ya cambió de la basura vieja",
    # no confirma con ese valor).
    reader.last_caught_queue = [DEFAULT_READ]
    runtime.update()
    assert runtime._capture_stage == 2
    assert runtime._capture_baseline == DEFAULT_READ
    assert nuzlocke.boxed_captures_received[-1] is None

    # Varios ciclos con el nombre por defecto -- sigue sin confirmar.
    for _ in range(20):
        reader.last_caught_queue = [DEFAULT_READ]
        runtime.update()
        assert nuzlocke.boxed_captures_received[-1] is None

    # El jugador cierra el diálogo: aparece el valor final.
    reader.last_caught_queue = [FINAL_READ]
    runtime.update()

    assert runtime._tracking_capture is False
    assert nuzlocke.boxed_captures_received[-1] == FINAL_READ

    print(
        "OK - ignora la basura vieja del buffer y confirma con el "
        "valor final correcto, no con la captura anterior ni con "
        "el nombre por defecto"
    )


def test_confirma_por_cambio_en_etapa_2():
    runtime, reader, nuzlocke = _make_runtime()

    reader.total_caught = 5
    runtime.update()

    reader.total_caught = 6
    reader.last_caught_queue = [DEFAULT_READ]
    runtime.update()
    assert runtime._capture_stage == 2  # no había basura vieja que saltar

    for _ in range(37):
        reader.last_caught_queue = [DEFAULT_READ]
        runtime.update()
        assert nuzlocke.boxed_captures_received[-1] is None

    reader.last_caught_queue = [FINAL_READ]
    runtime.update()

    assert nuzlocke.boxed_captures_received[-1] == FINAL_READ
    print("OK - confirma por cambio en etapa 2, sin importar cuántos ciclos default")


def test_fallback_por_timeout_en_etapa_2_si_nunca_cambia():
    runtime, reader, nuzlocke = _make_runtime()

    reader.total_caught = 5
    runtime.update()

    reader.total_caught = 6
    reader.last_caught_queue = [DEFAULT_READ]
    runtime.update()

    for _ in range(runtime._CAPTURE_TRACKING_TIMEOUT_CYCLES - 1):
        reader.last_caught_queue = [DEFAULT_READ]
        runtime.update()
        assert nuzlocke.boxed_captures_received[-1] is None

    reader.last_caught_queue = [DEFAULT_READ]
    runtime.update()

    assert runtime._tracking_capture is False
    assert nuzlocke.boxed_captures_received[-1] == DEFAULT_READ

    print("OK - fallback por timeout en etapa 2 cuando el jugador no cambia el nombre")


def test_se_activa_sin_importar_si_la_party_esta_llena_o_no():
    """
    A pedido explícito (26/08/2026): un solo método para toda
    captura, sin importar si la party tenía espacio o no. Ya no
    hay ningún gate por party llena.
    """
    runtime, reader, nuzlocke = _make_runtime()

    reader.total_caught = 5
    runtime.update()

    reader.total_caught = 6
    reader.last_caught_queue = [DEFAULT_READ]
    runtime.update()

    assert runtime._tracking_capture is True

    print("OK - se activa siempre, sin gate por party llena/con espacio")


if __name__ == "__main__":
    test_ignora_basura_vieja_del_buffer_antes_de_confirmar()
    test_confirma_por_cambio_en_etapa_2()
    test_fallback_por_timeout_en_etapa_2_si_nunca_cambia()
    test_se_activa_sin_importar_si_la_party_esta_llena_o_no()

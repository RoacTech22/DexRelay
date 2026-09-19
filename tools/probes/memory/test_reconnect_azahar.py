"""
Tests de reconexión (18/09/2026): cerrar Azahar por completo con
DexRelay abierto y volver a abrirlo con el juego dejaba a DexRelay
sin detectarlo hasta reiniciarlo.

Correr: python -m tools.probes.memory.test_reconnect_azahar
"""

from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader


class FakeCitra:
    """Azahar simulado: procesos, proceso seleccionado y 'cerrado'."""

    def __init__(self):
        self.closed = False
        self.processes = {}
        self.selected = 0xFFFFFFFF
        self.set_calls = []

    def get_process(self):
        if self.closed:
            raise ConnectionResetError("Azahar cerrado")
        return self.selected

    def process_list(self):
        if self.closed:
            raise ConnectionResetError("Azahar cerrado")
        return dict(self.processes)

    def set_process(self, process_id):
        if self.closed:
            raise ConnectionResetError("Azahar cerrado")
        self.selected = process_id
        self.set_calls.append(process_id)

    def read_memory(self, address, size):
        return None


class Stub:
    def resolve(self, *args, **kwargs):
        return None


def make_reader(citra, process_name=None):
    return AzaharReader(
        citra=citra,
        species_resolver=Stub(),
        location_resolver=Stub(),
        process_name=process_name,
    )


def cycle(reader):
    """Lo mismo que hace Runtime.update() al principio."""

    if not reader.is_connected():
        return reader.connect()

    return True


def test_reabrir_azahar_con_proceso_por_defecto_equivocado():
    citra = FakeCitra()
    citra.processes = {20: (0x0004000000155100, "sango-2")}
    reader = make_reader(citra)

    assert cycle(reader) is True
    assert reader.process_name == "sango-2" and reader.process_id == 20

    # Se cierra Azahar por completo.
    citra.closed = True
    assert cycle(reader) is False
    assert reader._process_selected is False

    # Se reabre: Azahar nuevo reporta un proceso cualquiera (5) como
    # seleccionado y el juego aparece con otro ID.
    citra.closed = False
    citra.selected = 5
    citra.processes = {5: (1, "menu"), 31: (0x0004000000155100, "sango-2")}
    citra.set_calls.clear()

    assert cycle(reader) is True
    assert citra.set_calls == [31], citra.set_calls
    assert reader.process_id == 31

    print("OK - Azahar reabierto: vuelve a seleccionar el proceso del juego")


def test_reabrir_azahar_con_otro_juego():
    citra = FakeCitra()
    citra.processes = {20: (1, "sango-2")}
    reader = make_reader(citra)
    assert cycle(reader) is True
    assert reader.process_name == "sango-2"

    citra.closed = True
    assert cycle(reader) is False

    citra.closed = False
    citra.selected = 20
    citra.processes = {22: (2, "sango-1")}

    assert cycle(reader) is True
    assert reader.process_name == "sango-1" and reader.process_id == 22

    print("OK - Azahar reabierto con OTRO juego: lo detecta solo")


def test_juego_relanzado_dentro_del_mismo_azahar():
    citra = FakeCitra()
    citra.processes = {20: (1, "sango-2")}
    reader = make_reader(citra)
    assert cycle(reader) is True

    # Mismo Azahar, el juego se cerró y reabrió con otro ID.
    citra.selected = 0xFFFFFFFF
    assert reader.is_connected() is False

    citra.processes = {44: (1, "sango-2")}
    assert cycle(reader) is True and reader.process_id == 44

    citra.selected = 60  # cambió por debajo sin pasar por 0xFFFFFFFF
    assert reader.is_connected() is False

    print("OK - juego relanzado en el mismo Azahar: reconecta")


def test_conexion_normal_no_reconecta_cada_ciclo():
    citra = FakeCitra()
    citra.processes = {20: (1, "sango-2")}
    reader = make_reader(citra)
    cycle(reader)
    citra.set_calls.clear()

    for _ in range(50):
        assert reader.is_connected() is True

    assert citra.set_calls == []

    print("OK - conexión estable: no se vuelve a llamar set_process")


def test_party_vacia_fuerza_reconexion():
    citra = FakeCitra()
    citra.processes = {20: (1, "sango-2")}
    reader = make_reader(citra)
    reader.read_party = lambda: []

    runtime = Runtime.__new__(Runtime)
    runtime.reader = reader
    runtime.state = ApplicationState()
    runtime._empty_party_cycles = 0
    runtime._reset_connection_dependent_state()

    for _ in range(Runtime.EMPTY_PARTY_RECONNECT_CYCLES):
        runtime.update()

    # Después del umbral la conexión se invalidó...
    assert reader._process_selected is False
    # ...y el próximo ciclo vuelve a seleccionar el juego.
    citra.set_calls.clear()
    runtime.update()
    assert citra.set_calls == [20]

    print("OK - party vacía sostenida fuerza reconexión")


def test_corte_en_combate_no_deja_perdido_falso():
    citra = FakeCitra()
    citra.processes = {20: (1, "sango-2")}
    reader = make_reader(citra)

    runtime = Runtime.__new__(Runtime)
    runtime.reader = reader
    runtime.state = ApplicationState()
    runtime._empty_party_cycles = 0
    runtime._reset_connection_dependent_state()

    runtime._combat_was_active = True
    runtime._lost_encounter_snapshot = {"location": "Ruta 101"}
    runtime._pending_lost_resolution = {"location": "Ruta 101"}

    citra.closed = True
    runtime.update()

    assert runtime._combat_was_active is False
    assert runtime._lost_encounter_snapshot is None
    assert runtime._pending_lost_resolution is None
    assert runtime.state.azahar_connected is False

    print("OK - cerrar Azahar en combate no deja un 'perdido' falso")


if __name__ == "__main__":
    test_reabrir_azahar_con_proceso_por_defecto_equivocado()
    test_reabrir_azahar_con_otro_juego()
    test_juego_relanzado_dentro_del_mismo_azahar()
    test_conexion_normal_no_reconecta_cada_ciclo()
    test_party_vacia_fuerza_reconexion()
    test_corte_en_combate_no_deja_perdido_falso()

"""
Bloque 5 (guía siguiente versión, 24/09/2026): identificación de la
PARTIDA por Trainer ID.

Confirmado en vivo por Ronald el 24/09/2026 (investigar_trainer_id.py
--scan) en Alpha Sapphire y Omega Ruby: la tarjeta de entrenador está
en TRAINER_CARD_ADDRESS con TID/SID y el nombre OT a +0x48. Estos tests
cubren la lógica alrededor: lectura validada, archivo por partida con
adopción del archivo por juego, y el gateo de Runtime.
"""

import json
import struct
import tempfile
from pathlib import Path

from app.core.runtime import Runtime
from app.core.state import ApplicationState
from app.games.registry import get_profile

_ORAS_MAP = get_profile("sango-2").memory_map
TRAINER_CARD_ADDRESS = _ORAS_MAP.trainer_card_address
TRAINER_CARD_READ_SIZE = _ORAS_MAP.trainer_card_read_size
from app.readers.azahar_reader import AzaharReader
from app.services.nuzlocke_service import NuzlockeService
from app.services.nuzlocke_storage import NuzlockeStorage


# ---------------- lectura de la tarjeta ----------------

class FakeMemory:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.last_read = None

    def read(self, address, size):
        self.last_read = (address, size)

        if self.error is not None:
            raise self.error

        return self.response


def _card(tid, sid, name):
    data = bytearray(TRAINER_CARD_READ_SIZE)
    struct.pack_into("<HH", data, 0, tid, sid)
    data[0x48:0x48 + 24] = name.encode("utf-16le").ljust(24, b"\x00")
    return bytes(data)


def _reader(memory):
    reader = AzaharReader(process_name="sango-2")
    reader.memory = memory
    return reader


def test_lee_la_identidad_de_la_tarjeta():
    memory = FakeMemory(_card(23756, 50341, "Ronii"))

    identity = _reader(memory).read_trainer_identity()

    assert identity == {"tid": 23756, "sid": 50341, "ot": "Ronii"}
    assert memory.last_read == (TRAINER_CARD_ADDRESS, TRAINER_CARD_READ_SIZE)


def test_lecturas_dudosas_devuelven_none():
    assert _reader(FakeMemory(None)).read_trainer_identity() is None
    assert _reader(FakeMemory(b"\x00" * 10)).read_trainer_identity() is None
    assert _reader(FakeMemory(error=OSError())).read_trainer_identity() is None
    # menú sin partida cargada: todo en cero
    assert _reader(FakeMemory(_card(0, 0, ""))).read_trainer_identity() is None
    # nombre con caracteres de control
    assert _reader(FakeMemory(_card(1, 2, "ab\x01"))).read_trainer_identity() is None


# ---------------- archivo por partida ----------------

def _write_game_file(directory, slug, roster_nicknames):
    path = Path(directory) / f"nuzlocke_{slug}.json"
    path.write_text(
        json.dumps({"roster": [{"nickname": n} for n in roster_nicknames]}),
        encoding="utf-8",
    )
    return path


def test_adopta_el_archivo_por_juego_si_es_de_esta_partida():
    with tempfile.TemporaryDirectory() as tmp:
        legacy = _write_game_file(
            tmp, "alpha_sapphire", ["Tiny", "Nuvia", "YER", "ERT", "Bibi", "Daron"]
        )

        storage = NuzlockeStorage.for_identity(
            "sango-2", 23756, 50341,
            {"Tiny", "Nuvia", "YER", "Alex", "Fasr"},
            data_dir=tmp,
        )

        assert storage.path.name == "nuzlocke_alpha_sapphire_23756_50341.json"
        assert storage.path.exists()
        assert not legacy.exists()


def test_no_adopta_el_archivo_de_otra_partida_y_lo_deja_intacto():
    with tempfile.TemporaryDirectory() as tmp:
        legacy = _write_game_file(tmp, "omega_ruby", ["LK", "RE", "WEY"])

        storage = NuzlockeStorage.for_identity(
            "sango-1", 29153, 54059,
            {"Cata", "Neva", "Aby", "Alf"},
            data_dir=tmp,
        )

        assert storage.path.name == "nuzlocke_omega_ruby_29153_54059.json"
        assert not storage.path.exists()
        assert legacy.exists()


def test_un_solo_nickname_en_comun_no_alcanza_con_varios_guardados():
    with tempfile.TemporaryDirectory() as tmp:
        legacy = _write_game_file(tmp, "omega_ruby", ["Daron", "LK", "RE"])

        NuzlockeStorage.for_identity(
            "sango-1", 1, 2, {"Daron", "Otro"}, data_dir=tmp
        )

        assert legacy.exists()


def test_la_nicknames_se_evalua_de_forma_perezosa_y_sin_archivo_no_hace_falta():
    calls = []

    with tempfile.TemporaryDirectory() as tmp:
        NuzlockeStorage.for_identity(
            "sango-2", 1, 2, lambda: calls.append(1) or set(), data_dir=tmp
        )

    assert calls == []


def test_si_el_archivo_de_la_partida_ya_existe_no_se_toca_el_del_juego():
    with tempfile.TemporaryDirectory() as tmp:
        legacy = _write_game_file(tmp, "alpha_sapphire", ["A", "B"])
        target = Path(tmp) / "nuzlocke_alpha_sapphire_1_2.json"
        target.write_text("{}", encoding="utf-8")

        NuzlockeStorage.for_identity("sango-2", 1, 2, {"A", "B"}, data_dir=tmp)

        assert legacy.exists()


# ---------------- gateo en Runtime ----------------

class FakeBadgesStorage:
    def save(self, badges):
        pass


class RecordingBadgesStorage:
    def __init__(self, process_name, tid, sid):
        self.key = (process_name, tid, sid)
        self.saved = []

    def save(self, badges):
        self.saved.append(badges)


class FakeBadgesService:
    def read_badges(self):
        return {"value": 0, "count": 0, "badges": [False] * 8}


class FakeCombatService:
    def read(self):
        return None

    def read_wild_flag(self):
        return None

    def read_combat_base_pointer(self):
        return None


def _quiet(runtime):
    """Sin badges/combate reales: estos tests solo miran el Nuzlocke."""

    runtime.badges_storage = FakeBadgesStorage()
    runtime._badges_storage_factory = (
        lambda process_name, tid, sid: RecordingBadgesStorage(
            process_name, tid, sid
        )
    )
    runtime.badges_service = FakeBadgesService()
    runtime.combat_service = FakeCombatService()
    return runtime


class FakeService:
    def __init__(self):
        self.storage = None
        self.updates = 0

    def switch_storage(self, storage):
        self.storage = storage

    def is_started(self):
        return True

    def update(self, party, boxed_party=None, has_pokeballs=None):
        self.updates += 1
        return {"roster": [], "graveyard": []}

    def register_lost_encounter(self, *args, **kwargs):
        raise AssertionError("no debería registrarse nada")


class FakeReader:
    def __init__(self):
        self.process_name = "sango-2"
        self.memory = FakeMemory(None)
        self.identities = []
        self.reads = 0

    def is_connected(self):
        return True

    def connect(self):
        return True

    def read_party(self):
        return [{"slot": 1, "nickname": "Tiny", "empty": False}]

    def read_boxes_range(self):
        return []

    def read_has_pokeballs(self):
        return True

    def read_trainer_identity(self):
        self.reads += 1
        index = min(self.reads - 1, len(self.identities) - 1)
        return self.identities[index]

    def invalidate_connection(self):
        pass


class FakeStorage:
    def __init__(self, label):
        self.path = Path(f"{label}.json")


def _runtime(reader, service, resolved):
    def resolver(process_name, identity, nicknames):
        resolved.append((process_name, identity))
        return FakeStorage(
            "juego" if identity is None else f"{identity['tid']}"
        )

    runtime = Runtime(
        reader,
        ApplicationState(),
        nuzlocke_service=service,
        storage_resolver=resolver,
    )
    return _quiet(runtime)


A = {"tid": 1, "sid": 2, "ot": "Ronii"}
B = {"tid": 3, "sid": 4, "ot": "Ronii"}


def test_no_rastrea_hasta_confirmar_la_identidad_dos_lecturas_iguales():
    reader = FakeReader()
    reader.identities = [A]
    service = FakeService()
    resolved = []
    runtime = _runtime(reader, service, resolved)

    runtime.update()
    assert service.updates == 0
    assert service.storage is None

    runtime.update()
    assert service.updates == 1
    assert service.storage.path.name == "1.json"
    assert runtime.state.trainer == A


def test_una_lectura_basura_aislada_no_cambia_de_partida():
    reader = FakeReader()
    reader.identities = [A, A, B, A, A]
    service = FakeService()
    runtime = _runtime(reader, service, [])

    for _ in range(5):
        runtime.update()

    assert runtime.state.trainer == A
    assert service.storage.path.name == "1.json"


def test_cambio_real_de_partida_cambia_el_archivo_tras_confirmar():
    reader = FakeReader()
    reader.identities = [A, A, B, B]
    service = FakeService()
    runtime = _runtime(reader, service, [])

    for _ in range(4):
        runtime.update()

    assert runtime.state.trainer == B
    assert service.storage.path.name == "3.json"


def test_identidad_ilegible_mucho_tiempo_cae_al_archivo_por_juego():
    reader = FakeReader()
    reader.identities = [None]
    service = FakeService()
    resolved = []
    runtime = _runtime(reader, service, resolved)

    for _ in range(Runtime.TRAINER_FALLBACK_CYCLES + 1):
        runtime.update()

    assert resolved[-1] == ("sango-2", None)
    assert service.storage.path.name == "juego.json"
    assert service.updates >= 1


def test_sin_resolver_todo_funciona_como_antes():
    reader = FakeReader()
    service = FakeService()
    runtime = _quiet(
        Runtime(reader, ApplicationState(), nuzlocke_service=service)
    )

    runtime.update()

    assert service.updates == 1
    assert reader.reads == 0


# ---------------- medallas por partida ----------------

def test_las_medallas_no_se_guardan_hasta_identificar_la_partida():
    reader = FakeReader()
    reader.identities = [A]
    service = FakeService()
    runtime = _runtime(reader, service, [])

    runtime.update()

    # Primer ciclo: identidad sin confirmar -> nada se guardó, ni en
    # el archivo viejo ni en uno de otra partida.
    assert runtime.badges_storage.__class__ is FakeBadgesStorage
    assert runtime.state.badges == {"value": 0, "count": 0, "badges": [False] * 8}


def test_las_medallas_van_al_archivo_de_la_partida_y_se_guardan_al_cambiar():
    reader = FakeReader()
    reader.identities = [A, A, B, B]
    service = FakeService()
    runtime = _runtime(reader, service, [])

    runtime.update()
    runtime.update()

    assert runtime.badges_storage.key == ("sango-2", 1, 2)
    assert len(runtime.badges_storage.saved) == 1

    runtime.update()
    runtime.update()

    # Cambio de partida: archivo nuevo y se escribe la lectura actual.
    assert runtime.badges_storage.key == ("sango-2", 3, 4)
    assert len(runtime.badges_storage.saved) == 1


def test_badges_storage_for_identity_arma_el_nombre_por_partida():
    from app.services.badges_storage import BadgesStorage

    with tempfile.TemporaryDirectory() as tmp:
        storage = BadgesStorage.for_identity(
            "sango-1", 29153, 54059, data_dir=tmp
        )

    assert storage.path.name == "badges_omega_ruby_29153_54059.json"

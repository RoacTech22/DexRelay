"""
Tarjeta "próximo líder" de la pestaña Bosses (P4, 07/10/2026): con las 8
medallas pasa al Alto Mando. Necesita `webview` (importa api_leaders), así que
se salta donde no esté instalado.
"""

import pytest

pytest.importorskip("webview")

from app.gui_web.api_leaders import LeadersMixin  # noqa: E402
from app.services.kalos_leaders import KALOS_LEADER_SPEC  # noqa: E402
from tests.test_boss_data import _catalog  # noqa: E402


class _Boss(LeadersMixin):
    def __init__(self, leaders, badges):
        self._leaders = leaders
        self.app = type("A", (), {"state": type("S", (), {"badges": badges})()})()

    def _leaders_available(self):
        return True

    def _active_gym_leader_catalog(self):
        leaders = self._leaders

        class _Catalog:
            def list_all(self):
                return leaders

        return _Catalog()

    def _with_resolved_type_keys(self, member):
        return member

    def _with_resolved_move_type_keys(self, member):
        return member


def _badges(count):
    return {"value": 0, "count": count, "badges": [i < count for i in range(8)]}


def test_la_tarjeta_siguiente_es_el_primer_lider_sin_medalla():
    boss = _Boss(_catalog(KALOS_LEADER_SPEC).list_all(), _badges(3))
    leaders = boss._gym_leaders_with_earned()
    nxt = boss._next_boss(leaders)

    assert nxt["nameEs"] == "Amaro" and not nxt.get("isLeague")
    assert [leader["earned"] for leader in leaders[:4]] == [True, True, True, False]
    assert not any(leader["earned"] for leader in leaders[8:])


def test_con_las_8_medallas_la_tarjeta_pasa_al_alto_mando():
    for spec, cap, first in ((None, 52, "Sixto"), (KALOS_LEADER_SPEC, 65, "Malva")):
        boss = _Boss(_catalog(spec).list_all(), _badges(8))
        nxt = boss._next_boss(boss._gym_leaders_with_earned())

        assert nxt["isLeague"] is True
        assert nxt["levelCap"] == cap
        assert nxt["order"] == 9
        assert nxt["members"][0]["nameEs"] == first
        assert len(nxt["members"]) == 5
        assert nxt["members"][-1]["kind"] == "champion"


def test_sin_datos_de_liga_con_8_medallas_no_hay_tarjeta_como_antes():
    gyms = [l for l in _catalog().list_all() if l["kind"] == "gym"]
    boss = _Boss(gyms, _badges(8))

    assert boss._next_boss(boss._gym_leaders_with_earned()) is None

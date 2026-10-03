"""
Bug real (03/10/2026): con el hackroom activo, los iniciales
(Mudkip/Torchic/Treecko) mostraban siempre la habilidad oculta
(Damp/Speed Boost/Unburden) aunque en el juego llevaban la normal.
El override de habilidad del Pokémon vivo se aplicaba sin comprobar
qué slot lleva realmente (AbilityNumber, byte 0x15 del PK6).
"""

from app.gui_web.api_hackroom import HackroomMixin


class _FakeConfig:
    def get(self, *args, **kwargs):
        return True


class _FakeApp:
    config = _FakeConfig()


class _Api(HackroomMixin):
    def __init__(self, changes):
        self.app = _FakeApp()
        self._hackroom_pokemon_changes_by_species = changes
        self._hackroom_attack_changes_by_move = {}

    def _resolve_hackroom_ability(self, name):
        return {"Damp": 6, "Torrent": 67}.get(name), name


def _raw(ability_number):
    data = bytearray(232)
    data[0x15] = ability_number
    return bytes(data)


def _details():
    return {"abilityId": 67, "abilityName": "Torrente", "moves": []}


CHANGES = {258: {"ability2": "Damp"}}


def test_inicial_con_habilidad_1_no_se_pisa_con_la_2():
    api = _Api(CHANGES)

    result = api._apply_hackroom_pokemon_changes_to_live_detail(
        258, _details(), raw_data=_raw(1)
    )

    assert result["abilityId"] == 67
    assert result["abilityName"] == "Torrente"


def test_pokemon_con_habilidad_2_si_recibe_el_cambio():
    api = _Api(CHANGES)

    result = api._apply_hackroom_pokemon_changes_to_live_detail(
        258, _details(), raw_data=_raw(2)
    )

    assert result["abilityId"] == 6
    assert result["abilityName"] == "Damp"


def test_habilidad_oculta_o_slot_desconocido_no_se_toca():
    api = _Api(CHANGES)

    for number in (0, 4):
        result = api._apply_hackroom_pokemon_changes_to_live_detail(
            258, _details(), raw_data=_raw(number)
        )
        assert result["abilityId"] == 67

    result = api._apply_hackroom_pokemon_changes_to_live_detail(
        258, _details(), raw_data=None
    )
    assert result["abilityId"] == 67


def test_ambos_slots_cambiados_cada_uno_aplica_al_suyo():
    api = _Api({258: {"ability1": "Torrent", "ability2": "Damp"}})

    r1 = api._apply_hackroom_pokemon_changes_to_live_detail(
        258, {"abilityId": 1, "abilityName": "x", "moves": []},
        raw_data=_raw(1),
    )
    r2 = api._apply_hackroom_pokemon_changes_to_live_detail(
        258, {"abilityId": 1, "abilityName": "x", "moves": []},
        raw_data=_raw(2),
    )

    assert r1["abilityName"] == "Torrent"
    assert r2["abilityName"] == "Damp"


if __name__ == "__main__":
    test_inicial_con_habilidad_1_no_se_pisa_con_la_2()
    test_pokemon_con_habilidad_2_si_recibe_el_cambio()
    test_habilidad_oculta_o_slot_desconocido_no_se_toca()
    test_ambos_slots_cambiados_cada_uno_aplica_al_suyo()
    print("OK - tests de habilidad viva con hackroom pasaron")

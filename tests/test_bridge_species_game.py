"""
P6: `PKHeXBridge.species_details` acepta `game` opcional. Sin él, el
pedido es idéntico al de siempre (los llamadores existentes no cambian).
"""

from app.services.pkhex.bridge import PKHeXBridge


class _Capturador(PKHeXBridge):
    def __init__(self):
        super().__init__()
        self.enviados = []

    def request(self, payload):
        self.enviados.append(payload)
        return {"id": payload["id"]}


def test_sin_game_el_pedido_es_el_de_siempre():
    bridge = _Capturador()

    bridge.species_details(25)

    assert bridge.enviados == [{"action": "species_details", "id": 25}]


def test_con_game_se_envia_en_el_pedido():
    bridge = _Capturador()

    bridge.species_details(25, game="X")

    assert bridge.enviados == [
        {"action": "species_details", "id": 25, "game": "X"}
    ]

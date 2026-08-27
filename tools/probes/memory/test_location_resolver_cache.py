"""
Reproduce el bug real reportado (26/08/2026): un Pokémon recién
atrapado se lee por primera vez mientras el juego todavía no
terminó de escribir el lugar de encuentro (metLocation vacío). Si
el nickname no cambia en lecturas siguientes -- porque el jugador
tarda mucho en decidir, o porque elige no ponerle nombre y se queda
con el de la especie -- el resultado vacío no debe quedar cacheado
para siempre: en cuanto el bridge pueda resolverlo de verdad, la
próxima lectura con ese mismo nickname debe traer el dato correcto.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.services.location_resolver import LocationResolver


class FakeBridge:
    """Simula el bridge PKHeX devolviendo primero vacío (el juego
    todavía no escribió Met_Location) y después el dato real."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def met_location(self, decrypted_box_data):
        self.calls += 1
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def test_no_cachea_resultado_vacio_reintenta_hasta_resolver():
    bridge = FakeBridge([
        {"metLocationId": 0, "metLocationName": "", "shiny": False},
        {"metLocationId": 0, "metLocationName": "", "shiny": False},
        {"metLocationId": 999999, "metLocationName": "Route 102", "shiny": False},
    ])
    resolver = LocationResolver(bridge=bridge)

    # El jugador tarda en decidir -- muchas lecturas seguidas con el
    # mismo nickname por defecto, mientras el juego todavía no
    # terminó de escribir la ruta.
    r1 = resolver.resolve("Weedle", b"x")
    assert r1["metLocation"] == ""

    r2 = resolver.resolve("Weedle", b"x")
    assert r2["metLocation"] == ""

    # El juego ya terminó de escribir -- la SIGUIENTE lectura con el
    # MISMO nickname (nunca cambió, el jugador no le puso nombre)
    # debe traer el dato real, no quedarse pegada en el vacío.
    r3 = resolver.resolve("Weedle", b"x")
    assert r3["metLocation"] == "Route 102"

    # Ahora que se resolvió, sí debe quedar cacheado -- no debe
    # volver a llamar al bridge para el mismo nickname.
    calls_before = bridge.calls
    r4 = resolver.resolve("Weedle", b"x")
    assert r4["metLocation"] == "Route 102"
    assert bridge.calls == calls_before  # no llamó de nuevo

    print(
        "OK - un resultado vacío no se cachea para siempre, se "
        "reintenta hasta resolver; uno exitoso sí se cachea"
    )


def test_resultado_exitoso_se_cachea_de_inmediato():
    bridge = FakeBridge([
        {"metLocationId": 999999, "metLocationName": "Route 102", "shiny": False},
    ])
    resolver = LocationResolver(bridge=bridge)

    r1 = resolver.resolve("Pandy", b"x")
    assert r1["metLocation"] == "Route 102"

    calls_before = bridge.calls
    r2 = resolver.resolve("Pandy", b"x")
    assert r2["metLocation"] == "Route 102"
    assert bridge.calls == calls_before

    print("OK - un resultado exitoso se cachea desde la primera vez")


if __name__ == "__main__":
    test_no_cachea_resultado_vacio_reintenta_hasta_resolver()
    test_resultado_exitoso_se_cachea_de_inmediato()

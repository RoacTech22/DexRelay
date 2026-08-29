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


def test_placeholder_none_se_trata_como_vacio():
    """
    Bug real reportado el 28/08/2026: PKHeX devuelve el texto
    literal "(None)" (no un string vacío) cuando el ID de
    metLocation todavía no es válido -- el usuario lo vio
    específicamente con capturas SIN nombre (nickname por defecto),
    registradas con "(None)" como si fuera una ruta real. Se filtra
    acá para que quede como vacío -- ni se cachea, ni se trata como
    resuelto, se reintenta igual que un resultado genuinamente
    vacío.
    """

    bridge = FakeBridge([
        {
            "metLocationId": 0,
            "metLocationName": "(None)",
            "shiny": False,
        },
        {
            "metLocationId": 0,
            "metLocationName": "(None)",
            "shiny": False,
        },
        {
            "metLocationId": 999999,
            "metLocationName": "Route 101",
            "shiny": False,
        },
    ])

    resolver = LocationResolver(bridge=bridge)

    r1 = resolver.resolve("Zigzagoon", b"x")
    assert r1["metLocation"] == ""

    r2 = resolver.resolve("Zigzagoon", b"x")
    assert r2["metLocation"] == ""

    # El juego termina de escribir el dato real -- la siguiente
    # lectura con el mismo nickname debe traerlo, no quedarse
    # pegada en "(None)".
    r3 = resolver.resolve("Zigzagoon", b"x")
    assert r3["metLocation"] == "Route 101"

    print(
        'OK - el placeholder "(None)" de PKHeX se trata como '
        "vacío, no como una ruta real -- se reintenta hasta que "
        "resuelve el dato de verdad"
    )


def test_placeholder_none_tambien_aplica_a_egg_location():

    bridge = FakeBridge([
        {
            "metLocationId": 0,
            "metLocationName": "",
            "eggLocationId": 0,
            "eggLocationName": "(None)",
            "shiny": False,
        },
        {
            "metLocationId": 0,
            "metLocationName": "",
            "eggLocationId": 55,
            "eggLocationName": "Anciana del Balneario",
            "shiny": False,
        },
    ])

    resolver = LocationResolver(bridge=bridge)

    r1 = resolver.resolve("Togepi", b"x")
    assert r1["eggLocation"] == ""

    r2 = resolver.resolve("Togepi", b"x")
    assert r2["eggLocation"] == "Anciana del Balneario"

    print(
        'OK - el placeholder "(None)" también se filtra en '
        "eggLocation"
    )


def test_isEgg_se_propaga_y_se_cachea_aunque_todo_lo_demas_este_vacio():
    """
    29/08/2026, a pedido del usuario: species_id de un huevo sin
    nacer ya resuelve la especie real -- el Team Overlay necesita
    saber que ES un huevo para mostrar el sprite genérico en vez
    de la especie real (spoiler). A diferencia de metLocation/
    eggLocation, `isEgg` es un flag fijo del PK6 (no depende de
    ningún cuadro de diálogo ni escritura progresiva) -- tiene que
    quedar disponible y cachearse desde la primera lectura, aunque
    metLocation y eggLocation sigan vacíos por mucho tiempo
    (huevo real, todavía sin nacer, puede ser por miles de pasos).
    """

    bridge = FakeBridge([
        {
            "metLocationId": 0,
            "metLocationName": "",
            "eggLocationId": 0,
            "eggLocationName": "",
            "shiny": False,
            "isEgg": True,
        },
    ])

    resolver = LocationResolver(bridge=bridge)

    r1 = resolver.resolve("Huevo", b"x")
    assert r1["isEgg"] is True
    assert r1["metLocation"] == ""

    # Se cachea de inmediato -- no debe golpear el bridge de nuevo
    # aunque metLocation/eggLocation sigan vacíos.
    calls_before = bridge.calls
    r2 = resolver.resolve("Huevo", b"x")
    assert r2["isEgg"] is True
    assert bridge.calls == calls_before

    print(
        "OK - isEgg se propaga y se cachea desde la primera "
        "lectura, aunque metLocation y eggLocation sigan vacíos"
    )


def test_isEgg_false_para_una_captura_normal():

    bridge = FakeBridge([
        {
            "metLocationId": 999999,
            "metLocationName": "Route 102",
            "shiny": False,
            "isEgg": False,
        },
    ])

    resolver = LocationResolver(bridge=bridge)

    r1 = resolver.resolve("Zubat", b"x")
    assert r1["isEgg"] is False
    assert r1["metLocation"] == "Route 102"

    print(
        "OK - una captura salvaje normal (no huevo) resuelve "
        "isEgg=False"
    )


if __name__ == "__main__":
    test_no_cachea_resultado_vacio_reintenta_hasta_resolver()
    test_resultado_exitoso_se_cachea_de_inmediato()
    test_placeholder_none_se_trata_como_vacio()
    test_placeholder_none_tambien_aplica_a_egg_location()
    test_isEgg_se_propaga_y_se_cachea_aunque_todo_lo_demas_este_vacio()
    test_isEgg_false_para_una_captura_normal()

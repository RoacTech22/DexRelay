"""
Valida la traducción manual de "Entregado por" (eggLocation) al
español, para los casos donde PKHeX.Core no trae el string en
español para ese ID puntual y devuelve inglés (bug real reportado
el 28/08/2026, ver app/services/egg_locations_es.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.services.egg_locations_es import translate_egg_location_name
from app.services.location_resolver import LocationResolver


def test_traduce_texto_conocido():

    assert (
        translate_egg_location_name(
            "an old hot-springs visitor"
        )
        == "Anciana del Balneario"
    )

    # No debe importar mayúsculas ni espacios de más.
    assert (
        translate_egg_location_name(
            "  AN OLD HOT-SPRINGS VISITOR  "
        )
        == "Anciana del Balneario"
    )

    print(
        "OK - traduce el texto en inglés conocido a la versión "
        "en español, sin importar mayúsculas/espacios"
    )


def test_texto_desconocido_pasa_tal_cual():

    assert (
        translate_egg_location_name("some unmapped npc")
        == "some unmapped npc"
    )

    assert translate_egg_location_name("") == ""
    assert translate_egg_location_name(None) is None

    print(
        "OK - un texto sin traducción confirmada pasa tal cual "
        "(no se inventa nada)"
    )


class FakeBridge:
    def __init__(self, response):
        self.response = response

    def met_location(self, decrypted_box_data):
        return self.response


def test_location_resolver_aplica_la_traduccion():
    """
    LocationResolver.resolve() tiene que aplicar la traducción de
    eggLocation automáticamente, igual que ya hace con
    metLocation.
    """

    bridge = FakeBridge({
        "metLocationId": 0,
        "metLocationName": "",
        "eggLocationId": 55,
        "eggLocationName": "an old hot-springs visitor",
        "shiny": False,
    })

    resolver = LocationResolver(bridge=bridge)

    info = resolver.resolve("Togepi", b"\x00" * 232)

    assert info["eggLocation"] == "Anciana del Balneario"

    print(
        "OK - LocationResolver aplica la traducción de "
        "eggLocation automáticamente"
    )


def test_location_resolver_no_confunde_id_cero_con_huevo():
    """
    eggLocationId == 0 (nunca fue huevo) debe llegar como
    eggLocation="" -- el bridge ya lo corta ahí (28/08/2026), pero
    este test confirma que LocationResolver no rompe ni inventa
    nada si de todas formas llegara un eggLocationName vacío.
    """

    bridge = FakeBridge({
        "metLocationId": 23,
        "metLocationName": "Ruta 101",
        "eggLocationId": 0,
        "eggLocationName": "",
        "shiny": False,
    })

    resolver = LocationResolver(bridge=bridge)

    info = resolver.resolve("Zigzagoon", b"\x00" * 232)

    assert info["eggLocation"] == ""
    assert info["metLocation"] == "Ruta 101"

    print(
        "OK - eggLocationId 0 -> eggLocation vacío, no se "
        "confunde con un huevo real"
    )


if __name__ == "__main__":
    test_traduce_texto_conocido()
    test_texto_desconocido_pasa_tal_cual()
    test_location_resolver_aplica_la_traduccion()
    test_location_resolver_no_confunde_id_cero_con_huevo()

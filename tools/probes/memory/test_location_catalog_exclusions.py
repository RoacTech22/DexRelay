"""
Valida el cierre de las traducciones faltantes de Hoenn
(29/08/2026, a pedido del usuario) y la exclusión explícita de
ubicaciones no relevantes para un Nuzlocke normal (mirage spots
de DexNav, cuevas de los Regis, base secreta del jugador).

Dos cosas separadas:
1. hoenn_locations_es.py: 4 traducciones nuevas confirmadas por
   el usuario (Shoal Cave, Sea Mauville, Scorched Slab, Soaring
   in the sky).
2. location_catalog.py: 13 ubicaciones excluidas del catálogo
   precargado del panel -- deliberadamente NO se traducen ni se
   muestran como fila esperando captura.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.services.hoenn_locations_es import translate_location_name
from app.services.location_catalog import (
    EXCLUDED_LOCATION_IDS,
    LocationCatalog,
)


class FakeBridge:
    """
    Simula el bridge PKHeX con una lista cruda mínima que incluye
    tanto ubicaciones normales de Hoenn como las 13 excluidas y
    las 4 recién traducidas -- no depende del caché real en
    disco, para que el test sea autocontenido.
    """

    def location_list(self):
        return {
            "locations": [
                {"id": 170, "name": "Littleroot Town"},
                {"id": 204, "name": "Route 101"},
                {"id": 276, "name": "???"},
                {"id": 300, "name": "Shoal Cave"},
                {"id": 304, "name": "Sea Mauville"},
                {"id": 312, "name": "Scorched Slab"},
                {"id": 348, "name": "Soaring in the sky"},
                {"id": 278, "name": "Desert Ruins"},
                {"id": 306, "name": "Island Cave"},
                {"id": 308, "name": "Ancient Tomb"},
                {"id": 310, "name": "Sealed Chamber"},
                {"id": 334, "name": "Trackless Forest"},
                {"id": 336, "name": "Pathless Plain"},
                {"id": 338, "name": "Nameless Cavern"},
                {"id": 340, "name": "Fabled Cave"},
                {"id": 342, "name": "Gnarled Den"},
                {"id": 344, "name": "Crescent Isle"},
                {"id": 354, "name": "Secret Base"},
                {"id": 350, "name": "Secret Shore"},
                {"id": 352, "name": "Secret Meadow"},
                # Fuera del rango de Hoenn -- nunca debe aparecer.
                {"id": 2, "name": "Vaniville Town"},
            ]
        }


def test_las_cuatro_traducciones_nuevas_resuelven_bien():

    assert translate_location_name(300, "Shoal Cave") == (
        "Cueva Cardumen"
    )
    assert translate_location_name(304, "Sea Mauville") == (
        "Malvamar"
    )
    assert translate_location_name(312, "Scorched Slab") == (
        "Gruta Solar"
    )
    assert translate_location_name(
        348, "Soaring in the sky"
    ) == "Firmamento"

    print(
        "OK - las 4 traducciones nuevas (Cueva Cardumen, "
        "Malvamar, Gruta Solar, Firmamento) resuelven bien por ID"
    )


def test_las_13_excluidas_no_aparecen_en_el_catalogo():

    catalog = LocationCatalog(
        bridge=FakeBridge(),
        cache_path="/tmp/dexrelay_test_location_cache_no_existe.json",
    )

    locations = catalog.list_all()
    ids = {entry["id"] for entry in locations}

    assert len(EXCLUDED_LOCATION_IDS) == 14
    assert ids.isdisjoint(EXCLUDED_LOCATION_IDS)

    # Las normales SÍ siguen apareciendo.
    assert 170 in ids
    assert 204 in ids
    assert 300 in ids
    assert 304 in ids

    # Fuera de rango de Hoenn, tampoco.
    assert 2 not in ids

    print(
        "OK - las 13 ubicaciones excluidas no aparecen en el "
        "catálogo precargado del panel, el resto sigue normal"
    )


def test_ubicaciones_normales_y_nuevas_traducen_en_el_catalogo():

    catalog = LocationCatalog(
        bridge=FakeBridge(),
        cache_path="/tmp/dexrelay_test_location_cache_no_existe.json",
    )

    by_id = {
        entry["id"]: entry["name"]
        for entry in catalog.list_all()
    }

    assert by_id[170] == "Villa Raíz"
    assert by_id[300] == "Cueva Cardumen"
    assert by_id[304] == "Malvamar"

    print(
        "OK - el catálogo aplica la traducción al español a las "
        "ubicaciones normales y a las 4 recién agregadas por igual"
    )


if __name__ == "__main__":
    test_las_cuatro_traducciones_nuevas_resuelven_bien()
    test_las_13_excluidas_no_aparecen_en_el_catalogo()
    test_ubicaciones_normales_y_nuevas_traducen_en_el_catalogo()

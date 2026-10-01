"""
Bloque 9.2 (01/10/2026): un único PKHeXBridge para toda la aplicación.

Antes, 9 servicios arrancaban su propio proceso .NET si nadie les
pasaba un bridge (y el patrón ya causó el bug de respuesta cruzada de
la sección 6.9 del Documento Maestro). Estos tests fijan que:

- PKHeXBridge.shared() devuelve siempre la misma instancia, también
  desde varios hilos a la vez.
- Todos los servicios, construidos SIN bridge, caen a esa instancia
  (un servicio olvidado en el cableado ya no crea un segundo proceso).
- Un bridge pasado explícitamente se respeta (tests/probes con fakes).
- Nadie en app/ vuelve a hacer `PKHeXBridge()` por su cuenta fuera de
  la propia clase (guarda estática contra regresiones).
"""

import re
import threading
from pathlib import Path

import pytest

from app.services.ability_catalog import AbilityCatalog
from app.services.item_catalog import ItemCatalog
from app.services.location_catalog import LocationCatalog
from app.services.location_resolver import LocationResolver
from app.services.move_catalog import MoveCatalog
from app.services.pkhex.bridge import PKHeXBridge
from app.services.playtime_service import PlaytimeService
from app.services.pokemon_detail_resolver import PokemonDetailResolver
from app.services.species_catalog import SpeciesCatalog
from app.services.species_resolver import SpeciesResolver

SERVICES = [
    AbilityCatalog,
    ItemCatalog,
    LocationCatalog,
    LocationResolver,
    MoveCatalog,
    PlaytimeService,
    PokemonDetailResolver,
    SpeciesCatalog,
    SpeciesResolver,
]


def test_shared_returns_the_same_instance():
    assert PKHeXBridge.shared() is PKHeXBridge.shared()


def test_shared_is_thread_safe():
    results = []

    def grab():
        results.append(PKHeXBridge.shared())

    threads = [threading.Thread(target=grab) for _ in range(20)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len({id(bridge) for bridge in results}) == 1


@pytest.mark.parametrize("service_class", SERVICES)
def test_services_without_bridge_use_the_shared_one(service_class):
    service = service_class()

    assert service.bridge is PKHeXBridge.shared()


@pytest.mark.parametrize("service_class", SERVICES)
def test_services_respect_an_explicit_bridge(service_class):
    fake = object()

    assert service_class(bridge=fake).bridge is fake


def test_nobody_in_app_creates_its_own_bridge():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    bridge_file = app_dir / "services" / "pkhex" / "bridge.py"
    offenders = []

    for path in app_dir.rglob("*.py"):
        if path == bridge_file:
            continue

        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            code = line.split("#", 1)[0]

            if re.search(r"\bPKHeXBridge\(\)", code):
                offenders.append(f"{path.name}:{number}")

    assert offenders == []

"""
Descarga los íconos de ítem (07/09/2026, roadmap 4.2 -- el modal de
evolución necesita mostrar el objeto puntual en varios de los 33
methodKey confirmados) desde el repo `PokeAPI/sprites` -- mismo
ecosistema/organización que ya usan los otros scripts de curación
de este proyecto (moves.csv/abilities.csv/items.csv vienen de
`PokeAPI/pokeapi`, esto viene de `PokeAPI/sprites`, ambos con
licencia permisiva y mantenidos por el mismo equipo).

A diferencia de los `build_*.py` de esta carpeta (que arman un JSON
a partir de CSV), esto descarga archivos BINARIOS (PNG) directo a
`assets/items/{id}.png` -- mismo directorio que ya sirve
`app/server/http_server.py` vía `_serve_item_sprite()`
(`/sprites/items/{id}.png`).

No todos los ~2223 ítems de PokéAPI tienen sprite en este repo
(algunos son de generaciones/mecánicas muy nuevas, ver el mismo
patrón ya visto en build_item_descriptions.py) -- un 404 puntual se
salta con gracia, no aborta la corrida completa.

USO:
    python -m tools.data_curation.download_item_sprites

Tarda un rato (una descarga HTTP por ítem, con una pausa chica
entre cada una). Se corre UNA vez -- los PNG quedan commiteados
como asset estático, la app en producción nunca vuelve a pedir
nada por red para esto.
"""

import time
import urllib.error
import urllib.request

from app.core import paths
from tools.data_curation.build_move_data import fetch_csv_rows


ITEMS_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/items.csv"
)

ITEM_SPRITE_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
    "sprites/items/{identifier}.png"
)

OUTPUT_DIRECTORY = paths.path("assets", "items")

REQUEST_DELAY_SECONDS = 0.05


def download_sprite(identifier):
    """
    Descarga un sprite puntual. Devuelve los bytes del PNG, o None
    si no existe en el repo (404) -- distinto de una falla de red
    real, que si se propaga (mismo criterio que fetch_json/
    fetch_csv_rows: un error real no se traga en silencio, solo el
    caso esperado de "este ítem no tiene ícono").
    """

    url = ITEM_SPRITE_URL_TEMPLATE.format(identifier=identifier)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DexRelay-DataCuration/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def main():
    print("================================")
    print("   DESCARGAR SPRITES DE ÍTEM")
    print("================================")
    print()

    print("Descargando items.csv...")
    item_rows = fetch_csv_rows(ITEMS_CSV_URL)
    print(f"  {len(item_rows)} ítems encontrados en total.")
    print()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    missing = []
    failed = []

    total = len(item_rows)

    for index, row in enumerate(item_rows, start=1):

        item_id = row["id"]
        identifier = row["identifier"]

        try:
            sprite_bytes = download_sprite(identifier)
        except Exception as error:
            failed.append((identifier, str(error)))
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if sprite_bytes is None:
            missing.append(identifier)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        output_path = OUTPUT_DIRECTORY / f"{item_id}.png"

        with open(output_path, "wb") as file:
            file.write(sprite_bytes)

        downloaded += 1

        if index % 100 == 0 or index == total:
            print(f"  ... {index}/{total}")

        time.sleep(REQUEST_DELAY_SECONDS)

    print()
    print(f"Sprites descargados: {downloaded}")
    print(f"Sin sprite en el repo (404, normal): {len(missing)}")

    if failed:
        print()
        print(
            f"Aviso: {len(failed)} ítem(s) fallaron por un error "
            "de red real (no 404) -- revisar si hace falta "
            "reintentar:"
        )
        for identifier, error in failed[:20]:
            print(f"    - {identifier}: {error}")

    print()
    print(f"Guardado en: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()

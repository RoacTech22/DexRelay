"""
Descarga el artwork oficial ("official-artwork", hasta 475x475px)
de cada especie 1-721 desde el repo PokeAPI/sprites -- mismo repo
ya usado para íconos de ítem, mismo criterio de licencia (ISC).

Para el modal Pokédex de especie (roadmap 07/09/2026, a pedido del
usuario: "quiero que quede exacto al mockup" -- el mockup muestra
el artwork grande, no el ícono chico ya usado en el resto de la
app).

USO:
    python -m tools.data_curation.download_species_artwork
"""

import time
import urllib.error
import urllib.request

from app.core import paths


ARTWORK_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
    "sprites/pokemon/other/official-artwork/{species_id}.png"
)

OUTPUT_DIRECTORY = paths.path("assets", "species_artwork")

REQUEST_DELAY_SECONDS = 0.05

LAST_SPECIES_ID_UP_TO_KALOS = 721


def download_sprite(species_id):

    url = ARTWORK_URL_TEMPLATE.format(species_id=species_id)

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
    print("   DESCARGAR ARTWORK DE ESPECIE")
    print("================================")
    print()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    missing = []
    failed = []

    for species_id in range(1, LAST_SPECIES_ID_UP_TO_KALOS + 1):

        try:
            sprite_bytes = download_sprite(species_id)
        except Exception as error:
            failed.append((species_id, str(error)))
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if sprite_bytes is None:
            missing.append(species_id)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        output_path = OUTPUT_DIRECTORY / f"{species_id}.png"

        with open(output_path, "wb") as file:
            file.write(sprite_bytes)

        downloaded += 1

        if species_id % 100 == 0:
            print(f"  ... {species_id}/{LAST_SPECIES_ID_UP_TO_KALOS}")

        time.sleep(REQUEST_DELAY_SECONDS)

    print()
    print(f"Sprites descargados: {downloaded}")
    print(f"Sin sprite en el repo (404): {len(missing)}")

    if missing:
        print(f"  ids sin sprite: {missing}")

    if failed:
        print(f"Aviso: {len(failed)} fallaron por error de red real:")
        for species_id, error in failed[:20]:
            print(f"    - #{species_id}: {error}")

    print()
    print(f"Guardado en: {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()

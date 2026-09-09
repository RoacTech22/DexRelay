"""
Curación de una sola vez: índice INVERSO de evolución (de qué
especie evoluciona cada una, si aplica) -- para el modal Pokédex de
especie (roadmap 07/09/2026, a pedido del usuario: "quiero que
quede exacto al mockup", que muestra la cadena completa: pre-
evolución -> especie actual -> evolución siguiente).

`species_details()` del bridge solo devuelve evoluciones HACIA
ADELANTE (a qué evoluciona esta especie) -- no tiene forma de
preguntar "quién evoluciona A esta especie" directamente. En vez de
armar eso en Program.cs (que necesitaría explorar la API de
EvolutionTree más a fondo, con el mismo riesgo de "escrito sin
poder compilar" ya documentado en otros lugares), se arma acá del
lado Python UNA sola vez: recorrer las 721 especies, invertir el
mapa de evoluciones hacia adelante que YA funciona y está probado
(mismo bridge call que ya usa recolectar_evolution_method_keys.py).

USO:
    python -m tools.data_curation.build_pre_evolution_index

No necesita Azahar corriendo -- mismo motivo que los otros probes
de species_details() (resuelve todo desde tablas internas de
PKHeX.Core). Tarda unos segundos por las 721 llamadas al bridge.
"""

import json

from app.core import paths
from app.services.pkhex.bridge import PKHeXBridge


OUTPUT_PATH = paths.path("data", "pre_evolution_index.json")

LAST_SPECIES_ID_UP_TO_KALOS = 721


def main():
    print("=================================================")
    print("   CONSTRUIR ÍNDICE INVERSO DE EVOLUCIÓN")
    print("   (especies 1-721, hasta Gen 6 inclusive)")
    print("=================================================")
    print()

    bridge = PKHeXBridge()

    # species_id (destino) -> {"speciesId", "name"} de quién
    # evoluciona A esa especie -- se arma invirtiendo, para cada
    # especie de origen, su lista de evoluciones hacia adelante.
    pre_evolution_by_species = {}

    failed_species_ids = []

    for species_id in range(1, LAST_SPECIES_ID_UP_TO_KALOS + 1):

        try:
            result = bridge.species_details(species_id)
        except Exception as error:
            failed_species_ids.append((species_id, str(error)))
            continue

        if "error" in result:
            failed_species_ids.append(
                (species_id, result["error"])
            )
            continue

        species_name = result.get("name", f"#{species_id}")

        for evolution in result.get("evolutions", []):

            to_species_id = evolution.get("toSpeciesId")

            if not to_species_id:
                continue

            # Si dos especies distintas dicen evolucionar a la
            # MISMA especie destino (no debería pasar en 1-721,
            # pero mejor no asumir), se queda con la primera
            # encontrada -- señal rara, no un caso esperado.
            pre_evolution_by_species.setdefault(
                to_species_id,
                {"speciesId": species_id, "name": species_name},
            )

        if species_id % 100 == 0:
            print(f"  ... {species_id}/{LAST_SPECIES_ID_UP_TO_KALOS}")

    bridge.stop()

    print()
    print(
        f"Especies con pre-evolución encontrada: "
        f"{len(pre_evolution_by_species)}"
    )

    if failed_species_ids:
        print(
            f"Aviso: {len(failed_species_ids)} especie(s) "
            "fallaron al pedirlas:"
        )
        for species_id, error in failed_species_ids[:20]:
            print(f"    - #{species_id}: {error}")

    print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(
            pre_evolution_by_species,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Guardado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

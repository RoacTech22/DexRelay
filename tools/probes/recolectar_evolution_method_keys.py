"""
Roadmap 06/09/2026, sección 4.2 (última pieza de datos pendiente:
traducir `methodKey` de evolución a español legible). Antes de
armar la tabla de traducción, hace falta saber CUÁLES valores de
`methodKey` existen de verdad entre las especies que DexRelay
puede llegar a mostrar (1-721, hasta Gen 6/Kalos inclusive) --
mismo criterio de siempre: nunca traducir a ciegas un enum que
puede tener variantes de generaciones posteriores que acá nunca van
a aparecer (ORAS no tiene Pokémon de Gen 7+).

Este probe llama a species_details() del bridge PKHeX para las 721
especies reales, junta el conjunto de methodKey distintos que
aparecen en el campo `evolutions`, y por cada uno guarda UN ejemplo
real (species origen/destino, level, argument) -- así la tabla de
traducción se arma mirando casos reales, no a ciegas.

No necesita Azahar corriendo (mismo motivo que
pkhex_species_move_details_probe.py: species_details() resuelve
todo desde las tablas internas de PKHeX.Core, no lee memoria de
ningún juego), pero SÍ tarda unos segundos por las 721 llamadas al
bridge (todas contra el mismo proceso .NET ya levantado, sin
reiniciarlo entre una y otra).

USO:
    python -m tools.probes.recolectar_evolution_method_keys
"""

from app.services.pkhex.bridge import PKHeXBridge


LAST_SPECIES_ID_UP_TO_KALOS = 721


def main():
    print("=================================================")
    print("   RECOLECTAR methodKey DE EVOLUCIÓN REALES")
    print("   (especies 1-721, hasta Gen 6 inclusive)")
    print("=================================================")
    print()

    bridge = PKHeXBridge()

    examples_by_method_key = {}
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

            method_key = evolution.get("methodKey")

            if not method_key:
                continue

            if method_key not in examples_by_method_key:

                examples_by_method_key[method_key] = {
                    "fromSpecies": species_name,
                    "toSpecies": evolution.get("toSpeciesName"),
                    "level": evolution.get("level"),
                    "argument": evolution.get("argument"),
                }

        if species_id % 100 == 0:
            print(f"  ... {species_id}/{LAST_SPECIES_ID_UP_TO_KALOS}")

    bridge.stop()

    print()
    print(
        f"methodKey distintos encontrados: "
        f"{len(examples_by_method_key)}"
    )
    print()

    for method_key in sorted(examples_by_method_key):

        example = examples_by_method_key[method_key]

        print(f"  {method_key}")
        print(
            f"    ejemplo: {example['fromSpecies']} -> "
            f"{example['toSpecies']} "
            f"(level={example['level']}, "
            f"argument={example['argument']})"
        )

    if failed_species_ids:
        print()
        print(
            f"Aviso: {len(failed_species_ids)} especie(s) "
            "fallaron al pedirlas (puede ser normal para huecos "
            "de la Pokédex nacional, ej. formas alternativas sin "
            "entrada propia):"
        )
        for species_id, error in failed_species_ids[:20]:
            print(f"    - #{species_id}: {error}")

    print()
    print(
        "Pasar esta lista para armar la tabla de traducción al "
        "español -- cada methodKey con su ejemplo real ayuda a "
        "confirmar qué significa exactamente antes de traducirlo."
    )


if __name__ == "__main__":
    main()

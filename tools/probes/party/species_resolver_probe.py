from app.services.species_resolver import SpeciesResolver


def main():
    print("================================")
    print("   DEXRELAY SPECIES RESOLVER")
    print("================================")
    print()

    species_data = [
        {
            "speciesId": 269,
            "species": "Beautifly"
        },
        {
            "speciesId": 659,
            "species": "Bunnelby"
        },
        {
            "speciesId": 258,
            "species": "Mudkip"
        }
    ]

    resolver = SpeciesResolver(
        species_data
    )

    test_ids = [
        269,
        659,
        258,
        9999
    ]

    for species_id in test_ids:

        name = resolver.resolve(
            species_id
        )

        print(
            f"{species_id} -> "
            f"{name}"
        )


if __name__ == "__main__":
    main()
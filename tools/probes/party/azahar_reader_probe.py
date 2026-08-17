from app.readers.azahar_reader import AzaharReader
from app.services.species_resolver import SpeciesResolver


def main():

    print("================================")
    print("     DEXRELAY AZAHAR READER")
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
        },
        {
            "speciesId": 15,
            "species": "Beedrill"
        },
        {
            "speciesId": 661,
            "species": "Fletchling"
        }
    ]

    resolver = SpeciesResolver(
        species_data
    )

    reader = AzaharReader(
        species_resolver=resolver
    )

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print(
            "No se encontró sango-2."
        )
        return

    print(
        "Azahar conectado correctamente."
    )

    print()
    print("Leyendo party...")

    party = reader.read_party()

    if len(party) != 6:

        print(
            "ERROR: La party no "
            "contiene 6 slots."
        )

        return

    print()
    print("================================")
    print("             PARTY")
    print("================================")

    for pokemon in party:

        print()

        print(
            f"Slot {pokemon['slot']}"
        )

        if pokemon["empty"]:

            print("  Vacío")

            continue

        print(
            f"  Species ID: "
            f"{pokemon['speciesId']}"
        )

        print(
            f"  Species:    "
            f"{pokemon['species']}"
        )

        print(
            f"  Nickname:   "
            f"{pokemon['nickname']}"
        )

        print(
            f"  Level:      "
            f"{pokemon['level']}"
        )

        print(
            f"  HP:         "
            f"{pokemon['hp']}/"
            f"{pokemon['maxHp']}"
        )


if __name__ == "__main__":
    main()
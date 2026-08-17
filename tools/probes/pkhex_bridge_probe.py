from app.services.pkhex.bridge import PKHeXBridge


def main():
    print("================================")
    print("     DEXRELAY PKHEX BRIDGE")
    print("================================")
    print()

    bridge = PKHeXBridge()

    print("Iniciando bridge...")

    bridge.start()

    print("Bridge iniciado.")
    print()

    species_ids = [
        269,
        659,
        258,
        15,
        661,
    ]

    for species_id in species_ids:

        response = bridge.species(
            species_id
        )

        print(
            f"{species_id} -> "
            f"{response}"
        )

    bridge.stop()

    print()
    print("Bridge detenido correctamente.")


if __name__ == "__main__":
    main()
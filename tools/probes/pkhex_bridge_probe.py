from app.services.pkhex.bridge import PKHeXBridge


def main():
    print("================================")
    print("   DEXRELAY PKHEX BRIDGE TEST")
    print("================================")
    print()

    bridge = PKHeXBridge()

    print("Primera petición...")

    result = bridge.species(269)

    print(result)

    print()
    print("Deteniendo bridge manualmente...")

    bridge.stop()

    print(
        f"Bridge activo: "
        f"{bridge.is_running()}"
    )

    print()
    print(
        "Segunda petición después "
        "del cierre..."
    )

    result = bridge.species(659)

    print(result)

    print()
    print(
        f"Bridge activo: "
        f"{bridge.is_running()}"
    )

    bridge.stop()

    print()
    print("Prueba finalizada.")


if __name__ == "__main__":
    main()
    
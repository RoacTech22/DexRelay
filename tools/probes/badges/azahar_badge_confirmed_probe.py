from app.readers.citra import Citra


PROCESS_NAME = "sango-2"

# Dirección de medallas confirmada por el prototipo
# pokemon-overlay para Alpha Sapphire.
BADGE_ADDRESS = 0x08C6DDD4


def connect_to_azahar():
    print("================================")
    print("   DEXRELAY BADGE CONFIRMED")
    print("================================")
    print()

    print("Conectando con Azahar...")
    print("Consultando procesos...")

    citra = Citra()
    processes = citra.process_list()

    if not processes:
        print("No se encontraron procesos.")
        return None

    process_id = None

    print()
    print("Procesos encontrados:")

    for pid, data in processes.items():

        title_id, process_name = data

        print(
            f"PID: {pid} | "
            f"Nombre: {process_name} | "
            f"Title ID: {title_id}"
        )

        if process_name == PROCESS_NAME:
            process_id = pid

    if process_id is None:
        print(
            f"No se encontró el proceso: "
            f"{PROCESS_NAME}"
        )
        return None

    print()
    print(f"Seleccionando proceso: {process_id}")

    citra.set_process(process_id)

    print("Proceso seleccionado correctamente.")

    print()
    print(
        f"Proceso activo según Azahar: "
        f"{citra.get_process()}"
    )

    return citra


def read_badges(citra):

    print()
    print("================================")
    print("        BADGE MEMORY")
    print("================================")
    print()

    print(
        f"Dirección: 0x{BADGE_ADDRESS:08X}"
    )

    data = citra.read_memory(
        BADGE_ADDRESS,
        1
    )

    if data is None:
        raise RuntimeError(
            "No se pudo leer la memoria."
        )

    if len(data) != 1:
        raise RuntimeError(
            f"Se esperaba 1 byte, "
            f"pero se recibieron {len(data)}."
        )

    value = data[0]

    print(
        f"Byte: 0x{value:02X}"
    )

    print(
        f"Decimal: {value}"
    )

    print(
        f"Binario: {value:08b}"
    )

    print()
    print("Bits:")

    for bit in range(8):

        active = bool(
            value & (1 << bit)
        )

        state = "ON" if active else "OFF"

        print(
            f"  Bit {bit}: {state}"
        )

    active_badges = [
        bit
        for bit in range(8)
        if value & (1 << bit)
    ]

    print()
    print(
        "Medallas activas según el bitfield:"
    )

    print(
        f"  {len(active_badges)}/8"
    )

    if active_badges:

        print()
        print("Bits activos:")

        print(
            "  "
            + ", ".join(
                str(bit)
                for bit in active_badges
            )
        )

    return value


def main():

    citra = connect_to_azahar()

    if citra is None:
        return

    print()
    print("Modo: SOLO LECTURA")

    value = read_badges(citra)

    print()
    print("================================")
    print("       PROBE FINALIZADO")
    print("================================")
    print()

    print(
        f"Valor leído: "
        f"0x{value:02X}"
    )

    print(
        "No se ha modificado ninguna "
        "dirección de memoria."
    )


if __name__ == "__main__":
    main()
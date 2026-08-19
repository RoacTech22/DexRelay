from app.readers.citra import Citra


PROCESS_NAME = "sango-2"

# Dirección histórica de ORAS v1.4 utilizada por PokeReader
# como save value / Trainer Info.
TRAINER_INFO_ADDRESS = 0x08C71DB8

# Leeremos 32 bytes alrededor de la dirección.
READ_SIZE = 32


def connect_to_azahar():
    print("================================")
    print("   DEXRELAY TRAINER INFO PROBE")
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


def read_trainer_info(citra):

    print()
    print("================================")
    print("       LECTURA TRAINER INFO")
    print("================================")
    print()

    print(
        f"Leyendo {READ_SIZE} bytes desde "
        f"0x{TRAINER_INFO_ADDRESS:08X}..."
    )

    data = citra.read_memory(
        TRAINER_INFO_ADDRESS,
        READ_SIZE
    )

    if data is None:
        raise RuntimeError(
            f"No se pudo leer "
            f"0x{TRAINER_INFO_ADDRESS:08X}"
        )

    if len(data) != READ_SIZE:
        raise RuntimeError(
            f"Se esperaban {READ_SIZE} bytes, "
            f"pero se recibieron {len(data)}."
        )

    print(
        f"Bytes recibidos: {len(data)}"
    )

    return data


def print_hex_dump(data):

    print()
    print("--------------------------------")
    print("HEX DUMP")
    print("--------------------------------")

    for offset in range(0, len(data), 16):

        chunk = data[offset:offset + 16]

        hex_data = " ".join(
            f"{byte:02X}"
            for byte in chunk
        )

        print(
            f"0x{TRAINER_INFO_ADDRESS + offset:08X} "
            f"(+0x{offset:02X}): "
            f"{hex_data}"
        )


def print_offsets(data):

    print()
    print("--------------------------------")
    print("VALORES POR OFFSET")
    print("--------------------------------")

    for offset in range(len(data)):

        address = TRAINER_INFO_ADDRESS + offset
        value = data[offset]

        print(
            f"0x{address:08X} "
            f"(+0x{offset:02X}) = "
            f"0x{value:02X} ({value})"
        )


def print_common_values(data):

    print()
    print("--------------------------------")
    print("VALORES DE 32 BITS")
    print("--------------------------------")

    for offset in range(0, len(data) - 3, 4):

        value = int.from_bytes(
            data[offset:offset + 4],
            byteorder="little",
            signed=False
        )

        print(
            f"+0x{offset:02X}: "
            f"0x{value:08X} "
            f"({value})"
        )


def main():

    citra = connect_to_azahar()

    if citra is None:
        return

    print()
    print("Modo: SOLO LECTURA")

    data = read_trainer_info(citra)

    print_hex_dump(data)

    print_offsets(data)

    print_common_values(data)

    print()
    print("================================")
    print("       PROBE FINALIZADO")
    print("================================")
    print()
    print(
        "No se ha modificado ninguna "
        "dirección de memoria."
    )


if __name__ == "__main__":
    main()
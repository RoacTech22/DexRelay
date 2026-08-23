from app.readers.citra import Citra


PROCESS_NAME = "sango-2"

# Estructura PK6 que ya validamos.
TARGET_ADDRESS = 0x08CF727C

# Rango que ya sabemos que es completamente legible.
RANGE_START = 0x08CE0000
RANGE_END = 0x08D00000

BLOCK_SIZE = 0x400


def connect_to_azahar():

    print("================================")
    print("   DEXRELAY POINTER PROBE")
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


def scan_for_pointer(citra):

    print()
    print("================================")
    print("       BUSCANDO PUNTEROS")
    print("================================")
    print()

    print(
        f"Objetivo: 0x{TARGET_ADDRESS:08X}"
    )

    print(
        f"Rango:   0x{RANGE_START:08X} "
        f"- 0x{RANGE_END:08X}"
    )

    print(
        f"Bloque:  0x{BLOCK_SIZE:X}"
    )

    # Un puntero de 32 bits se representa
    # en memoria en little-endian.
    target_bytes = TARGET_ADDRESS.to_bytes(
        4,
        byteorder="little",
        signed=False
    )

    print()
    print("Bytes buscados:")

    print(
        " ".join(
            f"{byte:02X}"
            for byte in target_bytes
        )
    )

    matches = []

    current = RANGE_START
    total_blocks = (
        RANGE_END - RANGE_START
    ) // BLOCK_SIZE

    block_number = 0

    while current < RANGE_END:

        remaining = RANGE_END - current

        read_size = min(
            BLOCK_SIZE,
            remaining
        )

        data = citra.read_memory(
            current,
            read_size
        )

        block_number += 1

        if data is None:

            print(
                f"\n[ERROR] "
                f"0x{current:08X}"
            )

            current += read_size
            continue

        offset = 0

        while True:

            found = data.find(
                target_bytes,
                offset
            )

            if found == -1:
                break

            address = current + found

            matches.append(address)

            offset = found + 1

        current += read_size

        print(
            f"\rBloques: "
            f"{block_number}/"
            f"{total_blocks}",
            end=""
        )

    print()

    return matches


def print_results(matches):

    print()
    print("================================")
    print("          RESULTADO")
    print("================================")
    print()

    print(
        f"Punteros encontrados: "
        f"{len(matches)}"
    )

    if not matches:

        print()
        print(
            "No se encontraron punteros "
            "directos hacia el PK6."
        )

        return

    print()

    for address in matches:

        print(
            f"0x{address:08X} "
            f"-> 0x{TARGET_ADDRESS:08X}"
        )


def main():

    citra = connect_to_azahar()

    if citra is None:
        return

    print()
    print("Modo: SOLO LECTURA")

    matches = scan_for_pointer(citra)

    print_results(matches)

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
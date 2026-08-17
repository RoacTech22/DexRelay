from app.readers.citra import Citra


PARTY_ORDER_ADDRESS = 0x08CF71F0
PARTY_ORDER_SIZE = 24


def main():
    print("================================")
    print("       DEXRELAY CITRA PROBE")
    print("================================")
    print()

    citra = Citra()

    print("Consultando procesos de Azahar...")

    processes = citra.process_list()

    if not processes:
        print("No se encontraron procesos.")
        return

    print()
    print("Procesos encontrados:")
    print()

    target_process_id = None

    for process_id, data in processes.items():
        title_id, process_name = data

        print(
            f"PID: {process_id} | "
            f"Nombre: {process_name} | "
            f"Title ID: {title_id}"
        )

        if process_name == "sango-2":
            target_process_id = process_id

    if target_process_id is None:
        print()
        print("No se encontró el proceso sango-2.")
        return

    print()
    print(f"Seleccionando proceso: {target_process_id}")

    citra.set_process(target_process_id)

    print("Proceso seleccionado correctamente.")

    current_process = citra.get_process()

    print(f"Proceso activo según Azahar: {current_process}")

    print()
    print(
        f"Leyendo {PARTY_ORDER_SIZE} bytes "
        f"desde 0x{PARTY_ORDER_ADDRESS:08X}..."
    )

    data = citra.read_memory(
        PARTY_ORDER_ADDRESS,
        PARTY_ORDER_SIZE
    )

    if not data:
        print("ERROR: No se pudo leer la memoria.")
        return

    print()
    print(f"Bytes recibidos: {len(data)}")
    print(f"Datos HEX: {data.hex(' ')}")


if __name__ == "__main__":
    main()
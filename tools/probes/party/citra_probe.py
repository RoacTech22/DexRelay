from app.readers.citra import Citra
from app.memory.memory_reader import MemoryReader
from app.memory.pointers import (
    PARTY_ORDER_ADDRESS,
    ORDER_ENTRY_SIZE,
)


def main():
    print("================================")
    print("       DEXRELAY MEMORY PROBE")
    print("================================")
    print()

    citra = Citra()
    memory = MemoryReader(citra)

    print("Consultando procesos de Azahar...")

    processes = citra.process_list()

    if not processes:
        print("No se encontraron procesos.")
        return

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

    print(
        f"Proceso activo según Azahar: "
        f"{current_process}"
    )

    print()
    print(
        f"Leyendo tabla de party desde "
        f"0x{PARTY_ORDER_ADDRESS:08X}..."
    )

    data = memory.read(
        PARTY_ORDER_ADDRESS,
        ORDER_ENTRY_SIZE * 6
    )

    if not data:
        print("ERROR: No se pudo leer la memoria.")
        return

    print()
    print(f"Bytes recibidos: {len(data)}")
    print(f"Datos HEX: {data.hex(' ')}")


if __name__ == "__main__":
    main()
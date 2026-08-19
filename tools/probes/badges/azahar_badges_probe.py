from app.readers.citra import Citra


PROCESS_NAME = "sango-2"

START_ADDRESS = 0x08CF0000
END_ADDRESS = 0x08D00000

CHUNK_SIZE = 0x400

SNAPSHOT_CONTROL_A = (
    "tools/probes/badges/snapshot_control_a.bin"
)

SNAPSHOT_CONTROL_B = (
    "tools/probes/badges/snapshot_control_b.bin"
)


def connect_to_azahar():
    print("================================")
    print("      DEXRELAY BADGES PROBE")
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
    print(
        f"Seleccionando proceso: "
        f"{process_id}"
    )

    citra.set_process(process_id)

    print(
        "Proceso seleccionado correctamente."
    )

    print()
    print(
        f"Proceso activo según Azahar: "
        f"{citra.get_process()}"
    )

    return citra


def read_bytes(citra, address, size):

    data = citra.read_memory(
        address,
        size
    )

    if data is None:
        raise RuntimeError(
            f"No se pudo leer memoria "
            f"desde 0x{address:08X}"
        )

    if len(data) != size:
        raise RuntimeError(
            f"Lectura incompleta desde "
            f"0x{address:08X}"
        )

    return data


def capture_range(citra):

    memory = bytearray()

    address = START_ADDRESS

    while address < END_ADDRESS:

        size = min(
            CHUNK_SIZE,
            END_ADDRESS - address
        )

        data = read_bytes(
            citra,
            address,
            size
        )

        memory.extend(data)

        address += size

    expected_size = (
        END_ADDRESS -
        START_ADDRESS
    )

    if len(memory) != expected_size:
        raise RuntimeError(
            "Tamaño de captura incorrecto."
        )

    return bytes(memory)


def save_snapshot(filename, data):

    with open(filename, "wb") as file:
        file.write(data)

    print(
        f"Snapshot guardado: "
        f"{filename} "
        f"({len(data)} bytes)"
    )


def find_all_changes(before, after):

    if len(before) != len(after):
        raise ValueError(
            "Los snapshots tienen "
            "diferente tamaño."
        )

    changes = []

    for offset in range(len(before)):

        old_value = before[offset]
        new_value = after[offset]

        if old_value != new_value:

            address = (
                START_ADDRESS +
                offset
            )

            changes.append(
                (
                    address,
                    old_value,
                    new_value
                )
            )

    return changes


def main():

    citra = connect_to_azahar()

    if citra is None:
        return

    print()
    print("================================")
    print("       CONTROL A / B")
    print("================================")
    print()

    print(
        f"Rango: "
        f"0x{START_ADDRESS:08X} - "
        f"0x{END_ADDRESS:08X}"
    )

    print()
    print("Estado requerido:")
    print("0 medallas")
    print("AS_before_badge.sav")
    print()

    input(
        "Pulsa ENTER para realizar "
        "la captura CONTROL A..."
    )

    print()
    print("Capturando CONTROL A...")

    snapshot_a = capture_range(citra)

    save_snapshot(
        SNAPSHOT_CONTROL_A,
        snapshot_a
    )

    print()
    print(
        "Ahora NO consigas ninguna medalla."
    )

    print(
        "Espera unos segundos manteniendo "
        "el juego prácticamente sin cambios."
    )

    input(
        "Cuando estés listo, pulsa ENTER "
        "para realizar CONTROL B..."
    )

    print()
    print("Capturando CONTROL B...")

    snapshot_b = capture_range(citra)

    save_snapshot(
        SNAPSHOT_CONTROL_B,
        snapshot_b
    )

    print()
    print("Comparando CONTROL A -> B...")

    changes = find_all_changes(
        snapshot_a,
        snapshot_b
    )

    print()
    print("================================")
    print("       RESULTADO CONTROL")
    print("================================")
    print()

    print(
        f"Bytes modificados: "
        f"{len(changes)}"
    )

    print()

    for address, old_value, new_value in changes:

        print(
            f"0x{address:08X} : "
            f"{old_value:02X} -> "
            f"{new_value:02X}"
        )

    print()
    print("Control finalizado.")
    print(
        "No se ha modificado ninguna "
        "dirección de memoria."
    )


if __name__ == "__main__":
    main()
from pathlib import Path


START_ADDRESS = 0x08CF0000

SNAPSHOT_BEFORE = (
    Path(__file__).resolve().parent /
    "snapshot_before.bin"
)

SNAPSHOT_AFTER = (
    Path(__file__).resolve().parent /
    "snapshot_after.bin"
)


def load_snapshot(path):
    if not path.exists():
        raise FileNotFoundError(
            f"No existe el snapshot: {path}"
        )

    data = path.read_bytes()

    print(
        f"Cargado: {path.name} "
        f"({len(data)} bytes)"
    )

    return data


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


def print_changes(changes):
    print()
    print("================================")
    print("       TODOS LOS CAMBIOS")
    print("================================")
    print()

    if not changes:
        print("No se encontraron cambios.")
        return

    print(
        f"Total de bytes modificados: "
        f"{len(changes)}"
    )

    print()

    for address, old_value, new_value in changes:

        print(
            f"0x{address:08X} : "
            f"{old_value:02X} -> "
            f"{new_value:02X}"
        )


def print_summary(changes):
    print()
    print("================================")
    print("          RESUMEN")
    print("================================")
    print()

    if not changes:
        print("Sin cambios.")
        return

    exact_00_01 = [
        change
        for change in changes
        if change[1] == 0x00
        and change[2] == 0x01
    ]

    exact_01_00 = [
        change
        for change in changes
        if change[1] == 0x01
        and change[2] == 0x00
    ]

    print(
        f"Total de cambios: "
        f"{len(changes)}"
    )

    print(
        f"00 -> 01: "
        f"{len(exact_00_01)}"
    )

    print(
        f"01 -> 00: "
        f"{len(exact_01_00)}"
    )

    print()

    print("Primeros cambios:")

    for address, old_value, new_value in changes[:20]:

        print(
            f"0x{address:08X} : "
            f"{old_value:02X} -> "
            f"{new_value:02X}"
        )


def main():

    print("================================")
    print("   DEXRELAY BADGE SNAPSHOT")
    print("        OFFLINE ANALYZER")
    print("================================")
    print()

    before = load_snapshot(
        SNAPSHOT_BEFORE
    )

    after = load_snapshot(
        SNAPSHOT_AFTER
    )

    print()

    changes = find_all_changes(
        before,
        after
    )

    print_changes(
        changes
    )

    print_summary(
        changes
    )

    print()
    print("Análisis finalizado.")


if __name__ == "__main__":
    main()
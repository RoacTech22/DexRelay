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

CONTEXT_BEFORE = 16
CONTEXT_AFTER = 16


def load_snapshot(path):
    if not path.exists():
        raise FileNotFoundError(
            f"No existe: {path}"
        )

    return path.read_bytes()


def find_exclusive_candidates(
    control_a,
    control_b,
    badge_a,
    badge_b
):
    candidates = []

    for offset in range(len(badge_a)):

        control_changed = (
            control_a[offset]
            != control_b[offset]
        )

        badge_changed = (
            badge_a[offset]
            != badge_b[offset]
        )

        if badge_changed and not control_changed:

            address = (
                START_ADDRESS +
                offset
            )

            candidates.append(offset)

    return candidates


def format_hex(data):
    return " ".join(
        f"{byte:02X}"
        for byte in data
    )


def print_context(
    snapshot_before,
    snapshot_after,
    offset
):
    start = max(
        0,
        offset - CONTEXT_BEFORE
    )

    end = min(
        len(snapshot_before),
        offset + CONTEXT_AFTER + 1
    )

    address = START_ADDRESS + offset

    before = snapshot_before[start:end]
    after = snapshot_after[start:end]

    print()
    print(
        f"Dirección candidata: "
        f"0x{address:08X}"
    )

    print(
        f"Rango: "
        f"0x{START_ADDRESS + start:08X} - "
        f"0x{START_ADDRESS + end - 1:08X}"
    )

    print()
    print(
        "ANTES :",
        format_hex(before)
    )

    print(
        "DESPUÉS:",
        format_hex(after)
    )


def main():

    print("================================")
    print("   DEXRELAY CANDIDATE CONTEXT")
    print("================================")
    print()

    base = (
        Path(__file__).resolve().parent
    )

    control_a = (
        (base / "snapshot_control_a.bin")
        .read_bytes()
    )

    control_b = (
        (base / "snapshot_control_b.bin")
        .read_bytes()
    )

    badge_a = load_snapshot(
        SNAPSHOT_BEFORE
    )

    badge_b = load_snapshot(
        SNAPSHOT_AFTER
    )

    if not (
        len(control_a)
        == len(control_b)
        == len(badge_a)
        == len(badge_b)
    ):
        raise RuntimeError(
            "Los snapshots no tienen "
            "el mismo tamaño."
        )

    candidates = find_exclusive_candidates(
        control_a,
        control_b,
        badge_a,
        badge_b
    )

    print(
        f"Candidatos exclusivos: "
        f"{len(candidates)}"
    )

    print()

    for offset in candidates:

        print_context(
            badge_a,
            badge_b,
            offset
        )

    print()
    print("Análisis finalizado.")


if __name__ == "__main__":
    main()
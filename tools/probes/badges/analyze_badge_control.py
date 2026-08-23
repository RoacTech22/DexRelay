from pathlib import Path


START_ADDRESS = 0x08CF0000

BASE_DIR = Path(__file__).resolve().parent

CONTROL_A = BASE_DIR / "snapshot_control_a.bin"
CONTROL_B = BASE_DIR / "snapshot_control_b.bin"

BADGE_A = BASE_DIR / "snapshot_before.bin"
BADGE_B = BASE_DIR / "snapshot_after.bin"


def load_snapshot(path):
    if not path.exists():
        raise FileNotFoundError(
            f"No existe: {path}"
        )

    data = path.read_bytes()

    print(
        f"{path.name}: "
        f"{len(data)} bytes"
    )

    return data


def analyze(control_a, control_b, badge_a, badge_b):

    if not (
        len(control_a)
        == len(control_b)
        == len(badge_a)
        == len(badge_b)
    ):
        raise ValueError(
            "Los snapshots no tienen "
            "el mismo tamaño."
        )

    candidates = []

    for offset in range(len(badge_a)):

        ca = control_a[offset]
        cb = control_b[offset]

        ba = badge_a[offset]
        bb = badge_b[offset]

        control_changed = ca != cb
        badge_changed = ba != bb

        # Debe cambiar durante la obtención
        # de la medalla.
        if not badge_changed:
            continue

        # Pero no debe cambiar durante
        # el control sin medalla.
        if control_changed:
            continue

        address = START_ADDRESS + offset

        candidates.append(
            (
                address,
                ca,
                cb,
                ba,
                bb
            )
        )

    return candidates


def print_candidates(candidates):

    print()
    print("================================")
    print("     CANDIDATOS EXCLUSIVOS")
    print("================================")
    print()

    print(
        f"Candidatos encontrados: "
        f"{len(candidates)}"
    )

    print()

    if not candidates:
        print(
            "No se encontraron candidatos."
        )
        return

    for (
        address,
        ca,
        cb,
        ba,
        bb
    ) in candidates:

        print(
            f"0x{address:08X} | "
            f"CONTROL {ca:02X}->{cb:02X} | "
            f"MEDALLA {ba:02X}->{bb:02X}"
        )


def print_badge_candidates(candidates):

    badge_candidates = [
        candidate
        for candidate in candidates
        if candidate[3] == 0x00
        and candidate[4] == 0x01
    ]

    print()
    print("================================")
    print("       CANDIDATOS 00 -> 01")
    print("================================")
    print()

    print(
        f"Candidatos: "
        f"{len(badge_candidates)}"
    )

    print()

    for (
        address,
        ca,
        cb,
        ba,
        bb
    ) in badge_candidates:

        print(
            f"0x{address:08X} | "
            f"MEDALLA {ba:02X}->{bb:02X}"
        )


def main():

    print("================================")
    print("   DEXRELAY BADGE ANALYZER")
    print("================================")
    print()

    print("Cargando snapshots...")

    control_a = load_snapshot(
        CONTROL_A
    )

    control_b = load_snapshot(
        CONTROL_B
    )

    badge_a = load_snapshot(
        BADGE_A
    )

    badge_b = load_snapshot(
        BADGE_B
    )

    print()
    print("Analizando...")

    candidates = analyze(
        control_a,
        control_b,
        badge_a,
        badge_b
    )

    print_candidates(
        candidates
    )

    print_badge_candidates(
        candidates
    )

    print()
    print("Análisis finalizado.")


if __name__ == "__main__":
    main()
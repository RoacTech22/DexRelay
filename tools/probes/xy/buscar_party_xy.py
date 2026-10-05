"""
Paso 2 del Bloque 14 (ruta multijuego, 04/10/2026): encontrar dónde
vive el equipo de Pokémon X/Y en la memoria de Azahar.

Mismo método que ya encontró la Caja PC y la party de Omega Ruby
(tools/probes/party/buscar_party_omega_ruby.py): escanear la memoria
buscando estructuras PK6 con checksum válido (1 falso positivo cada
65536), en vez de asumir direcciones. Además de listar los Pokémon
hallados, este probe responde la pregunta abierta del riesgo R1 de la
guía (DexRelay_Guia_Ruta_Multi-Juego): ¿X/Y guarda la party con la
misma tabla de 6 punteros + offset 0x40 que ORAS, o de otra forma?

    * "Grupos con stride constante": direcciones de Pokémon separadas
      por una distancia fija (party contigua = 0x104 en la lista de
      LiveHeX; cajas = 0xE8). Si la party de XY es contigua, aparecerá
      un grupo de N Pokémon (N = tamaño de tu equipo).
    * "Referencias": direcciones de memoria que contienen un puntero
      hacia un Pokémon hallado, tanto a la estructura (A) como 0x40
      antes (A-0x40, la convención de ORAS). Si hay una tabla de 6
      punteros consecutivos, es la misma mecánica que ORAS.

Solo lectura: no escribe nada en el juego.

COMO USARLO (Azahar abierto con X o Y ya CARGADO en una partida, con
tu equipo real; no en el logo ni en el menú de título):

    python tools/probes/xy/buscar_party_xy.py

    Opciones: --process kujira-1   (por defecto se detecta solo)
              --start 0x08000000 --size 0x2000000   (32 MB, ~1-2 min)

Antes de correrlo anota el nickname/especie de 2 o 3 de tus Pokémon
para reconocerlos en la salida, y la versión exacta del juego
(actualización 1.5). Pega la salida completa en el chat. También deja
un JSON con TODOS los candidatos en logs/salida_party_xy.json (la
carpeta logs/ ya está en .gitignore).
"""

import argparse
import json
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.memory.structures import SLOT_DATA_SIZE, decrypt_data  # noqa: E402

DEFAULT_START = 0x08000000
DEFAULT_SIZE = 0x2000000  # 32 MB, como los probes de ORAS
CHUNK_SIZE = 0x10000
ALIGNMENT = 4
MAX_SPECIES_GEN6 = 721

# Title ID de X e Y ya conocidos por el proyecto (TITLE_ID_REGIONS).
XY_TITLE_IDS = {
    0x0004000000055D00: "Pokémon X",
    0x0004000000055E00: "Pokémon Y",
}

# Strides típicos a señalar en los grupos: party contigua de 3DS (0x104),
# caja PC (0xE8) y el buffer de captura de ORAS (0x1E4).
KNOWN_STRIDES = {0x104: "party contigua", 0xE8: "caja PC", 0x1E4: "buffer de captura"}

POINTER_OFFSETS = (0x40, 0x0)  # A-0x40 (convención ORAS) y A directo
MAX_PRINT = 120


def decode_candidate(raw):
    """Datos de un PK6 ya descifrado (232 bytes) para mostrar."""
    species = struct.unpack("<H", raw[0x08:0x0A])[0]
    tid, sid = struct.unpack("<HH", raw[0x0C:0x10])
    nickname = raw[0x40:0x58].decode("utf-16le", errors="ignore").split("\x00", 1)[0]
    ot = raw[0xB0:0xC8].decode("utf-16le", errors="ignore").split("\x00", 1)[0]

    return {
        "species": species,
        "tid": tid,
        "sid": sid,
        "nickname": nickname,
        "ot": ot,
    }


def find_pk6_candidates(snapshot, base_address, alignment=ALIGNMENT):
    """
    Recorre `snapshot` (bytes) y devuelve [(dirección, datos)] de cada
    estructura PK6 con checksum válido y especie plausible de Gen 6.

    Prefiltro barato antes de descifrar: PV distinto de cero y el campo
    "sanity" (bytes 4-5, sin cifrar) en cero.
    """
    found = []
    limit = len(snapshot) - SLOT_DATA_SIZE

    for offset in range(0, limit + 1, alignment):
        if snapshot[offset + 4] or snapshot[offset + 5]:
            continue

        if not any(snapshot[offset:offset + 4]):
            continue

        decrypted = decrypt_data(snapshot[offset:offset + SLOT_DATA_SIZE])

        if not decrypted:
            continue

        data = decode_candidate(decrypted)

        if not 1 <= data["species"] <= MAX_SPECIES_GEN6:
            continue

        found.append((base_address + offset, data))

    return found


def group_by_stride(addresses, min_group=3):
    """
    Agrupa direcciones ordenadas que avanzan con la MISMA distancia
    (>= min_group seguidas). Devuelve [(stride, [direcciones])].
    """
    addresses = sorted(set(addresses))
    groups = []
    i = 0

    while i < len(addresses) - 1:
        stride = addresses[i + 1] - addresses[i]
        j = i + 1

        while j + 1 < len(addresses) and addresses[j + 1] - addresses[j] == stride:
            j += 1

        if stride > 0 and j - i + 1 >= min_group:
            groups.append((stride, addresses[i:j + 1]))
            i = j + 1
        else:
            i += 1

    return groups


def find_pointer_refs(snapshot, base_address, targets, alignment=ALIGNMENT):
    """
    Busca en `snapshot` valores u32 iguales a cada dirección objetivo
    (y a objetivo-0x40). Devuelve {objetivo: [(dirección_del_puntero,
    offset_usado)]}.
    """
    wanted = {}

    for target in targets:
        for pointer_offset in POINTER_OFFSETS:
            wanted.setdefault(
                struct.pack("<I", target - pointer_offset), []
            ).append((target, pointer_offset))

    refs = {target: [] for target in targets}

    for pattern, owners in wanted.items():
        start = 0

        while True:
            index = snapshot.find(pattern, start)

            if index < 0:
                break

            if index % alignment == 0:
                for target, pointer_offset in owners:
                    refs[target].append((base_address + index, pointer_offset))

            start = index + 1

    return refs


def group_consecutive_pointers(pointer_addresses, min_group=3, max_stride=0x20):
    """Punteros que están uno al lado del otro (tabla de punteros)."""
    return [
        (stride, group)
        for stride, group in group_by_stride(pointer_addresses, min_group)
        if stride <= max_stride
    ]


def read_snapshot(citra, start, size):
    """Lee la ventana en bloques; los bloques ilegibles quedan en ceros."""
    chunks = []
    unreadable = 0

    for chunk_start in range(0, size, CHUNK_SIZE):
        length = min(CHUNK_SIZE, size - chunk_start)
        data = citra.read_memory(start + chunk_start, length)

        if data is None or len(data) != length:
            unreadable += 1
            data = b"\x00" * length

        chunks.append(data)

        if (chunk_start // CHUNK_SIZE) % 32 == 0:
            done = 100 * (chunk_start + length) / size
            print(f"  leyendo... {done:5.1f}%", end="\r", flush=True)

    print(" " * 30, end="\r")
    return b"".join(chunks), unreadable


def select_process(citra, wanted_name):
    processes = citra.process_list()

    for pid, (title_id, name) in sorted(processes.items()):
        if wanted_name is not None:
            if name == wanted_name:
                return pid, title_id, name
        elif title_id in XY_TITLE_IDS:
            return pid, title_id, name

    return None


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--start", type=parse_int, default=DEFAULT_START)
    parser.add_argument("--size", type=parse_int, default=DEFAULT_SIZE)
    parser.add_argument(
        "--out", default=str(PROJECT_ROOT / "logs" / "salida_party_xy.json")
    )
    args = parser.parse_args()

    from app.readers.citra import Citra

    citra = Citra()

    try:
        selected = select_process(citra, args.process)
    except OSError as error:
        print(f"No se pudo hablar con Azahar: {error!r}")
        return 1

    if selected is None:
        print("No se encontró el proceso de X/Y. Corre antes listar_procesos_xy.py.")
        return 1

    pid, title_id, name = selected
    citra.set_process(pid)

    print("================================")
    print("   BUSCAR PARTY EN X/Y (por checksum PK6)")
    print("================================")
    print(f"Proceso: {name}  Title ID: {title_id:016X}")
    print(f"Ventana: 0x{args.start:08X} + 0x{args.size:X}\n")

    snapshot, unreadable = read_snapshot(citra, args.start, args.size)

    if unreadable:
        print(f"Aviso: {unreadable} bloques de 0x{CHUNK_SIZE:X} no se pudieron leer.")

    print("Buscando estructuras PK6 (puede tardar un minuto)...")
    candidates = find_pk6_candidates(snapshot, args.start)
    addresses = [address for address, _ in candidates]

    print(f"\nCandidatos con checksum válido: {len(candidates)}\n")
    print(f"{'DIRECCIÓN':<12} {'ESP':>4}  {'TID':>5} {'SID':>5}  NICKNAME / OT")

    for address, data in candidates[:MAX_PRINT]:
        print(
            f"0x{address:08X}  {data['species']:>4}  "
            f"{data['tid']:>5} {data['sid']:>5}  "
            f"{data['nickname']!r} / {data['ot']!r}"
        )

    if len(candidates) > MAX_PRINT:
        print(f"... y {len(candidates) - MAX_PRINT} más (están en el JSON).")

    print("\n--- Grupos con stride constante (3 o más seguidos) ---")
    groups = group_by_stride(addresses)

    if not groups:
        print("(ninguno)")

    for stride, group in groups:
        label = KNOWN_STRIDES.get(stride, "stride no reconocido")
        print(
            f"stride 0x{stride:X} ({label}): {len(group)} Pokémon, "
            f"de 0x{group[0]:08X} a 0x{group[-1]:08X}"
        )

    print("\n--- Punteros hacia los Pokémon hallados ---")
    # Con cajas llenas hay cientos de candidatos: se buscan punteros solo
    # a los primeros 150 que NO caen en un grupo de caja (stride 0xE8).
    box_members = {a for s, g in groups if s == 0xE8 for a in g}
    targets = [a for a in addresses if a not in box_members][:150]
    refs = find_pointer_refs(snapshot, args.start, targets)
    pointer_addresses = []

    for target in targets:
        for pointer_address, pointer_offset in refs[target]:
            pointer_addresses.append(pointer_address)
            print(
                f"0x{pointer_address:08X} -> Pokémon 0x{target:08X} "
                f"(puntero a A-0x{pointer_offset:X})"
            )

    if not pointer_addresses:
        print("(ninguno: la party podría ser contigua, sin tabla de punteros)")

    print("\n--- Posibles tablas de punteros (3 o más seguidos) ---")
    tables = group_consecutive_pointers(pointer_addresses)

    if not tables:
        print("(ninguna)")

    for stride, group in tables:
        print(
            f"stride 0x{stride:X}: {len(group)} punteros, "
            f"de 0x{group[0]:08X} a 0x{group[-1]:08X}"
        )

    output = {
        "process": name,
        "title_id": f"{title_id:016X}",
        "window": [args.start, args.size],
        "candidates": [
            {"address": address, **data} for address, data in candidates
        ],
        "stride_groups": [
            {"stride": stride, "addresses": group} for stride, group in groups
        ],
        "pointer_refs": [
            {"pointer": pointer, "target": target, "offset": offset}
            for target in targets
            for pointer, offset in refs[target]
        ],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nJSON completo: {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

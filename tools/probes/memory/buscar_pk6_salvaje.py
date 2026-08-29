"""
Busca un offset RELATIVO a la base de combate donde el juego guarda
al Pokemon salvaje rival como una estructura PK6 CIFRADA completa
(232 bytes) -- en vez de buscar el speciesId en texto plano (lo que
ya se probo en buscar_species_salvaje.py sin resultado), esto
intenta DESCIFRAR cada offset candidato con decrypt_data() (la
misma funcion de app/memory/structures.py que ya se usa para la
party) y valida:

    1. El checksum PK6 tiene que dar valido (probabilidad de un
       choque aleatorio: 1 en 65536).
    2. El speciesId resultante DESPUES de descifrar tiene que
       coincidir exactamente con la especie que confirmaste vos.

Mismo patron que tools/probes/party/buscar_caja_pc.py (que encontro
la Caja PC de la misma forma), aplicado ahora a la estructura de
combate en vez de a la memoria de guardado.

Por que probar esto: si el speciesId estuviera en texto plano en
algun lado de la zona de datos del salvaje, buscar_species_salvaje.py
ya lo deberia haber encontrado. Que no haya aparecido nada sugiere
que el dato esta CIFRADO -- razonable, ya que el juego probablemente
reutiliza la misma logica de PK6 para representar temporalmente al
Pokemon salvaje rival durante el combate (por ejemplo, para poder
ofrecerlo como capturable con sus IVs/naturaleza ya generados).

COMO USARLO:

    python -m tools.probes.memory.buscar_pk6_salvaje

    Igual que buscar_species_salvaje.py: entra a un combate
    SALVAJE, todavia adentro escribi el nombre de la especie (en
    ingles), repetir con VARIAS especies distintas (4-5+
    recomendado), 'fin' para cortar y analizar.
"""

import argparse
import json
import struct
from pathlib import Path

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import SLOT_DATA_SIZE
from app.memory.structures import Pokemon6, decrypt_data


COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4

# Ventana amplia por defecto: el filtro por checksum es tan
# selectivo que se puede permitir escanear una zona grande sin
# miedo a ruido (mismo razonamiento que buscar_caja_pc.py).
DEFAULT_WINDOW_START_OFFSET = 0x0
DEFAULT_WINDOW_SIZE = 0x3000  # 12288 bytes

ALIGNMENT = 4

SPECIES_CACHE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "species_cache.json"
)


def load_species_cache():
    if not SPECIES_CACHE_PATH.exists():
        return []

    with SPECIES_CACHE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_species_id(species_list, query):
    query_normalized = query.strip().lower()

    for entry in species_list:
        if entry["name"].strip().lower() == query_normalized:
            return entry["id"]

    return None


def suggest_species(species_list, query, limit=8):
    query_normalized = query.strip().lower()

    matches = [
        entry
        for entry in species_list
        if query_normalized in entry["name"].strip().lower()
    ]

    return matches[:limit]


def read_combat_base(memory):
    pointer_before = memory.read(COMBAT_POINTER_ADDRESS, 4)

    if len(pointer_before) != 4:
        return None

    base_address = struct.unpack("<I", pointer_before)[0]

    if base_address in (0, COMBAT_INACTIVE_POINTER):
        return None

    return base_address


def read_window_relative_to_combat(memory, window_start_offset, window_size):
    base_before = read_combat_base(memory)

    if base_before is None:
        return None, None

    snapshot = memory.read(
        base_before + window_start_offset,
        window_size,
    )

    if len(snapshot) != window_size:
        return None, None

    base_after = read_combat_base(memory)

    if base_after != base_before:
        return None, None

    return base_before, snapshot


def find_pk6_offsets(snapshot, expected_species_id, alignment=ALIGNMENT):
    """
    Escanea `snapshot` en offsets alineados a `alignment` bytes
    buscando una estructura PK6 que descifre con checksum valido Y
    cuyo speciesId coincida con `expected_species_id`. Devuelve el
    conjunto de offsets que cumplieron ambas condiciones.
    """

    hits = set()

    for offset in range(0, len(snapshot) - SLOT_DATA_SIZE + 1, alignment):

        chunk = snapshot[offset:offset + SLOT_DATA_SIZE]

        if chunk[:8] == b"\x00" * 8:
            continue

        decrypted = decrypt_data(chunk)

        if not decrypted:
            continue

        pokemon = Pokemon6.__new__(Pokemon6)
        pokemon.raw_data = decrypted

        if pokemon.species_id() == expected_species_id:
            hits.add(offset)

    return hits


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Busca la estructura PK6 cifrada del Pokemon salvaje "
            "rival, relativa a la base de combate."
        )
    )
    parser.add_argument(
        "--before",
        type=lambda s: int(s, 0),
        default=0,
        help=(
            "Bytes a escanear ANTES de la base de combate (valor "
            "positivo). Ejemplo: --before 0x4000. Default: 0"
        ),
    )
    parser.add_argument(
        "--after",
        type=lambda s: int(s, 0),
        default=DEFAULT_WINDOW_SIZE,
        help=(
            "Bytes a escanear DESPUES de la base de combate. "
            f"Default: {hex(DEFAULT_WINDOW_SIZE)}"
        ),
    )
    parser.add_argument(
        "--alignment",
        type=lambda s: int(s, 0),
        default=ALIGNMENT,
        help=(
            f"Alineacion de bytes a probar (las estructuras del "
            f"juego casi siempre estan alineadas a 4, pero se "
            f"puede bajar a 1 para un escaneo exhaustivo mas "
            f"lento). Default: {ALIGNMENT}"
        ),
    )
    args = parser.parse_args()
    args.start = -args.before
    args.size = args.before + args.after

    print("================================")
    print("   BUSCAR PK6 SALVAJE (por checksum)")
    print("================================")
    print()
    print(
        f"Ventana relativa a la base de combate: "
        f"[{hex(args.start)}, {hex(args.start + args.size)})"
    )
    print()

    species_list = load_species_cache()

    if not species_list:
        print(f"No se encontro {SPECIES_CACHE_PATH}.")
        return

    print(f"Cache de especies cargado: {len(species_list)} entradas.")
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print()
    print(
        "Entra a un combate SALVAJE. TODAVIA DENTRO del combate, "
        "volve aca y escribi el nombre de la especie (en ingles). "
        "Escribi 'fin' para cortar y analizar."
    )
    print()

    memory = reader.memory

    # offsets_por_muestra: lista de sets de offsets que dieron hit
    # en cada muestra. El resultado final es la interseccion de
    # todos.
    offsets_por_muestra = []
    sample_count = 0

    while True:

        query = input(
            f"[{sample_count} especies guardadas] "
            f"Especie salvaje actual (o 'fin'): "
        ).strip()

        if not query:
            continue

        if query.lower() in ("fin", "salir", "exit"):
            break

        species_id = resolve_species_id(species_list, query)

        if species_id is None:

            suggestions = suggest_species(species_list, query)

            if suggestions:
                print("  No hubo coincidencia exacta. ¿Quisiste decir?")
                for entry in suggestions:
                    print(f"    {entry['name']}")
            else:
                print(
                    "  No se encontro ninguna especie parecida en "
                    "el cache."
                )

            continue

        base_address, snapshot = read_window_relative_to_combat(
            memory,
            args.start,
            args.size,
        )

        if snapshot is None:
            print(
                "  No se detecto un combate activo (o el puntero "
                "cambio a mitad de lectura). Confirma que seguis "
                "DENTRO del combate y proba de nuevo."
            )
            continue

        print("  Escaneando (calculo local, deberia ser rapido)...")

        hits = find_pk6_offsets(snapshot, species_id, args.alignment)

        offsets_por_muestra.append(hits)
        sample_count += 1

        if hits:
            hits_hex = ", ".join(
                (
                    ("+" if args.start + o >= 0 else "-")
                    + hex(abs(args.start + o))
                )
                for o in sorted(hits)
            )
            print(
                f"  Muestra guardada: {query} (id={species_id}). "
                f"Base: {hex(base_address)}. "
                f"Offsets con PK6 valido: {hits_hex}"
            )
        else:
            print(
                f"  Muestra guardada: {query} (id={species_id}). "
                f"Base: {hex(base_address)}. "
                f"Ningun offset con PK6 valido en esta ventana."
            )

        print()

    print()

    if len(offsets_por_muestra) < 2:
        print(
            "Hacen falta al menos 2 muestras para poder cruzar "
            "resultados. No se analizo nada."
        )
        return

    interseccion = set.intersection(*offsets_por_muestra)

    print(
        f"================================\n"
        f"   RESULTADO ({len(offsets_por_muestra)} muestras)\n"
        f"================================"
    )

    if not interseccion:
        print(
            "Ningun offset dio PK6 valido en TODAS las muestras a "
            "la vez. Puede que el offset se mueva entre combates "
            "(no relativo a la base de combate de forma fija), o "
            "que la ventana no lo cubra -- probar ampliando "
            "--size o corriendo con --start negativo."
        )
        return

    for offset in sorted(interseccion):
        real_offset = args.start + offset
        sign = "+" if real_offset >= 0 else "-"
        print(f"  offset {sign}{hex(abs(real_offset))}  <-- CONFIRMADO en todas las muestras")


if __name__ == "__main__":
    main()

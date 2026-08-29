"""
Busca un offset RELATIVO a la base de combate (misma base dinamica
que ya usan combat_service.py y WILD_BATTLE_FLAG_OFFSET) donde el
juego guarda el speciesId (numero de Pokedex nacional) del Pokemon
salvaje rival.

Pieza 3 de 3 (la ultima) para la deteccion automatica de "perdido"
en el Nuzlocke Tracker (ver
DexRelay_Contexto_Deteccion_Perdido.md).

A diferencia de buscar_flag_tipo_combate.py (que comparaba
categorias entre si, sin saber de antemano que valor esperar), acá
SI sabemos el valor exacto que tiene que aparecer en memoria: el
speciesId real del Pokemon que estas peleando. Eso hace la busqueda
mucho mas precisa -- se descarta cualquier offset que no coincida
con el ID exacto en TODOS los combates, no solo "es distinto entre
categorias".

Usa data/species_cache.json (ya generado por una sesion anterior
via el bridge PKHeX) para resolver nombre de especie -> ID, sin
necesitar que el bridge .NET este corriendo.

COMO USARLO:

    python -m tools.probes.memory.buscar_species_salvaje

    1. Entra a un combate SALVAJE en el juego (los de entrenador no
       sirven para esto, no hay speciesId rival que buscar de la
       misma forma).
    2. TODAVIA DENTRO del combate, volve a la terminal y escribi el
       nombre de la especie que ves (en ingles, como lo conoce
       PKHeX -- por ejemplo "Zigzagoon", "Wurmple"). Si no estas
       seguro del nombre en ingles, el script te muestra las
       coincidencias mas parecidas para que confirmes.
    3. Repetir con VARIAS especies DISTINTAS -- cuantas mas
       distintas, mejor filtra (recomendado: al menos 4-5 especies
       distintas antes de terminar). Repetir la MISMA especie dos
       veces no suma nada nuevo para este metodo en particular.
    4. Escribi 'fin' para cortar y analizar. Imprime los offsets
       donde el valor coincidio EXACTAMENTE con el speciesId real
       en todos los combates.

Nota: como ya sabemos por la pieza 2 que la zona alrededor de
WILD_BATTLE_FLAG_OFFSET (+0x87f relativo a la base) es la tabla de
datos del encuentro salvaje, la ventana por defecto de este script
cubre esa misma zona y sus alrededores -- si no aparece nada ahi,
se puede ampliar con --start/--size.
"""

import argparse
import json
import struct
from pathlib import Path

from app.readers.azahar_reader import AzaharReader


COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4

# Ventana por defecto: cubre la zona ya confirmada en la pieza 2
# (WILD_BATTLE_FLAG_OFFSET = +0x87f) con margen razonable a los
# costados, ya que se identifico como la tabla de datos del
# encuentro salvaje.
DEFAULT_WINDOW_START_OFFSET = 0x780
DEFAULT_WINDOW_SIZE = 0x300  # 768 bytes

SPECIES_CACHE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "species_cache.json"
)


def load_species_cache():
    if not SPECIES_CACHE_PATH.exists():
        return []

    with SPECIES_CACHE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_species_id(species_list, query):
    """
    Busca `query` (nombre escrito por el usuario) en la lista de
    especies. Devuelve el ID si hay una coincidencia exacta
    (insensible a mayusculas), o None si no hay ninguna -- en ese
    caso el llamador se encarga de mostrar sugerencias.
    """

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


def find_candidates(samples, width):
    """
    `samples` es una lista de (expected_id, snapshot).

    Devuelve la lista de offsets donde, para TODOS los samples, el
    valor de `width` bytes (little-endian) leido en ese offset
    coincide EXACTAMENTE con el expected_id de esa muestra.
    """

    size = len(samples[0][1])
    unpack_format = "<B" if width == 1 else "<H"

    candidates = []

    for offset in range(size - width + 1):

        matches_all = True

        for expected_id, snapshot in samples:

            value = struct.unpack(
                unpack_format,
                snapshot[offset:offset + width],
            )[0]

            if value != expected_id:
                matches_all = False
                break

        if matches_all:
            candidates.append(offset)

    return candidates


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Busca el offset del speciesId del Pokemon salvaje "
            "rival, relativo a la base de combate."
        )
    )
    parser.add_argument(
        "--start",
        type=lambda s: int(s, 0),
        default=DEFAULT_WINDOW_START_OFFSET,
        help=(
            "Offset de inicio de la ventana relativo a la base de "
            f"combate. Default: {hex(DEFAULT_WINDOW_START_OFFSET)}"
        ),
    )
    parser.add_argument(
        "--size",
        type=lambda s: int(s, 0),
        default=DEFAULT_WINDOW_SIZE,
        help=(
            f"Tamano de la ventana en bytes. Default: "
            f"{hex(DEFAULT_WINDOW_SIZE)}"
        ),
    )
    args = parser.parse_args()

    print("================================")
    print("   BUSCAR SPECIES SALVAJE")
    print("================================")
    print()
    print(
        f"Ventana relativa a la base de combate: "
        f"[{hex(args.start)}, {hex(args.start + args.size)})"
    )
    print()

    species_list = load_species_cache()

    if not species_list:
        print(
            f"No se encontro {SPECIES_CACHE_PATH} -- hace falta "
            f"para resolver nombre -> ID. Corre el panel de "
            f"Nuzlocke al menos una vez (genera este cache "
            f"automaticamente) o inicia el bridge PKHeX."
        )
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
    samples = []

    while True:

        query = input(
            f"[{len(samples)} especies guardadas] "
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

        samples.append((species_id, snapshot))

        print(
            f"  Muestra guardada: {query} (id={species_id}). "
            f"Base de combate: {hex(base_address)}"
        )
        print()

    print()

    if len(samples) < 2:
        print(
            "Hacen falta al menos 2 especies DISTINTAS para poder "
            "comparar. No se analizo nada."
        )
        return

    distinct_ids = {species_id for species_id, _ in samples}

    if len(distinct_ids) < 2:
        print(
            "Todas las muestras guardadas son de la MISMA especie "
            "-- no sirve para distinguir el offset (cualquier "
            "offset con ese valor fijo pasaria el filtro sin "
            "decir nada real). Repeti con especies distintas."
        )
        return

    print(f"Analizando {len(samples)} muestras ({len(distinct_ids)} especies distintas)...")
    print()

    for width in (1, 2):

        print(f"-- Candidatos de {width} byte(s) --")

        candidates = find_candidates(samples, width)

        if not candidates:
            print("  (ninguno)")
        else:
            for window_offset in candidates:
                real_offset = args.start + window_offset
                sign = "+" if real_offset >= 0 else "-"
                print(f"  offset {sign}{hex(abs(real_offset))}")

        print()


if __name__ == "__main__":
    main()

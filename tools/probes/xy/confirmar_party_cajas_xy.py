"""
Paso 3 del Bloque 14 (ruta multijuego, 04/10/2026): confirmar en vivo
los CANDIDATOS de party y cajas de Pokémon X/Y que dejó
buscar_party_xy.py (ver DexRelay_Guia_Ruta_Multi-Juego).

Lo que mostró buscar_party_xy.py con X (1.5) cargado:

  * Una tabla de 6 punteros consecutivos en 0x08CE1C6C (0x08CE1C6C ..
    0x08CE1C80), cada uno apuntando 0x40 ANTES del Pokémon -- la MISMA
    convención que la tabla de party de ORAS (POKEMON_POINTER_OFFSET).
    Los Pokémon apuntados forman un buffer de stride 0x1E4, igual que el
    "buffer de captura" de ORAS. Es decir: X/Y parece usar la misma
    mecánica de party que ORAS (riesgo R1 de la guía: descartado, a
    falta de esta confirmación).
  * Una cadena de 497 Pokémon con stride 0xE8 sin huecos desde
    0x08C861C8 (primer slot = Chespin): la Caja PC, contigua y sin
    padding entre cajas, como en ORAS.

Un candidato NO es una dirección confirmada (reglas 1, 11 y 12 del
Documento Maestro). Este probe lo valida con el CÓDIGO REAL del reader
(AzaharReader.read_pokemon / read_boxes_range) usando un perfil
temporal solo en memoria -- así lo que se confirme aquí es exactamente
lo que usará el perfil de X/Y.

Falta además la dirección de la CANTIDAD de Pokémon en el equipo. En ORAS
está 0x18 bytes después de la tabla (PARTY_COUNT = PARTY_ORDER + 0x18);
aquí se prueba ese mismo desplazamiento (0x08CE1C84) y se vuelcan los
bytes de alrededor para poder ver cuál cambia.

Solo lectura. USO (X o Y cargado en una partida, equipo real):

    python tools/probes/xy/confirmar_party_cajas_xy.py --watch

--watch repite cada segundo e imprime SOLO cuando algo cambia. Con el
probe corriendo, en el juego haz, uno por uno y esperando a ver la
salida de cada paso:

    1. Nada: compara el equipo impreso con tu equipo real (orden y niveles).
    2. Cambia el orden de dos Pokémon del equipo (menú Pokémon > Cambiar).
    3. Deposita un Pokémon en la caja (el equipo baja a 5).
    4. Retíralo (vuelve a 6).
    5. Anota en cuál Caja/slot está el primer Pokémon que ves en la salida
       "Cajas" y si coincide con lo que ves en el juego.

Sin --watch hace una sola lectura. Pega la salida completa en el chat.
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.games import registry  # noqa: E402
from app.games.base import GameCapabilities, GameContent, GameProfile, MemoryMap  # noqa: E402
from app.memory.structures import Pokemon6  # noqa: E402
from app.readers.azahar_reader import READ_FAILED, AzaharReader  # noqa: E402
from app.readers.citra import Citra  # noqa: E402

XY_TITLE_IDS = {0x0004000000055D00, 0x0004000000055E00}

# Candidatos de buscar_party_xy.py (X 1.5). NO son valores confirmados.
CANDIDATE_PARTY_TABLE = 0x08CE1C6C
CANDIDATE_PARTY_COUNT_OFFSET = 0x18  # como ORAS: tabla + 0x18
CANDIDATE_BOX_BASE = 0x08C861C8
BOX_SLOT_STRIDE = 0xE8
BOX_SLOT_COUNT = 30

# (caja, slot) a mostrar para comparar con el juego; 1-based.
BOX_SAMPLES = ((1, 1), (1, 30), (2, 1), (2, 30), (3, 1))


def parse_int(value):
    return int(value, 0)


def build_temp_profile(key, party_table, count_address, box_base):
    """Perfil SOLO en memoria con los candidatos (no se escribe a disco)."""
    return GameProfile(
        key=key,
        display_name="X/Y (candidatos, probe)",
        reader_kind="azahar",
        pokemon_format=Pokemon6,
        memory_map=MemoryMap(
            party_order_address=party_table,
            party_count_address=count_address,
            box_base_address=box_base,
            box_slot_stride=BOX_SLOT_STRIDE,
            box_slot_count=BOX_SLOT_COUNT,
        ),
        capabilities=GameCapabilities(),
        content=GameContent(),
    )


def select_process(citra, wanted):
    for pid, (title_id, name) in sorted(citra.process_list().items()):
        if wanted is not None:
            if name == wanted:
                return pid, name
        elif title_id in XY_TITLE_IDS:
            return pid, name

    return None


def describe(pokemon):
    if pokemon is None:
        return "(vacío)"

    if pokemon is READ_FAILED:
        return "(lectura fallida / checksum inválido)"

    return (
        f"#{pokemon.species_id():<4} {pokemon.nickname()!r:<14} "
        f"Nv{pokemon.level():<3} HP {pokemon.hp()}/{pokemon.max_hp()}"
    )


def read_box_slot(reader, box_index, slot):
    """Pokemon6 de un slot de caja (usa el código real del reader)."""
    raw = reader.read_box_slot_raw(box_index, slot)

    if raw is None:
        return None

    pokemon = Pokemon6.__new__(Pokemon6)
    pokemon.raw_data = raw
    return pokemon


def read_state(reader, count_address, table_address):
    """Todo lo que se imprime, como lista de líneas (para detectar cambios)."""
    lines = []

    raw_table = reader.memory.read(table_address, 24)
    pointers = (
        [int.from_bytes(raw_table[i:i + 4], "little") for i in range(0, 24, 4)]
        if raw_table and len(raw_table) == 24
        else []
    )

    around = reader.memory.read(count_address - 4, 0x20)
    count_byte = reader.memory.read(count_address, 1)

    lines.append(f"Tabla de punteros en 0x{table_address:08X}:")

    if not pointers:
        lines.append("  (no se pudo leer)")

    for slot, pointer in enumerate(pointers, start=1):
        pokemon = reader.read_pokemon(pointer)
        lines.append(f"  slot {slot}: puntero 0x{pointer:08X}  {describe(pokemon)}")

    lines.append(
        f"Cantidad candidata en 0x{count_address:08X}: "
        f"{count_byte[0] if count_byte else '?'}"
    )

    if around:
        lines.append(
            f"  bytes desde 0x{count_address - 4:08X}: {around.hex(' ')}"
        )

    lines.append("Cajas (comparar con el juego):")

    for box, slot in BOX_SAMPLES:
        pokemon = read_box_slot(reader, box, slot)
        lines.append(f"  Caja {box} slot {slot:>2}: {describe(pokemon)}")

    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--table", type=parse_int, default=CANDIDATE_PARTY_TABLE)
    parser.add_argument("--count", type=parse_int, default=None)
    parser.add_argument("--box-base", type=parse_int, default=CANDIDATE_BOX_BASE)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()

    count_address = (
        args.count
        if args.count is not None
        else args.table + CANDIDATE_PARTY_COUNT_OFFSET
    )

    citra = Citra()

    try:
        selected = select_process(citra, args.process)
    except OSError as error:
        print(f"No se pudo hablar con Azahar: {error!r}")
        return 1

    if selected is None:
        print("No se encontró el proceso de X/Y. Corre antes listar_procesos_xy.py.")
        return 1

    pid, name = selected
    citra.set_process(pid)

    profile = build_temp_profile(name, args.table, count_address, args.box_base)
    registry._PROFILES[name] = profile  # solo en memoria, solo en este probe

    # Resolvers falsos: el probe no necesita nombres ni el bridge .NET.
    reader = AzaharReader(
        citra=citra,
        species_resolver=object(),
        location_resolver=object(),
        process_name=name,
    )

    print(f"Proceso: {name}  (PID {pid})")
    print(
        f"Candidatos: tabla 0x{args.table:08X}, cantidad 0x{count_address:08X}, "
        f"caja base 0x{args.box_base:08X}\n"
    )

    previous = None

    while True:
        try:
            lines = read_state(reader, count_address, args.table)
        except OSError as error:
            lines = [f"(lectura UDP fallida: {error!r})"]

        if lines != previous:
            print(time.strftime("[%H:%M:%S]"))
            print("\n".join(lines))
            print()
            previous = lines

        if not args.watch:
            return 0

        time.sleep(1.0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nFin.")

"""
Busca DÓNDE guarda hoy el juego al Pokémon rival de un combate
salvaje, como estructura PK6 cifrada, en una ventana de memoria
ABSOLUTA (18/09/2026).

Por qué existe: LAST_CAUGHT_ADDRESS (0x08805638) devolvía la especie
del rival en pruebas anteriores, pero en la partida real del 18/09
read_last_caught() da None durante todo el combate (log real:
"last_caught.species=None"). O la dirección se movió en esa versión
exacta del juego (regla 4: las direcciones son específicas de la
versión), o el buffer se puebla en otro momento. Este probe lo
distingue y, si se movió, encuentra la nueva.

Solo LECTURA. Cierra DexRelay antes (comparte el socket UDP).

CÓMO USARLO:

    python -m tools.probes.memory.buscar_rival_pk6_absoluto

    1. Entrá a un combate SALVAJE (sin capturar todavía).
    2. Ya dentro, escribí en la terminal la especie del rival, EN
       INGLÉS (ej. "Zigzagoon"). Enter.
    3. Repetí en 3-4 combates con especies DISTINTAS: el script
       intersecta los resultados y deja solo las direcciones que
       coincidieron SIEMPRE.
    4. 'fin' para cortar.

Opciones:
    --start 0x08780000 --size 0x100000   ventana a escanear (por
    defecto 1 MB alrededor de LAST_CAUGHT_ADDRESS).
    Si con la ventana por defecto no aparece nada, ampliar
    (ej. --start 0x08000000 --size 0xD00000, tarda más).
"""

import argparse
import struct

from app.core.config import Config
from app.memory.pointers import LAST_CAUGHT_ADDRESS, SLOT_DATA_SIZE
from app.memory.structures import Pokemon6, decrypt_data
from app.readers.azahar_reader import AzaharReader
from tools.probes.memory.buscar_pk6_salvaje import (
    load_species_cache,
    resolve_species_id,
    suggest_species,
)

READ_CHUNK = 0x1000
DEFAULT_START = LAST_CAUGHT_ADDRESS - 0x80000
DEFAULT_SIZE = 0x100000


def read_window(memory, start, size):
    """Lee la ventana en bloques; los bloques fallidos quedan en 0."""

    data = bytearray(size)
    failed = 0

    for offset in range(0, size, READ_CHUNK):
        length = min(READ_CHUNK, size - offset)
        chunk = None

        for _ in range(3):
            try:
                chunk = memory.read(start + offset, length)
            except OSError:
                chunk = None

            if chunk is not None and len(chunk) == length:
                break

            chunk = None

        if chunk is None:
            failed += 1
            continue

        data[offset:offset + length] = chunk

    return bytes(data), failed


def find_valid_pk6(snapshot, base_address):
    """
    {dirección: speciesId} de todo lo que descifra con checksum
    válido. Prefiltro barato: en PK6 los bytes 4-5 (sanity) valen 0
    y el checksum (6-7) no.
    """

    found = {}

    for offset in range(0, len(snapshot) - SLOT_DATA_SIZE + 1, 4):

        if snapshot[offset + 4:offset + 6] != b"\x00\x00":
            continue

        if snapshot[offset + 6:offset + 8] == b"\x00\x00":
            continue

        if snapshot[offset:offset + 4] == b"\x00\x00\x00\x00":
            continue

        decrypted = decrypt_data(
            snapshot[offset:offset + SLOT_DATA_SIZE]
        )

        if not decrypted:
            continue

        pokemon = Pokemon6.__new__(Pokemon6)
        pokemon.raw_data = decrypted

        species_id = pokemon.species_id()

        if 1 <= species_id <= 721:
            found[base_address + offset] = species_id

    return found


def describe_current_last_caught(memory):

    data = memory.read(LAST_CAUGHT_ADDRESS, SLOT_DATA_SIZE)

    print(f"Contenido actual de {hex(LAST_CAUGHT_ADDRESS)}:")

    if data is None or len(data) != SLOT_DATA_SIZE:
        print("  lectura FALLIDA")
        return

    print(f"  primeros 16 bytes: {data[:16].hex(' ')}")

    if all(b == 0 for b in data[:8]):
        print("  -> vacío (ceros): no hay Pokémon ahí ahora.")
        return

    decrypted = decrypt_data(data)

    if not decrypted:
        print("  -> hay datos pero el checksum PK6 NO valida "
              "(dirección movida o escritura a medias).")
        return

    pokemon = Pokemon6.__new__(Pokemon6)
    pokemon.raw_data = decrypted
    print(f"  -> PK6 válido, speciesId={pokemon.species_id()}")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=lambda v: int(v, 0),
                        default=DEFAULT_START)
    parser.add_argument("--size", type=lambda v: int(v, 0),
                        default=DEFAULT_SIZE)
    args = parser.parse_args()

    species_list = load_species_cache()

    process_name = Config().get("azahar", "process_name", default=None)
    reader = AzaharReader(process_name=process_name)

    print("Conectando con Azahar...")

    if not reader.connect():
        print("No se pudo conectar.")
        return

    print(f"Conectado -- proceso: {reader.process_name}")
    print(f"Ventana: {hex(args.start)} .. {hex(args.start + args.size)}")
    print()

    describe_current_last_caught(reader.memory)
    print()

    survivors = None

    while True:

        answer = input(
            "Estando DENTRO de un combate salvaje, especie del "
            "rival en inglés ('fin' para cortar): "
        ).strip()

        if answer.lower() == "fin":
            break

        species_id = resolve_species_id(species_list, answer)

        if species_id is None:
            print("  No la reconozco. Parecidas:",
                  [e["name"] for e in suggest_species(species_list, answer)])
            continue

        snapshot, failed = read_window(
            reader.memory, args.start, args.size
        )

        if failed:
            print(f"  (aviso: {failed} bloques no se pudieron leer)")

        valid = find_valid_pk6(snapshot, args.start)
        hits = {a for a, sid in valid.items() if sid == species_id}

        print(f"  PK6 válidos en la ventana: {len(valid)}; "
              f"con esa especie: {len(hits)}")

        for address in sorted(hits)[:15]:
            delta = address - LAST_CAUGHT_ADDRESS
            print(f"    {hex(address)}  (LAST_CAUGHT {delta:+#x})")

        survivors = hits if survivors is None else survivors & hits

        print(f"  Direcciones que coincidieron en TODOS los "
              f"combates hasta ahora: {len(survivors)}")

        for address in sorted(survivors):
            print(f"    -> {hex(address)}  "
                  f"(LAST_CAUGHT {address - LAST_CAUGHT_ADDRESS:+#x})")

    print()
    print("Resultado final:",
          [hex(a) for a in sorted(survivors or [])] or "sin coincidencias")


if __name__ == "__main__":
    main()

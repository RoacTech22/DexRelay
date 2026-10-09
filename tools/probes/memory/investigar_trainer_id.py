"""
Investiga de dónde se puede sacar el identificador de la PARTIDA
(Trainer ID / Secret ID / nombre del entrenador) para el Bloque 5 de
la guía de la siguiente versión (23/09/2026).

Por qué existe: hoy DexRelay guarda un solo `nuzlocke_<juego>.json`
por juego (AS / OR). Con dos partidas distintas del mismo juego, los
datos se mezclarían. Para separarlas hace falta algo que identifique
QUÉ partida está cargada. Este probe evalúa las dos fuentes que NO
requieren una dirección de memoria nueva y, opcionalmente, busca la
tercera.

FUENTE A -- Pokémon propios (sin dirección nueva)
    Cada PK6 lleva TID (0x0C), SID (0x0E) y el nombre del entrenador
    original -- OT (0xB0) -- y el juego YA descifra esos bytes para
    la party y las cajas. Un Pokémon capturado o recibido de regalo por
    el jugador lleva SU Trainer ID. Un Pokémon recibido por intercambio
    lleva el de OTRA persona (y además tiene el "handler" HT en 0x78
    con el nombre del jugador). El script lee party + 7 cajas, muestra
    todo y hace un "voto" del (TID, SID, OT) más frecuente.

    Limitaciones que este probe permite medir con datos reales:
      * Con la party y las cajas vacías (partida recién empezada,
        antes del inicial) no hay de dónde sacarlo.
      * Si la mayoría de los Pokémon fueran de intercambio, el voto
        se equivocaría (en un Nuzlocke no debería pasar).

FUENTE B -- copia "viva" de la partida en RAM (opcional, --scan)
    El juego mantiene en memoria una copia de los datos del entrenador
    (la tarjeta de entrenador). Con el Trainer ID/OT ya conocidos por
    la Fuente A, se buscan en RAM las apariciones del nombre OT en
    UTF-16LE con el par TID/SID (u32) cerca. Se descartan las que caen
    a 0xA4 de distancia (esa es la firma de una estructura PK6:
    OT en 0xB0 menos TID en 0x0C). Lo que sobre son candidatos a la
    tarjeta de entrenador -- se imprime la distancia entre el nombre y
    el ID para poder compararla entre corridas y entre juegos.
    ESTO NO CONFIRMA NADA POR SÍ SOLO: hay que repetirlo con otra
    partida (otro TID) y ver que el candidato se mueva con la partida
    y NO con el Pokémon.

Cómo usarlo (cierra DexRelay antes: comparte el socket UDP):

    python -m tools.probes.memory.investigar_trainer_id
    python -m tools.probes.memory.investigar_trainer_id --scan

    Compara lo que imprime contra la Tarjeta de Entrenador del juego
    ("ID No." -- en ORAS son los 5 dígitos del TID16) y el nombre.

Opciones del scan:
    --start 0x08000000 --size 0x800000   ventana a escanear (por
    defecto 8 MB desde 0x08000000; ampliar si no aparece nada).

IMPORTANTE: solo lectura, no escribe nada en el juego.
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter

from tools.probes.legacy_pointers import (
    BOX_COUNT,
    BOX_SLOT_COUNT,
    BOX_SLOT_STRIDE,
    SLOT_DATA_SIZE,
)
from app.memory.structures import Pokemon6
from app.readers.azahar_reader import AzaharReader

# Offsets del formato PK6 (los mismos que ya usa PKHeX). Los primeros
# bytes (0x00-0x07) de la cabecera y TODOS estos campos quedan
# accesibles en `raw_data` una vez descifrado por Pokemon6.
PK6_TID_OFFSET = 0x0C
PK6_SID_OFFSET = 0x0E
PK6_HT_NAME_OFFSET = 0x78
PK6_OT_NAME_OFFSET = 0xB0
PK6_NAME_BYTES = 24  # 12 caracteres UTF-16LE
PK6_OT_GENDER_OFFSET = 0xDD
PK6_VERSION_OFFSET = 0xDF

# Distancia OT - TID dentro de un PK6 (0xB0 - 0x0C). Se usa para
# descartar en el scan las coincidencias que son un Pokémon.
PK6_OT_MINUS_TID = PK6_OT_NAME_OFFSET - PK6_TID_OFFSET

READ_CHUNK = 0x1000
DEFAULT_SCAN_START = 0x08000000
DEFAULT_SCAN_SIZE = 0x800000


def _decode_name(raw: bytes) -> str:
    try:
        return raw.decode("utf-16le", errors="ignore").split("\x00", 1)[0]
    except Exception:
        return ""


def extract_trainer_fields(raw_data: bytes) -> dict | None:
    """
    Saca los datos de entrenador de un PK6 YA DESCIFRADO (`raw_data`
    de Pokemon6). `None` si no alcanza el largo mínimo.

    `tid7` es el ID de 6 dígitos que muestra Gen 7 en adelante
    ((SID << 16 | TID) % 1_000_000); en ORAS la tarjeta muestra el
    TID de 16 bits directo, por eso se imprimen los dos.
    """

    if len(raw_data) < PK6_VERSION_OFFSET + 1:
        return None

    tid = struct.unpack_from("<H", raw_data, PK6_TID_OFFSET)[0]
    sid = struct.unpack_from("<H", raw_data, PK6_SID_OFFSET)[0]

    ot_name = _decode_name(
        raw_data[PK6_OT_NAME_OFFSET:PK6_OT_NAME_OFFSET + PK6_NAME_BYTES]
    )
    ht_name = _decode_name(
        raw_data[PK6_HT_NAME_OFFSET:PK6_HT_NAME_OFFSET + PK6_NAME_BYTES]
    )

    return {
        "tid": tid,
        "sid": sid,
        "tid7": ((sid << 16) | tid) % 1_000_000,
        "ot": ot_name,
        "ht": ht_name,
        "ot_gender": raw_data[PK6_OT_GENDER_OFFSET],
        "version": raw_data[PK6_VERSION_OFFSET],
    }


def vote_trainer(entries: list[dict]) -> tuple[tuple, int, int] | None:
    """
    Voto simple: la terna (tid, sid, ot) más repetida entre los
    Pokémon leídos. Devuelve (terna, votos, total) o `None` si no hay
    ningún Pokémon con OT legible.
    """

    valid = [e for e in entries if e and e["ot"]]

    if not valid:
        return None

    counts = Counter((e["tid"], e["sid"], e["ot"]) for e in valid)
    winner, votes = counts.most_common(1)[0]

    return winner, votes, len(valid)


def find_id_and_name_pairs(
    data: bytes,
    tid: int,
    sid: int,
    ot_name: str,
    max_distance: int = 0x100,
) -> list[tuple[int, int]]:
    """
    En `data` busca el nombre OT en UTF-16LE (terminado en 0x0000) y,
    a menos de `max_distance` bytes de él, el par TID,SID como dos u16
    seguidos. Devuelve [(offset_id, offset_nombre), ...] SIN filtrar
    las firmas de PK6 (eso lo hace el llamador).
    """

    if not ot_name:
        return []

    needle_name = ot_name.encode("utf-16le") + b"\x00\x00"
    needle_id = struct.pack("<HH", tid, sid)

    hits = []
    pos = data.find(needle_name)

    while pos != -1:
        low = max(0, pos - max_distance)
        high = min(len(data), pos + max_distance)

        id_pos = data.find(needle_id, low, high)

        while id_pos != -1:
            hits.append((id_pos, pos))
            id_pos = data.find(needle_id, id_pos + 1, high)

        pos = data.find(needle_name, pos + 1)

    return hits


def read_window(memory, start: int, size: int) -> tuple[bytes, int]:
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


def collect_pokemon_trainer_data(reader) -> list[dict]:
    """Party (6) + cajas 1..BOX_COUNT -> lista de dicts con origen."""

    rows = []

    for slot in range(1, 7):
        pokemon = reader.read_pokemon_raw_for_slot(slot)

        if pokemon is None or not pokemon.raw_data:
            continue

        fields = extract_trainer_fields(pokemon.raw_data)

        if fields is None:
            continue

        fields["origin"] = f"Party {slot}"
        fields["species_id"] = pokemon.species_id()
        fields["nickname"] = pokemon.nickname()
        rows.append(fields)

    for box_index in range(1, BOX_COUNT + 1):
        data = reader.read_box_raw(box_index)

        if data is None:
            continue

        for slot_index in range(BOX_SLOT_COUNT):
            start = slot_index * BOX_SLOT_STRIDE
            chunk = data[start:start + SLOT_DATA_SIZE]

            if len(chunk) != SLOT_DATA_SIZE:
                continue

            pokemon = Pokemon6(chunk)

            if not pokemon.raw_data:
                continue

            fields = extract_trainer_fields(pokemon.raw_data)

            if fields is None:
                continue

            fields["origin"] = f"Caja {box_index}.{slot_index + 1}"
            fields["species_id"] = pokemon.species_id()
            fields["nickname"] = pokemon.nickname()
            rows.append(fields)

    return rows


def print_table(rows: list[dict]) -> None:
    print(
        f"{'Origen':<12} {'Esp':>4} {'Nickname':<14} {'TID16':>6} "
        f"{'SID16':>6} {'TID7':>7} {'OT':<14} {'HT (traspasado)':<14}"
    )
    print("-" * 88)

    for row in rows:
        print(
            f"{row['origin']:<12} {row['species_id']:>4} "
            f"{row['nickname'][:14]:<14} {row['tid']:>6} "
            f"{row['sid']:>6} {row['tid7']:>7} "
            f"{row['ot'][:14]:<14} {row['ht'][:14]:<14}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true")
    parser.add_argument(
        "--start", type=lambda v: int(v, 0), default=DEFAULT_SCAN_START
    )
    parser.add_argument(
        "--size", type=lambda v: int(v, 0), default=DEFAULT_SCAN_SIZE
    )
    args = parser.parse_args()

    # process_name=None: detección automática (AzaharReader() sin
    # argumentos NO es automático, ver Documento Maestro 4.1).
    reader = AzaharReader(process_name=None)

    print("Conectando con Azahar...")

    if not reader.connect():
        print("No se pudo conectar (Azahar cerrado o sin juego).")
        return

    print(f"Conectado -- proceso: {reader.process_name}\n")

    print("=== FUENTE A: Trainer ID desde los Pokémon en memoria ===\n")

    rows = collect_pokemon_trainer_data(reader)

    if not rows:
        print("No se leyó ningún Pokémon (party y cajas vacías).")
        return

    print_table(rows)
    print()

    result = vote_trainer(rows)

    if result is None:
        print("Ningún Pokémon con OT legible.")
        return

    (tid, sid, ot), votes, total = result

    print(
        f"Voto: OT='{ot}'  TID16={tid}  SID16={sid}  "
        f"TID7={((sid << 16) | tid) % 1_000_000:06d}  "
        f"({votes} de {total} Pokémon)"
    )
    print(
        "\nCompara contra la Tarjeta de Entrenador del juego (nombre e "
        "'ID No.') y anota si coincide."
    )
    print(
        "Los Pokémon con OT distinto y HT con tu nombre son los "
        "recibidos por intercambio."
    )

    if not args.scan:
        return

    print("\n=== FUENTE B: buscar la copia viva en RAM ===\n")
    print(f"Ventana: {hex(args.start)} .. {hex(args.start + args.size)}")

    data, failed = read_window(reader.memory, args.start, args.size)

    if failed:
        print(f"(bloques que no se pudieron leer: {failed})")

    hits = find_id_and_name_pairs(data, tid, sid, ot)

    candidates = []
    pk6_like = 0

    for id_offset, name_offset in hits:
        distance = name_offset - id_offset

        if distance == PK6_OT_MINUS_TID:
            pk6_like += 1
            continue

        candidates.append((id_offset, name_offset, distance))

    print(
        f"Coincidencias totales: {len(hits)}  "
        f"(descartadas por firma PK6 [+0xA4]: {pk6_like})"
    )

    if not candidates:
        print(
            "Sin candidatos fuera de estructuras PK6. Prueba una "
            "ventana más grande (--size 0xD00000) o quédate con la "
            "Fuente A."
        )
        return

    print(
        f"\n{'Dirección ID':>12} {'Dirección nombre':>17} "
        f"{'nombre - id':>12}"
    )

    for id_offset, name_offset, distance in candidates:
        print(
            f"{hex(args.start + id_offset):>12} "
            f"{hex(args.start + name_offset):>17} "
            f"{distance:>+12}"
        )

    print(
        "\nPara confirmar un candidato: repite con OTRA partida "
        "(otro TID) y comprueba que el candidato se mueve con la "
        "partida. NO fijes nada en pointers.py hasta entonces."
    )


if __name__ == "__main__":
    main()

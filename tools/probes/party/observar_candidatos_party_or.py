"""
Observa en vivo los dos bloques candidatos encontrados en Omega
Ruby por buscar_party_omega_ruby.py (29/08/2026), para ver cuál
de los dos es la party "viva" (real) y cuál es solo una copia/
espejo que puede no reflejar cambios al instante.

IMPORTANTE (corregido tras el primer intento): la prueba NO
puede ser "pegarte en un combate salvaje y ver si cambia el HP"
-- ni siquiera en Alpha Sapphire el campo `hp` de la estructura
de party se actualiza en tiempo real durante un combate (por eso
existe un mecanismo COMPLETAMENTE APARTE, `COMBAT_POINTER_ADDRESS`,
solo para el HP en vivo de una pelea). La prueba correcta es
REORDENAR EL EQUIPO -- eso sí se refleja al toque en la
estructura de party real, sin depender de nada de combate.

COMO USARLO:

    python -m tools.probes.party.observar_candidatos_party_or

    Con el script corriendo:
    1. Andá al menú de Pokémon (o a la PC) y reordená tu equipo
       -- por ejemplo, intercambiá el primero y el segundo.
    2. Mirá cuál de los dos bloques (BLOQUE 1 o BLOQUE 2) refleja
       ese cambio de orden en el nickname, y cuál se queda igual.

El que SÍ cambie de orden en tiempo real es la party real -- 
pasame cuál fue y seguimos desde ahí.
"""

import struct
import time

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.memory.structures import Pokemon6, decrypt_data


BLOCK1_START = 0x08C814BC
BLOCK1_STRIDE = 0x104

BLOCK2_START = 0x08CFB26C
BLOCK2_STRIDE = 0x1E4

SLOT_DATA_SIZE = 232


def read_slot_summary(memory, address):
    """
    Lee un slot de 232 bytes en `address`, devuelve
    (nickname, especie) o None si no decodifica.

    Se sacó el intento de leer nivel/HP (versión anterior de este
    probe): el offset de stats usado (+344 bytes) fue calibrado
    específicamente para la estructura ya confirmada de Alpha
    Sapphire -- no hay garantía de que aplique igual acá, y de
    hecho no aplicó (daba nivel=0/hp=0 siempre). Nickname/especie
    sí decodifican bien con el checksum de los 232 bytes
    principales nomás, que es lo único que hace falta para esta
    prueba puntual (ver cuál bloque refleja el ORDEN real del
    equipo).
    """

    chunk = memory.read(address, SLOT_DATA_SIZE)

    if len(chunk) != SLOT_DATA_SIZE:
        return None

    decrypted = decrypt_data(chunk)

    if not decrypted:
        return None

    pokemon = Pokemon6.__new__(Pokemon6)
    pokemon.raw_data = decrypted

    return (
        pokemon.nickname(),
        pokemon.species_id(),
    )


def read_block(memory, start, stride):
    summaries = []

    for slot in range(6):
        address = start + slot * stride
        summary = read_slot_summary(memory, address)
        summaries.append(summary)

    return summaries


def format_block(name, summaries):
    lines = [f"-- {name} --"]

    for i, summary in enumerate(summaries):

        if summary is None:
            lines.append(f"  slot{i + 1}: (sin datos)")
            continue

        nickname, species_id = summary

        lines.append(
            f"  slot{i + 1}: {nickname!r}  "
            f"speciesId={species_id}"
        )

    return "\n".join(lines)


def main():
    print("================================")
    print("   OBSERVAR CANDIDATOS DE PARTY")
    print("   (Omega Ruby)")
    print("================================")
    print()

    process_name = Config().get(
        "azahar", "process_name", default="sango-2"
    )

    reader = AzaharReader(process_name=process_name)

    print(f"Buscando proceso {process_name!r}...")

    if not reader.connect():
        print(f"No se encontro {process_name!r}.")
        return

    print("Azahar conectado correctamente.")
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory

    last_block1 = None
    last_block2 = None

    try:
        while True:

            block1 = read_block(
                memory, BLOCK1_START, BLOCK1_STRIDE
            )
            block2 = read_block(
                memory, BLOCK2_START, BLOCK2_STRIDE
            )

            if block1 != last_block1:
                print(format_block("BLOQUE 1 (0x08C814BC)", block1))
                print()
                last_block1 = block1

            if block2 != last_block2:
                print(format_block("BLOQUE 2 (0x08CFB26C)", block2))
                print()
                last_block2 = block2

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

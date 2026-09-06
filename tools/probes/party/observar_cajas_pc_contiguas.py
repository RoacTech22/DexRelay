"""
Confirma (o descarta) si la Caja 2 en adelante vive contigua a la
Caja 1 en memoria, para AMBAS versiones (Alpha Sapphire / Omega
Ruby, auto-detectado).

Contexto (roadmap 06/09/2026, sección 5.2): hoy solo la Caja 1 tiene
dirección confirmada (BOX_BASE_ADDRESS, 30 slots, BOX_SLOT_STRIDE =
0xE8 = SLOT_DATA_SIZE exacto, sin padding). La Caja 1 resultó ser un
array compacto sin padding entre slots -- por eso la hipótesis mas
razonable para probar primero es que la Caja 2 empiece justo donde
termina la Caja 1:

    BOX_BASE_ADDRESS + (BOX_SLOT_COUNT * BOX_SLOT_STRIDE)

Pero, MISMA REGLA DE SIEMPRE: esto es una extrapolación a mano, no
una dirección confirmada -- hay que probarla en vivo antes de
integrarla a pointers.py. Este script no asume que es cierta, la
pone a prueba.

Qué hace exactamente:
    - Muestra en vivo (refresco cada 1s) qué hay en los primeros
      slots de la Caja 1 (para orientarte) Y en los primeros slots
      de la dirección hipotética de la Caja 2.
    - También prueba un segundo candidato por las dudas (mismo
      criterio que se usó en Omega Ruby con el stride: probar más
      de una hipótesis a la vez es más barato que tres corridas
      separadas). El segundo candidato es la posibilidad de que
      haya algún padding/cabecera entre cajas (se prueba con un
      offset extra de 0x4 y 0x8 bytes, que fueron los que aparecieron
      como "ruido" en investigaciones pasadas de otras estructuras).

CÓMO USARLO:

    1. Antes de correr esto, la Caja 1 debe tener AL MENOS 1
       Pokémon (para tener una referencia conocida en la salida).
    2. Correr:

           python -m tools.probes.party.observar_cajas_pc_contiguas

    3. Confirmar que el slot 1 de la Caja 1 se ve correcto.
    4. SIN CERRAR el script: cambiar a la Caja 2 en el juego (PC de
       Pokémon) y depositar un Pokémon ahí, uno reconocible (anotá
       el nickname/especie de antemano).
    5. Mirar la salida:
       - Si el Pokémon depositado aparece en "CANDIDATO A: contiguo
         exacto (offset 0)" -> hipótesis CONFIRMADA, la Caja 2 vive
         justo después de la Caja 1, sin padding. Avisar para fijar
         BOX_BASE_ADDRESS_BOX2 = BOX_BASE_ADDRESS + BOX_SLOT_COUNT *
         BOX_SLOT_STRIDE en pointers.py.
       - Si aparece en "CANDIDATO B/C" (con padding) -> anotar cuál
         offset exacto fue y avisar (no está premasticado un tercer
         candidato a ciegas -- si ninguno matchea, hace falta un
         escaneo más amplio tipo buscar_caja_pc.py pero apuntando
         después del final de la Caja 1, no cerca de la party).
       - Si NO aparece en ninguno -> la hipótesis de contigüidad
         queda descartada, hay que tratar la Caja 2 como una
         dirección independiente a cazar por separado (avisar para
         armar ese escaneo).
    6. Repetir el mismo procedimiento para Cajas 3+ una vez Caja 2
       esté confirmada (multiplicando el índice), pero recién
       después de tener Caja 2 confirmada -- no tiene sentido probar
       más lejos si la base de contigüidad ya falla en el primer
       salto.
"""

import time

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    BOX_SLOT_STRIDE,
    BOX_SLOT_COUNT,
    SLOT_DATA_SIZE,
    get_box_base_address,
)
from app.memory.structures import Pokemon6, decrypt_data


SLOTS_TO_SHOW = 3

# Tamaño real del bloque de la Caja 1 completa (30 slots * 232
# bytes), usado para calcular dónde "debería" empezar la Caja 2 si
# son contiguas sin padding.
BOX_BLOCK_SIZE = BOX_SLOT_COUNT * BOX_SLOT_STRIDE

# Offsets de padding candidatos a probar además del contiguo exacto,
# por si el juego deja algún separador entre cajas (encabezado de
# caja, flag de "caja usada", etc). Elegidos chicos y alineados a 4
# bytes -- no es una lista exhaustiva, es un punto de partida barato
# antes de pasar a un escaneo más caro si estos fallan.
PADDING_CANDIDATES = {
    "CANDIDATO A: contiguo exacto (offset 0)": 0x0,
    "CANDIDATO B: +4 bytes de padding": 0x4,
    "CANDIDATO C: +8 bytes de padding": 0x8,
}


def read_slot(memory, base, index):

    address = base + (BOX_SLOT_STRIDE * index)

    data = memory.read(address, SLOT_DATA_SIZE)

    if not data or len(data) != SLOT_DATA_SIZE:
        return address, None, None

    if data[:8] == b"\x00" * 8:
        return address, None, None

    decrypted = decrypt_data(data)

    if not decrypted:
        return address, "???", "(checksum invalido / vacio)"

    pokemon = Pokemon6.__new__(Pokemon6)
    pokemon.raw_data = decrypted

    return address, pokemon.species_id(), pokemon.nickname()


def print_slots(label, memory, base):

    print(f"--- {label} (base {hex(base)}) ---")

    for index in range(SLOTS_TO_SHOW):

        address, species_id, nickname = read_slot(memory, base, index)

        if species_id is None:
            print(f"  slot{index + 1} ({hex(address)}): vacio")
        else:
            print(
                f"  slot{index + 1} ({hex(address)}): "
                f"speciesId={species_id} nickname={nickname!r}"
            )

    print()


def main():
    print("=========================================")
    print("   OBSERVAR CAJAS PC CONTIGUAS (Caja 2+)")
    print("=========================================")
    print()

    # Modo automatico: detecta AS u OR, igual que el resto de la
    # GUI (find_game_process con process_name=None). OJO:
    # AzaharReader() SIN pasar process_name usa "sango-2" fijo por
    # defecto (ver su __init__), NO modo automatico -- hay que
    # pasar None explicito para que busque cualquiera de los dos
    # juegos conocidos.
    reader = AzaharReader(process_name=None)

    print("Buscando Azahar (Alpha Sapphire u Omega Ruby)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    print(f"Conectado: {reader.process_name!r}")

    box1_base = get_box_base_address(reader.process_name)
    box2_hypothesis = box1_base + BOX_BLOCK_SIZE

    print(f"BOX_BASE_ADDRESS (Caja 1): {hex(box1_base)}")
    print(
        f"Hipotesis Caja 2 (contigua, sin padding): "
        f"{hex(box2_hypothesis)}"
    )
    print()
    print(
        "Deposita un Pokemon RECONOCIBLE en la Caja 2 mientras esto "
        "corre, y fijate en cual candidato aparece."
    )
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory

    try:
        while True:

            print_slots("CAJA 1 (referencia conocida)", memory, box1_base)

            for label, padding in PADDING_CANDIDATES.items():
                print_slots(label, memory, box2_hypothesis + padding)

            print("=" * 40)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

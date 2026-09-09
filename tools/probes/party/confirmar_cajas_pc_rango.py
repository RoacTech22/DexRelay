"""
Roadmap 5.2 (Cajas PC 2-31): confirma (o descarta) que la hipótesis
de contigüidad ya validada para el salto Caja 1 -> Caja 2
(06/09/2026, tools/probes/party/observar_cajas_pc_contiguas.py) se
sostiene más allá de ese primer salto.

Alcance decidido (07/09/2026, a pedido del usuario): el juego trae
de fábrica solo 7 cajas habilitadas (+ la Caja de Combate, que es
una estructura completamente aparte -- no forma parte de este array
compacto de cajas normales, ni vale la pena tocarla acá). Comprar
cajas extra hasta llegar a las 31 es opcional y no todos los
Nuzlocke lo necesitan, así que este script solo apunta a lo que HOY
se puede probar sin gastar nada en el juego: Cajas 3, 5 y 7.

BOX_COUNT sigue en 31 en pointers.py -- si en algún momento se
compran más cajas, get_box_address()/read_box() ya van a funcionar
igual para ellas (misma fórmula extrapolada), solo que esas
direcciones puntuales (8-31) van a seguir sin confirmación empírica
propia hasta que alguien las pruebe en vivo -- documentado así a
propósito, no es un olvido.

Por qué NO se prueban las 7 una por una en vez de un muestreo: con
solo 7 cajas alcanzables, sí vale la pena mirarlas casi todas de una
sola pasada (3, 5 y 7 -- temprana, media y la última disponible),
en vez de limitarse a un par sueltas.

CÓMO USARLO:

    1. Correr:

           python -m tools.probes.party.confirmar_cajas_pc_rango

    2. Vas a ver 3 direcciones candidatas (una por caja objetivo),
       cada una mostrando qué hay ahí ahora mismo (probablemente
       "vacio" si nunca depositaste nada en esas cajas).
    3. SIN CERRAR el script: andá al juego, abrí la Caja objetivo
       (ej. Caja 3), depositá un Pokémon reconocible (anotá antes el
       nickname/especie), esperá el próximo refresco (1s) y fijate
       si aparece en la fila de esa caja.
    4. Repetí para las otras 2 cajas (podés hacerlas una por una o
       todas seguidas, el script no distingue orden).
    5. Reportar el resultado de las 3:
       - Si las 3 confirman -> se puede dar por buena la fórmula
         para las 7 cajas de fábrica (se documenta en pointers.py,
         y se deja constancia de que 8-31 sigue siendo extrapolación
         sin confirmar, para cuando haga falta).
       - Si alguna falla -> anotar CUÁL caja y en qué dirección
         apareció el Pokémon en realidad (si aparece cerca del
         candidato, puede ser un offset de padding fijo; si no
         aparece en ningún lado visible, hay que armar un escaneo
         más amplio como buscar_caja_pc.py apuntando alrededor de
         esa caja puntual).
"""

import time

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    BOX_SLOT_STRIDE,
    SLOT_DATA_SIZE,
    get_box_address,
)
from app.memory.structures import Pokemon6, decrypt_data


SLOTS_TO_SHOW = 2

# Índices de caja a muestrear (1-based, igual que get_box_address()).
# Acotado a las 7 cajas de fábrica (ver docstring del módulo) --
# no tiene sentido apuntar más allá de lo que hoy se puede probar
# sin comprar cajas extra en el juego.
TARGET_BOX_INDEXES = [3, 5, 7]


def read_slot(memory, box_base, slot_index):

    address = box_base + (BOX_SLOT_STRIDE * slot_index)

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


def print_box(label, memory, box_base):

    print(f"--- {label} (base {hex(box_base)}) ---")

    for slot_index in range(SLOTS_TO_SHOW):

        address, species_id, nickname = read_slot(
            memory, box_base, slot_index
        )

        if species_id is None:
            print(f"  slot{slot_index + 1} ({hex(address)}): vacio")
        else:
            print(
                f"  slot{slot_index + 1} ({hex(address)}): "
                f"speciesId={species_id} nickname={nickname!r}"
            )

    print()


def main():
    print("=================================================")
    print("   CONFIRMAR CAJAS PC EN RANGO (roadmap 5.2)")
    print("=================================================")
    print()

    # Modo automatico: process_name=None explicito, ver el mismo
    # comentario ya usado en observar_cajas_pc_contiguas.py --
    # AzaharReader() sin argumentos NO es modo automatico.
    reader = AzaharReader(process_name=None)

    print("Buscando Azahar (Alpha Sapphire u Omega Ruby)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    print(f"Conectado: {reader.process_name!r}")
    print()

    for box_index in TARGET_BOX_INDEXES:
        address = get_box_address(reader.process_name, box_index)
        print(f"Caja {box_index}, hipotesis: {hex(address)}")

    print()
    print(
        "Deposita un Pokemon RECONOCIBLE en cada una de estas cajas "
        "(podes hacerlo de a una o todas seguidas) y fijate en cual "
        "aparece."
    )
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory

    try:
        while True:

            for box_index in TARGET_BOX_INDEXES:

                box_base = get_box_address(
                    reader.process_name, box_index
                )

                print_box(f"CAJA {box_index}", memory, box_base)

            print("=" * 40)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

"""
Confirma BOX_BASE_ADDRESS/BOX_SLOT_STRIDE para Omega Ruby en vivo.

Contexto: buscar_caja_pc_or.py encontro un candidato aislado (sin
vecinos con checksum valido, justo lo esperado si la Caja PC tiene
solo 1 Pokemon adentro) en 0x08C9E134 con el Pokemon depositado
("Jhosy"). Antes de fijarlo como BOX_BASE_ADDRESS de Omega Ruby (regla
#14: confirmar con un probe dedicado antes de fijar un offset de
produccion), hace falta confirmar el STRIDE real -- en Alpha Sapphire
resulto ser 0xE8 (exactamente SLOT_DATA_SIZE, sin padding entre
slots), pero no se puede asumir que Omega Ruby usa el mismo valor sin
probarlo (misma leccion que ya dejo la investigacion de
PARTY_ORDER_ADDRESS).

Este script lee varios slots candidatos a la vez, probando DOS
strides posibles (0xE8, el de Alpha Sapphire, y 0x104, el que
aparecio en el otro cluster -- por las dudas) y muestra que hay en
cada uno, refrescando cada 1s.

COMO USARLO:

    1. Correr el script ANTES de depositar nada nuevo -- confirmar
       que el slot 1 (offset 0) ya muestra "Jhosy" (o el nombre del
       Pokemon que tengas ahi) en AMBOS strides (offset 0 es igual
       para los dos).
    2. Sin cerrar el script, depositar un SEGUNDO Pokemon distinto en
       la Caja PC (desde el juego).
    3. Ver en cual de los dos strides aparece el segundo Pokemon en
       el slot 2 -- ese es el stride correcto. Si aparece en los DOS,
       o en ninguno, avisar para pensar otra ventana.

    python -m tools.probes.party.observar_caja_pc_or
"""

import time

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import PROCESS_NAME_OMEGA_RUBY, SLOT_DATA_SIZE
from app.memory.structures import Pokemon6, decrypt_data


BOX_BASE_ADDRESS_CANDIDATE_OR = 0x08C9E134

# Candidatos a probar. 0xE8 == SLOT_DATA_SIZE (232), el que funciono
# en Alpha Sapphire. 0x104 (260) es el que aparecio en el otro
# cluster durante el escaneo -- se prueba tambien por las dudas,
# aunque ese cluster no parece ser la Caja PC real.
CANDIDATE_STRIDES = {
    "0xE8 (igual que Alpha Sapphire)": 0xE8,
    "0x104 (el del otro cluster)": 0x104,
}

SLOTS_TO_SHOW = 5


def read_slot(memory, base, stride, index):

    address = base + (stride * index)

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


def main():
    print("================================")
    print("   OBSERVAR CAJA PC (Omega Ruby)")
    print("================================")
    print()

    process_name = Config().get(
        "azahar", "process_name", default=PROCESS_NAME_OMEGA_RUBY
    )

    reader = AzaharReader(process_name=process_name)

    print(f"Buscando proceso {process_name!r}...")

    if not reader.connect():
        print(f"No se encontro {process_name!r}.")
        return

    print("Azahar conectado correctamente.")
    print(
        f"Base candidata: {hex(BOX_BASE_ADDRESS_CANDIDATE_OR)}"
    )
    print(
        "Deposita un SEGUNDO Pokemon distinto en la Caja PC mientras "
        "esto corre, y fijate en cual stride aparece en el slot 2."
    )
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory

    try:
        while True:

            for label, stride in CANDIDATE_STRIDES.items():

                print(f"--- Stride {label} ---")

                for index in range(SLOTS_TO_SHOW):

                    address, species_id, nickname = read_slot(
                        memory,
                        BOX_BASE_ADDRESS_CANDIDATE_OR,
                        stride,
                        index,
                    )

                    if species_id is None:
                        print(
                            f"  slot{index + 1} ({hex(address)}): vacio"
                        )
                    else:
                        print(
                            f"  slot{index + 1} ({hex(address)}): "
                            f"speciesId={species_id} "
                            f"nickname={nickname!r}"
                        )

                print()

            print("=" * 40)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

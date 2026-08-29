"""
Confirma si 0x08CFB1E0 (candidata a PARTY_ORDER_ADDRESS para
Omega Ruby, 29/08/2026) contiene una tabla real de 6 punteros --
calculada como PARTY_COUNT_ADDRESS_OR (0x08CFB1F8, ya confirmado
en vivo) menos 0x18, misma relación que ya se confirmó para
Alpha Sapphire (PARTY_COUNT_ADDRESS = PARTY_ORDER_ADDRESS + 0x18).

Qué hay que ver:
    - Si los 6 valores son direcciones no-cero, parecidas entre sí
      (mismo prefijo alto, tipo 0x08Cxxxxx) -- buena señal, es
      candidata real.
    - Si te sigue dando todo 0x0 -- la relación "+0x18" no se
      cumple igual en Omega Ruby, hay que buscar de otra forma.
    - Reordená el equipo mientras el script corre: si los 6
      valores se reordenan entre sí (como ya vimos que pasa en
      Alpha Sapphire), es la tabla real.

USO:
    python -m tools.probes.party.observar_orden_party_or
"""

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
import time


PARTY_ORDER_ADDRESS_OR = 0x08CFB1E0
ORDER_ENTRY_SIZE = 4


def main():
    print("================================")
    print("   OBSERVAR ORDEN DE PARTY")
    print("   (candidata, Omega Ruby)")
    print("================================")
    print()
    print(
        f"Dirección candidata: {hex(PARTY_ORDER_ADDRESS_OR)}"
    )
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
    previous = None

    try:
        while True:

            data = memory.read(
                PARTY_ORDER_ADDRESS_OR,
                ORDER_ENTRY_SIZE * 6,
            )

            if len(data) != ORDER_ENTRY_SIZE * 6:
                print("Lectura fallida.")
                time.sleep(0.5)
                continue

            pointers = [
                int.from_bytes(
                    data[
                        slot * ORDER_ENTRY_SIZE:
                        (slot + 1) * ORDER_ENTRY_SIZE
                    ],
                    byteorder="little",
                )
                for slot in range(6)
            ]

            parts = []

            for index, pointer in enumerate(pointers):

                changed = (
                    previous is not None
                    and pointer != previous[index]
                )

                marker = " <-- CAMBIO" if changed else ""

                parts.append(
                    f"slot{index + 1}={hex(pointer)}{marker}"
                )

            print("  ".join(parts))

            previous = pointers

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

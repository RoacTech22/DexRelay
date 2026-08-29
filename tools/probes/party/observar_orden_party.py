"""
Observa en vivo los 6 punteros de PARTY_ORDER_ADDRESS mientras
depositás un Pokémon en la Caja PC.

Contexto: el bug reportado (29/08/2026) es que el slot que queda
libre en el overlay del equipo, tras depositar un Pokémon que NO
es el último de la party, se sigue mostrando con el sprite del
último Pokémon del equipo en vez de quedar vacío -- confirmado que
YA pasaba antes de esta sesión (no es una regresión de los cambios
recientes del overlay), así que el problema está acá, en la
lectura de memoria, no en el JS.

Ya se probó una hipótesis (corregida en read_party_order():
tratar como vacío cualquier puntero que sea un duplicado EXACTO de
uno anterior) y el usuario reportó que el síntoma persiste -- así
que la hipótesis original (el puntero que sobra queda duplicado
tal cual) probablemente esté incompleta o sea incorrecta. Este
script es para ver, sin adivinar más, qué pasa REALMENTE con los
6 punteros en el momento exacto del depósito.

USO:
    1. Corré este script con 6 Pokémon en la party (los 6 slots
       llenos).
    2. Andá al menú de la PC, entrá a la party, y depositá un
       Pokémon que NO sea el último (por ejemplo, el del medio).
    3. Mirá qué imprime el script justo en ese momento y un par de
       segundos después -- especialmente cuál de los 6 punteros
       cambia, a qué valor, y si alguno queda IGUAL a otro.
    4. Repetí depositando el ÚLTIMO Pokémon de la party esta vez,
       para comparar si ese caso se comporta distinto (capaz ahí
       sí se limpia bien, y el bug es específico de depositar del
       medio).
    5. Copiá la salida completa (o al menos las líneas de antes/
       durante/después del depósito) para seguir la investigación
       con ese dato real en la mano.

Cada línea muestra los 6 punteros crudos (en hex) tal cual están
en la tabla, uno por slot, y marca con "<-- CAMBIO" los slots que
cambiaron respecto a la lectura anterior.
"""

import time

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    PARTY_ORDER_ADDRESS,
    ORDER_ENTRY_SIZE,
)


def read_raw_pointers(memory):
    data = memory.read(
        PARTY_ORDER_ADDRESS,
        ORDER_ENTRY_SIZE * 6,
    )

    if len(data) != ORDER_ENTRY_SIZE * 6:
        return None

    return [
        int.from_bytes(
            data[
                slot * ORDER_ENTRY_SIZE:
                (slot + 1) * ORDER_ENTRY_SIZE
            ],
            byteorder="little",
        )
        for slot in range(6)
    ]


def format_pointers(pointers, previous):

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

    line = "  ".join(parts)

    # Duplicados entre slots -- dos Pokémon reales de la party
    # nunca pueden compartir la misma dirección de memoria, así
    # que cualquier coincidencia acá (fuera de 0x0) es sospechosa.
    seen = {}
    duplicates = []

    for index, pointer in enumerate(pointers):

        if pointer == 0:
            continue

        if pointer in seen:
            duplicates.append(
                f"slot{seen[pointer] + 1}==slot{index + 1}"
                f"=={hex(pointer)}"
            )
        else:
            seen[pointer] = index

    if duplicates:
        line += "   DUPLICADOS: " + ", ".join(duplicates)

    return line


def main():
    print("================================")
    print("   OBSERVAR ORDEN DE PARTY")
    print("================================")
    print()
    print(f"PARTY_ORDER_ADDRESS = {hex(PARTY_ORDER_ADDRESS)}")
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory
    previous = None

    try:
        while True:

            pointers = read_raw_pointers(memory)

            if pointers is None:
                print("Lectura fallida (tamano incorrecto).")
                time.sleep(0.5)
                continue

            print(
                format_pointers(pointers, previous)
            )

            previous = pointers

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

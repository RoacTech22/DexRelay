"""
Confirma en vivo los 2 candidatos que sobrevivieron dos corridas
independientes de rastrear_zona_actual.py (distinta secuencia,
distinto save, cero lugares en comun entre ambas):

    0x8c6a7b2
    0x8c6a894

En las dos corridas dieron siempre el mismo valor entre si (parecen
ser la misma zona guardada por duplicado en dos lugares), asi que
esto observa ambos a la vez para confirmar esa hipotesis tambien.

A diferencia de rastrear_zona_actual.py (que pide una secuencia
fija de antemano y compara snapshots), este es de observacion libre
en vivo, mismo patron que observar_puntero_combate.py: corre el
script, camina por el mapa, y mira si el valor cambia exactamente
cuando cambias de zona -- y si vuelve al mismo numero cuando volves
a un lugar ya visitado.

COMO USARLO:

    1. Corre el script (el juego ya tiene que estar abierto, en
       cualquier lugar del mapa, fuera de combate/menus).
    2. Fijate el valor inicial impreso.
    3. Camina a otra ruta/ciudad distinta. Deberia imprimir una
       linea nueva con "<-- CAMBIO" apenas el juego actualice el
       valor.
    4. Volve al lugar de partida. Confirmar: tiene que volver a
       imprimir el MISMO valor que el paso 2 (no uno parecido, el
       mismo exacto).
    5. Repetir el paso 3-4 con 2-3 lugares mas para estar tranquilo.

Si el valor sube/baja de forma rara dentro del MISMO lugar (por
ejemplo cambia solo mientras caminas, sin cruzar ninguna frontera
de zona), probablemente sea un candidato falso (por ejemplo, alguna
variable de posicion/animacion que solo coincidio por casualidad en
las dos corridas anteriores) y hay que descartarlo.

Presiona Ctrl+C para detener.
"""

import time

from app.readers.azahar_reader import AzaharReader


CANDIDATES = {
    "0x8c6a7b2": 0x08C6A7B2,
    "0x8c6a894": 0x08C6A894,
}

POLL_SECONDS = 0.5


def read_byte(memory, address):
    data = memory.read(address, 1)

    if len(data) != 1:
        return None

    return data[0]


def main():
    print("================================")
    print("   VERIFICAR ZONA ACTUAL")
    print("================================")
    print()

    for label, address in CANDIDATES.items():
        print(f"Candidato {label} = {hex(address)}")

    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print("Camina entre lugares y mira si los valores cambian.")
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory
    last_values = {label: None for label in CANDIDATES}

    try:
        while True:
            current_values = {}

            for label, address in CANDIDATES.items():
                current_values[label] = read_byte(memory, address)

            changed_labels = [
                label
                for label in CANDIDATES
                if current_values[label] != last_values[label]
            ]

            if changed_labels or last_values[
                next(iter(CANDIDATES))
            ] is None:

                parts = []

                for label in CANDIDATES:
                    value = current_values[label]
                    marker = (
                        " <-- CAMBIO"
                        if label in changed_labels
                        and last_values[label] is not None
                        else ""
                    )
                    parts.append(f"{label}={value}{marker}")

                same_between_candidates = (
                    len(set(current_values.values())) == 1
                )
                agreement = (
                    "  (coinciden entre si)"
                    if same_between_candidates
                    else "  (NO coinciden entre si)"
                )

                print("  ".join(parts) + agreement)

            last_values = current_values

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

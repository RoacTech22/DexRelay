"""
Recorre Hoenn y arma la tabla ID -> nombre de lugar de
CURRENT_ZONE_ID_ADDRESS (confirmada el 27/08/2026, ver
DexRelay_Contexto_Deteccion_Perdido.md, pieza 1).

Esta tabla es NUEVA y separada de la que ya usa PKHeX para
Met_Location -- no hay garantia de que los IDs coincidan entre
ambos sistemas.

Distinto de rastrear_zona_actual.py (que busca LA DIRECCION en si,
comparando muchos offsets a la vez) y de verificar_zona_actual.py
(observacion libre en vivo, sin guardar nada) -- este script ya da
por CONFIRMADA la direccion, y su unico trabajo es recorrer lugares
y guardar el mapeo id -> nombre en un archivo, pudiendo pausar y
retomar entre sesiones.

COMO USARLO:

    python -m tools.probes.memory.mapear_zonas

    1. El script carga lo que ya este guardado en
       zonas_recolectadas.json (si existe) y lo muestra.
    2. Parate en un lugar del mapa (fuera de combate/menus) y
       escribi su nombre cuando te lo pida (o "salir" para
       terminar).
    3. Lee el valor varias veces para confirmar que esta quieto
       (mismo criterio de estabilidad que rastrear_zona_actual.py)
       antes de guardarlo.
    4. Si el mismo nombre ya tenia un ID distinto guardado, o el
       mismo ID ya tenia otro nombre, avisa el conflicto en vez de
       pisar en silencio -- hay que revisar a mano cual es el
       correcto (puede ser un typo del nombre, o que dos lugares
       resulten compartir el mismo ID de zona, lo cual tambien
       seria un dato real interesante).
    5. Guarda a disco despues de cada lugar (no hace falta terminar
       toda la sesion de una para no perder progreso).

Al terminar (o en cualquier momento intermedio), el archivo
zonas_recolectadas.json queda en tools/probes/memory/ junto a este
script, con el mapeo nombre -> id acumulado hasta ese punto.
"""

import json
import time
from pathlib import Path

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import CURRENT_ZONE_ID_ADDRESS


OUTPUT_PATH = Path(__file__).parent / "zonas_recolectadas.json"

# Mismo criterio que rastrear_zona_actual.py: varias lecturas
# seguidas, exigir que coincidan, para no guardar un valor de
# transito (a mitad de un cruce de zona, por ejemplo).
STABILITY_READS = 4
STABILITY_DELAY_SECONDS = 0.3
STABILITY_MAX_ATTEMPTS = 5


def load_existing():
    if not OUTPUT_PATH.exists():
        return {}

    with OUTPUT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def read_stable_zone_id(memory):
    """
    Lee CURRENT_ZONE_ID_ADDRESS varias veces seguidas y exige que
    coincidan, para no guardar un valor de transito (a mitad de un
    cruce de zona). Devuelve el valor si se estabilizo, o None si
    no lo logro tras STABILITY_MAX_ATTEMPTS intentos.
    """

    for attempt in range(1, STABILITY_MAX_ATTEMPTS + 1):

        values = []

        for _ in range(STABILITY_READS):

            data = memory.read(CURRENT_ZONE_ID_ADDRESS, 1)

            if len(data) != 1:
                return None

            values.append(data[0])
            time.sleep(STABILITY_DELAY_SECONDS)

        if all(value == values[0] for value in values[1:]):
            return values[0]

        print(
            f"  (intento {attempt}/{STABILITY_MAX_ATTEMPTS}: "
            f"el valor cambio durante la lectura -- reintentando; "
            f"quedate quieto)"
        )

    return None


def print_table(data):
    if not data:
        print("(todavia no hay lugares guardados)")
        return

    by_id = sorted(data.items(), key=lambda item: item[1])

    for name, zone_id in by_id:
        print(f"  {zone_id:>3}  {name}")


def main():
    print("================================")
    print("   MAPEAR ZONAS")
    print("================================")
    print()
    print(f"CURRENT_ZONE_ID_ADDRESS = {hex(CURRENT_ZONE_ID_ADDRESS)}")
    print(f"Archivo de progreso: {OUTPUT_PATH}")
    print()

    data = load_existing()

    print(f"Lugares ya guardados ({len(data)}):")
    print_table(data)
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print()
    print(
        "Parate en un lugar (fuera de combate/menus), escribi su "
        "nombre y presiona Enter. Escribi 'salir' para terminar."
    )
    print()

    memory = reader.memory

    while True:

        name = input("Lugar (o 'salir'): ").strip()

        if not name:
            continue

        if name.lower() in ("salir", "exit", "quit"):
            break

        print("Leyendo (quedate quieto)...")

        zone_id = read_stable_zone_id(memory)

        if zone_id is None:
            print(
                "No se logro una lectura estable. Probá de nuevo, "
                "bien quieto."
            )
            print()
            continue

        # Conflicto: mismo nombre, ID distinto al ya guardado.
        if name in data and data[name] != zone_id:
            print(
                f"  AVISO: '{name}' ya estaba guardado con ID "
                f"{data[name]}, y ahora se leyo {zone_id}. "
                f"No se sobreescribe solo -- revisa si es un typo "
                f"del nombre, si te moviste de zona sin darte "
                f"cuenta antes de confirmar, o si hace falta "
                f"corregir a mano en el archivo."
            )
            print()
            continue

        # Conflicto: mismo ID, nombre distinto al ya guardado.
        existing_name_for_id = next(
            (
                other_name
                for other_name, other_id in data.items()
                if other_id == zone_id and other_name != name
            ),
            None,
        )

        if existing_name_for_id is not None:
            print(
                f"  AVISO: el ID {zone_id} ya estaba guardado como "
                f"'{existing_name_for_id}'. Puede ser que este "
                f"lugar comparta el mismo ID de zona (dato real, a "
                f"veces pasa con sub-areas), o que uno de los dos "
                f"nombres tenga un typo. Se guarda igual -- "
                f"revisar despues."
            )

        data[name] = zone_id
        save(data)

        print(f"  Guardado: {name} = {zone_id}")
        print()

    print()
    print("================================")
    print(f"   TOTAL GUARDADO: {len(data)} lugares")
    print("================================")
    print_table(data)


if __name__ == "__main__":
    main()

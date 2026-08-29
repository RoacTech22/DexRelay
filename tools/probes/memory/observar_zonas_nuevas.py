"""
Version pasiva de mapear_zonas.py: en vez de que vos elijas de
antemano a que lugar ir, esto corre mientras jugas NORMAL (avanzando
la historia, entrando a edificios, lo que sea) y solo te interrumpe
cuando detecta una zona que todavia no esta en
zonas_recolectadas.json.

Asi no hace falta planear una gira por todo el mapa -- alcanza con
jugar como jugarias igual, y la tabla se va completando sola con
los lugares que de verdad recorres.

COMO USARLO:

    python -m tools.probes.memory.observar_zonas_nuevas

    1. Cargalo con el juego ya abierto, en cualquier lugar.
    2. Jugá normal.
    3. Cuando cruces a una zona ya conocida, el script solo lo
       menciona de pasada (no te interrumpe).
    4. Cuando cruces a una zona NUEVA (no guardada todavia), el
       script espera a que el valor se asiente (undisruptivo, no
       hace falta que dejes de caminar) y recien ahi te pide el
       nombre por teclado. Mientras esta esperando tu respuesta, el
       juego sigue corriendo en la ventana de Azahar sin problema
       -- respondé cuando puedas, no hay apuro.
    5. Guarda a disco despues de cada zona nueva nombrada, mismo
       archivo que mapear_zonas.py (podes combinar ambos scripts
       sin problema, comparten el mismo zonas_recolectadas.json).

Si en algun momento escribis "salir" en vez de un nombre, esa zona
queda SIN nombrar por ahora (no se guarda, no se vuelve a preguntar
en esta misma corrida hasta que el ID cambie a otra cosa y vuelva) y
el script sigue jugando en segundo plano.

Presiona Ctrl+C para terminar la sesion.
"""

import json
import time
from pathlib import Path

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import CURRENT_ZONE_ID_ADDRESS


OUTPUT_PATH = Path(__file__).parent / "zonas_recolectadas.json"

# Cada cuanto se sondea la direccion mientras se juega.
POLL_SECONDS = 0.4

# Cuantas lecturas SEGUIDAS con el mismo valor hacen falta para
# considerar que el jugador ya "se asento" en la zona nueva (y no
# esta a mitad de un cruce, con el valor todavia inestable). No
# hace falta que el jugador se quede quieto para esto -- alcanza
# con que el valor deje de cambiar de un sondeo al otro.
CONFIRM_POLLS = 3


def load_existing():
    if not OUTPUT_PATH.exists():
        return {}

    with OUTPUT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def build_id_to_name(data):
    id_to_name = {}

    for name, zone_id in data.items():
        # Si dos nombres comparten ID (dato real posible, ver aviso
        # en mapear_zonas.py), se muestra solo el primero que
        # aparezca -- no afecta la deteccion, solo el texto
        # mostrado.
        id_to_name.setdefault(zone_id, name)

    return id_to_name


def read_zone_id(memory):
    data = memory.read(CURRENT_ZONE_ID_ADDRESS, 1)

    if len(data) != 1:
        return None

    return data[0]


def main():
    print("================================")
    print("   OBSERVAR ZONAS NUEVAS")
    print("================================")
    print()
    print(f"CURRENT_ZONE_ID_ADDRESS = {hex(CURRENT_ZONE_ID_ADDRESS)}")
    print(f"Archivo de progreso: {OUTPUT_PATH}")
    print()

    data = load_existing()
    id_to_name = build_id_to_name(data)

    print(f"Zonas ya conocidas: {len(data)}")
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print("Jugá normal. Ctrl+C para terminar.")
    print()

    memory = reader.memory

    last_reported_id = None
    pending_id = None
    pending_streak = 0
    skipped_ids = set()

    try:
        while True:

            current_id = read_zone_id(memory)

            if current_id is None:
                time.sleep(POLL_SECONDS)
                continue

            if current_id == pending_id:
                pending_streak += 1
            else:
                pending_id = current_id
                pending_streak = 1

            settled = pending_streak >= CONFIRM_POLLS

            if settled and current_id != last_reported_id:

                last_reported_id = current_id

                if current_id in id_to_name:
                    print(
                        f"Zona conocida: {id_to_name[current_id]} "
                        f"(id={current_id})"
                    )

                elif current_id in skipped_ids:
                    # Ya la salteaste esta sesion, no volver a
                    # preguntar hasta que cambies de zona y vuelvas.
                    print(
                        f"Zona sin nombrar (salteada antes): "
                        f"id={current_id}"
                    )

                else:
                    print()
                    print(
                        f"*** ZONA NUEVA detectada: id={current_id} "
                        f"***"
                    )

                    name = input(
                        "  ¿Cómo se llama este lugar? "
                        "(o 'salir' para no nombrarla ahora): "
                    ).strip()

                    if name and name.lower() not in (
                        "salir",
                        "skip",
                    ):

                        if name in data and data[name] != current_id:
                            print(
                                f"  AVISO: '{name}' ya estaba "
                                f"guardado con otro ID "
                                f"({data[name]}). No se "
                                f"sobreescribe -- revisa a mano."
                            )
                        else:
                            data[name] = current_id
                            id_to_name.setdefault(current_id, name)
                            save(data)
                            print(f"  Guardado: {name} = {current_id}")

                    else:
                        skipped_ids.add(current_id)
                        print("  Sin nombrar por ahora.")

                    print()

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        print()
        print("================================")
        print(f"   SESION TERMINADA -- {len(data)} zonas guardadas")
        print("================================")


if __name__ == "__main__":
    main()

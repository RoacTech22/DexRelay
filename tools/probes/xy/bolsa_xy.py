"""
P5 (paridad X/Y, 09/10/2026), paso 1: ¿dónde está el bolsillo de MEDICINA en
X/Y? (el Caramelo Raro se escribe ahí).

Lo único que falta para el Caramelo Raro en X/Y es esa dirección: el
servicio de bolsa (`BagService`) ya es genérico y lee la dirección del perfil.
En ORAS el bolsillo de Medicina quedaba 0x970 bytes después del de Objetos;
en X/Y NO se asume lo mismo (hay menos Objetos Clave), por eso se mide.

Este probe es de SOLO LECTURA (no escribe nada):
  1. Vuelca una ventana ancha desde el inicio del bolsillo de Objetos
     (confirmado en P3) y la parte en TRAMOS de casilleros con datos
     separados por rachas de casilleros vacíos (0,0), con el nombre de cada
     objeto. Ahí se ve a ojo qué tramo es Objetos, Objetos Clave, MT/MO,
     Medicina y Bayas.
  2. Queda vigilando la ventana: cada cambio de cantidad se imprime con su
     DIRECCIÓN exacta y el tramo al que pertenece. Así se ancla el bolsillo
     sin suponer nada: tira (o usa) UNA unidad de un objeto de Medicina
     (Poción, Revivir, Antídoto...) y la dirección sale sola.

USO, con X o Y cargado en Azahar:

    python tools/probes/xy/bolsa_xy.py

Con el probe corriendo (la bolsa del juego, sin guardar nada):
  a) Tira o usa 1 unidad de un objeto de MEDICINA (p. ej. una Poción).
  b) Tira 1 unidad de un objeto CLAVE o una MT, y 1 Baya, si tienes (para
     ver los límites de los bolsillos vecinos). Opcional.
Ctrl+C termina, imprime el resumen y guarda
tools/probes/xy/salida/bolsa_xy.json. Pega el resumen en el chat y adjunta el
JSON.
"""

import argparse
import json
import struct
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = Path(__file__).resolve().parent / "salida" / "bolsa_xy.json"
ITEM_CACHE_PATH = PROJECT_ROOT / "data" / "item_cache.json"

SLOT_SIZE = 4
# Ventana por defecto: 1500 casilleros = 6000 bytes desde el bolsillo de
# Objetos (en ORAS la Medicina estaba a 604 casilleros del inicio).
DEFAULT_SLOTS = 1500
POLL_SECONDS = 0.5
# Casilleros vacíos seguidos que cuentan como separación entre tramos.
MIN_VACIOS = 4


def cargar_nombres(path=ITEM_CACHE_PATH):
    """{id: nombre}; vacío si no hay caché (el probe sigue funcionando)."""
    try:
        with Path(path).open(encoding="utf-8") as file:
            return {int(e["id"]): e["name"] for e in json.load(file)}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def leer_casilleros(data, base):
    """{dirección: (id, cantidad)} de todos los casilleros de `data`."""
    casilleros = {}

    if not data:
        return casilleros

    for offset in range(0, len(data) - SLOT_SIZE + 1, SLOT_SIZE):
        casilleros[base + offset] = struct.unpack_from("<HH", data, offset)

    return casilleros


def tramos(casilleros, min_vacios=MIN_VACIOS):
    """
    Parte los casilleros (ordenados por dirección) en tramos de datos.

    Un tramo termina tras `min_vacios` casilleros (0,0) seguidos. Devuelve
    [{"inicio", "fin", "n", "items": [(dirección, id, cantidad)]}] con
    "fin" = dirección del último casillero con datos.
    """
    resultado = []
    actual = None
    vacios = 0

    for direccion in sorted(casilleros):
        item_id, cantidad = casilleros[direccion]

        if item_id == 0 and cantidad == 0:
            vacios += 1

            if actual is not None and vacios >= min_vacios:
                resultado.append(actual)
                actual = None

            continue

        vacios = 0

        if actual is None:
            actual = {"inicio": direccion, "fin": direccion, "items": []}

        actual["fin"] = direccion
        actual["items"].append((direccion, item_id, cantidad))

    if actual is not None:
        resultado.append(actual)

    for tramo in resultado:
        tramo["n"] = len(tramo["items"])

    return resultado


def tramo_de(direccion, lista_tramos):
    """Tramo que contiene la dirección (o None si cae entre tramos)."""
    for tramo in lista_tramos:
        if tramo["inicio"] <= direccion <= tramo["fin"]:
            return tramo

    return None


def diferencias(anterior, actual):
    """[(dirección, (id, cant) antes, (id, cant) después)] de lo que cambió."""
    cambios = []

    for direccion in sorted(set(anterior) | set(actual)):
        antes = anterior.get(direccion, (0, 0))
        despues = actual.get(direccion, (0, 0))

        if antes != despues:
            cambios.append((direccion, antes, despues))

    return cambios


def nombre(item_id, nombres):
    return nombres.get(item_id, "?")


def formatear_tramos(lista_tramos, nombres, base=None):
    lines = []

    for numero, tramo in enumerate(lista_tramos, 1):
        rel = (
            f" (+0x{tramo['inicio'] - base:X} desde el bolsillo de Objetos)"
            if base is not None else ""
        )
        lines.append(
            f"Tramo {numero}: 0x{tramo['inicio']:08X} .. 0x{tramo['fin']:08X}"
            f"{rel}, {tramo['n']} casilleros con datos"
        )

        for direccion, item_id, cantidad in tramo["items"]:
            lines.append(
                f"    0x{direccion:08X}  id={item_id:>4}  x{cantidad:<4} "
                f"{nombre(item_id, nombres)}"
            )

    return "\n".join(lines)


def formatear_cambios(eventos, lista_tramos, nombres, base=None):
    lines = [f"Cambios registrados: {len(eventos)}"]

    for e in eventos:
        tramo = tramo_de(e["direccion"], lista_tramos)
        donde = (
            f"tramo que empieza en 0x{tramo['inicio']:08X}"
            + (
                f" (+0x{tramo['inicio'] - base:X})"
                if base is not None else ""
            )
            if tramo else "fuera de tramos"
        )
        antes_id, antes_c = e["antes"]
        desp_id, desp_c = e["despues"]
        lines.append(
            f"  0x{e['direccion']:08X}: id {antes_id} x{antes_c} -> "
            f"id {desp_id} x{desp_c} "
            f"({nombre(desp_id or antes_id, nombres)}); {donde}"
        )

    return "\n".join(lines)


def guardar(base, casilleros, lista_tramos, eventos, path=OUTPUT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    datos = {
        "base": base,
        "tramos": [
            {
                "inicio": t["inicio"], "fin": t["fin"], "n": t["n"],
                "items": [list(i) for i in t["items"]],
            }
            for t in lista_tramos
        ],
        "eventos": eventos,
    }

    with tmp.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(datos, file, indent=1, ensure_ascii=False)
        file.write("\n")

    tmp.replace(path)


# ---------------------------------------------------------------------
# E/S (no se prueba sin Azahar)
# ---------------------------------------------------------------------

def main():
    from app.games.registry import get_profile
    from app.readers.azahar_reader import AzaharReader

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--casilleros", type=int, default=DEFAULT_SLOTS)
    args = parser.parse_args()

    reader = AzaharReader(process_name=args.process)

    if not reader.connect():
        print("No se pudo conectar con Azahar / no se encontró X o Y.")
        return 1

    if get_profile(reader.process_name) is None:
        print(f"El juego {reader.process_name!r} no tiene perfil.")
        return 1

    base = reader._field("items_pocket_start_address")

    if base is None:
        print("El perfil no tiene el bolsillo de Objetos confirmado.")
        return 1

    size = args.casilleros * SLOT_SIZE

    def leer():
        data = reader.memory.read(base, size)

        if data is None or len(data) != size:
            return None

        return leer_casilleros(data, base)

    nombres = cargar_nombres()
    actual = leer()

    if actual is None:
        print("No se pudo leer la bolsa.")
        return 1

    lista_tramos = tramos(actual)
    print(
        f"Juego: {reader.profile.display_name}. Ventana: {args.casilleros} "
        f"casilleros desde 0x{base:08X}.\n"
    )
    print(formatear_tramos(lista_tramos, nombres, base))
    print(
        "\nVigilando cambios. Tira o usa 1 unidad de un objeto de MEDICINA "
        "(y opcionalmente de otros bolsillos). Ctrl+C para terminar.\n",
        flush=True,
    )

    eventos = []
    t0 = time.time()

    try:
        while True:
            nuevo = leer()

            if nuevo is not None:
                for direccion, antes, despues in diferencias(actual, nuevo):
                    eventos.append({
                        "t": round(time.time() - t0, 1),
                        "direccion": direccion,
                        "antes": list(antes),
                        "despues": list(despues),
                    })
                    print(
                        time.strftime("[%H:%M:%S]"),
                        f"0x{direccion:08X}: id {antes[0]} x{antes[1]} -> "
                        f"id {despues[0]} x{despues[1]} "
                        f"({nombre(despues[0] or antes[0], nombres)})",
                        flush=True,
                    )

                actual = nuevo

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        pass

    guardar(base, actual, lista_tramos, eventos)
    print(f"\nGuardado en {OUTPUT_PATH}.\n")
    print(formatear_cambios(eventos, lista_tramos, nombres, base))

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
P3 (paridad X/Y, 06/10/2026): ¿se puede reconocer un fósil revivido por
la BOLSA, sin mirar qué Pokémon salió?

Propuesta de Ronald (randomlocke: el fósil puede revivir cualquier
especie, así que ni la especie ni el lugar de encuentro alcanzan, porque
una captura pescada en Pueblo Petroglifo trae el mismo lugar 44): vigilar
la cantidad de fósiles en la bolsa y, cada vez que baje 1 y aparezca un
Pokémon nuevo, ese Pokémon es el del fósil.

Este probe NO decide nada: mide si la idea es viable.
  1. ¿Los fósiles se ven en el bolsillo de Objetos (400 casilleros, el
     mismo que ya se lee para las Poké Balls)? Registra TODO cambio de
     cantidad (id de objeto, antes -> después), así que el id del fósil
     sale solo, sin suponerlo.
  2. ¿En qué ORDEN y con cuánto retraso ocurren las dos cosas (baja el
     fósil / aparece el Pokémon en equipo o cajas)? Define la ventana de
     tiempo de la regla.
  3. ¿Qué otros objetos bajan al mismo tiempo? (p. ej. una Poké Ball al
     capturar), para saber si el id del fósil basta para no confundirlos.

Solo lectura (no escribe memoria). USO, con X o Y cargado:

    python tools/probes/xy/fosil_bolsa_xy.py

Necesitas AL MENOS UN FÓSIL en la bolsa. Con el probe corriendo:
  a) Revive el fósil en el Laboratorio de Fósiles (Pueblo Petroglifo).
  b) Captura un Pokémon salvaje CUALQUIERA pescando o en hierba (así se ve
     cómo baja una Poké Ball y que no se parece al fósil). Mejor en Pueblo
     Petroglifo, el mismo lugar.
  c) Si tienes un segundo fósil, repite (a): se comprueba que cada fósil
     da su propio par.
No uses ni vendas nada más durante la prueba. Ctrl+C termina, imprime el
resumen y guarda tools/probes/xy/salida/fosil_bolsa_xy.json. Pega el
resumen en el chat y adjunta el JSON.
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

OUTPUT_PATH = Path(__file__).resolve().parent / "salida" / "fosil_bolsa_xy.json"

POLL_SECONDS = 0.5
BOX_SCAN_SECONDS = 2.0
SLOT_SIZE = 4
# Segundos a cada lado de un Pokémon nuevo en los que se buscan bajas de la
# bolsa. Es solo para el resumen: la ventana real de la regla sale de lo que
# se mida aquí.
VENTANA_SEGUNDOS = 120.0


def leer_bolsillo(data):
    """{id_objeto: cantidad} del bolsillo (casilleros u16 id + u16 cantidad)."""
    bolsillo = {}

    if not data:
        return bolsillo

    for offset in range(0, len(data) - SLOT_SIZE + 1, SLOT_SIZE):
        item_id, cantidad = struct.unpack_from("<HH", data, offset)

        if item_id and cantidad:
            bolsillo[item_id] = bolsillo.get(item_id, 0) + cantidad

    return bolsillo


def diferencias(anterior, actual):
    """[(id, antes, después)] de los objetos cuya cantidad cambió."""
    cambios = []

    for item_id in sorted(set(anterior) | set(actual)):
        antes = anterior.get(item_id, 0)
        despues = actual.get(item_id, 0)

        if antes != despues:
            cambios.append((item_id, antes, despues))

    return cambios


def correlacionar(eventos, lugares=None, ventana=VENTANA_SEGUNDOS):
    """
    Para cada Pokémon nuevo (opcionalmente solo con Met_Location en
    `lugares`), las bajas de objetos cercanas en el tiempo.

    `eventos`: lista de dicts con "t" y "tipo": "bolsa" (con "id", "antes",
    "despues") o "pokemon" (con "campos"). Devuelve una lista de
    {"pokemon", "bajas": [{"id", "delta", "segundos"}]} donde "segundos"
    es (instante de la baja - instante del Pokémon): negativo = la bolsa
    bajó ANTES de que apareciera el Pokémon.
    """
    resultado = []

    for evento in eventos:
        if evento["tipo"] != "pokemon":
            continue

        campos = evento["campos"]

        if lugares and campos["met_location"] not in lugares:
            continue

        bajas = []

        for otro in eventos:
            if otro["tipo"] != "bolsa" or otro["despues"] >= otro["antes"]:
                continue

            segundos = otro["t"] - evento["t"]

            if abs(segundos) <= ventana:
                bajas.append({
                    "id": otro["id"],
                    "delta": otro["despues"] - otro["antes"],
                    "segundos": round(segundos, 1),
                })

        resultado.append({"pokemon": evento, "bajas": bajas})

    return resultado


def resumen(eventos, lugares=None):
    lines = []
    bolsa = [e for e in eventos if e["tipo"] == "bolsa"]
    lines.append(f"Cambios en la bolsa registrados: {len(bolsa)}")

    for e in bolsa:
        lines.append(
            f"  t={e['t']:.1f} objeto {e['id']}: {e['antes']} -> {e['despues']}"
        )

    lines.append("\nPokémon nuevos y bajas de objetos cercanas:")

    pares = correlacionar(eventos, lugares)

    if not pares:
        lines.append("  (ningún Pokémon nuevo)")

    for par in pares:
        c = par["pokemon"]["campos"]
        lines.append(
            f"  esp {c['especie']} apodo={c['apodo']!r} met={c['met_location']} "
            f"nv={c['nivel_encuentro']} t={par['pokemon']['t']:.1f}"
        )

        if not par["bajas"]:
            lines.append("    (sin bajas de objetos cerca)")

        for baja in par["bajas"]:
            lines.append(
                f"    objeto {baja['id']} {baja['delta']:+d} a "
                f"{baja['segundos']:+.1f} s"
            )

    return "\n".join(lines)


def guardar(eventos, path=OUTPUT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8", newline="\n") as file:
        json.dump({"eventos": eventos}, file, indent=1, ensure_ascii=False)
        file.write("\n")

    tmp.replace(path)


# ---------------------------------------------------------------------
# E/S (no se prueba sin Azahar)
# ---------------------------------------------------------------------

def main():
    from app.games.registry import get_profile
    from app.readers.azahar_reader import AzaharReader
    from origenes_xy import Seguimiento, escanear_equipo
    from zonas_vs_lugares_xy import scan_party_and_boxes

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--cajas", type=int, default=31)
    parser.add_argument(
        "--lugar", type=int, action="append", default=None,
        help="solo correlaciona Pokémon con este Met_Location (repetible)",
    )
    args = parser.parse_args()

    reader = AzaharReader(process_name=args.process)

    if not reader.connect():
        print("No se pudo conectar con Azahar / no se encontró X o Y.")
        return 1

    if get_profile(reader.process_name) is None:
        print(f"El juego {reader.process_name!r} no tiene perfil.")
        return 1

    inicio = reader._field("items_pocket_start_address")
    casilleros = reader._field("items_pocket_slot_count")

    if inicio is None or casilleros is None:
        print("El perfil no tiene el bolsillo de Objetos confirmado.")
        return 1

    def leer_bolsa():
        data = reader.memory.read(inicio, casilleros * SLOT_SIZE)

        if data is None or len(data) != casilleros * SLOT_SIZE:
            return None

        return leer_bolsillo(data)

    bolsa = leer_bolsa()

    if bolsa is None:
        print("No se pudo leer la bolsa.")
        return 1

    t0 = time.time()
    seg = Seguimiento()
    cajas = scan_party_and_boxes(
        reader, None, boxes=args.cajas, include_last=False
    )
    seg.linea_base({**cajas, **escanear_equipo(reader)}, t0)
    eventos = []
    ultimo_cajas = t0

    print(
        f"Juego: {reader.profile.display_name}. Bolsa: {len(bolsa)} objetos "
        f"distintos. Línea base: {len(seg.conocidos)} Pokémon. Revive el "
        "fósil y captura algo; Ctrl+C para terminar.\n",
        flush=True,
    )

    try:
        while True:
            ahora = time.time()
            t = ahora - t0
            actual = leer_bolsa()

            if actual is not None:
                for item_id, antes, despues in diferencias(bolsa, actual):
                    eventos.append({
                        "t": t, "tipo": "bolsa", "id": item_id,
                        "antes": antes, "despues": despues,
                    })
                    print(
                        time.strftime("[%H:%M:%S]"),
                        f"BOLSA objeto {item_id}: {antes} -> {despues}",
                        flush=True,
                    )

                bolsa = actual

            if ahora - ultimo_cajas >= BOX_SCAN_SECONDS:
                ultimo_cajas = ahora
                cajas = scan_party_and_boxes(
                    reader, None, boxes=args.cajas, include_last=False
                )

            nuevos = seg.alimentar(
                {**cajas, **escanear_equipo(reader)}, ahora,
                zona=reader.read_current_zone_id(),
            )

            for evento in nuevos:
                if evento["tipo"] != "nuevo":
                    continue

                eventos.append({
                    "t": t, "tipo": "pokemon", "campos": evento["campos"],
                    "origen": evento.get("origen"), "zona": evento.get("zona"),
                })
                c = evento["campos"]
                print(
                    time.strftime("[%H:%M:%S]"),
                    f"POKEMON nuevo esp {c['especie']} apodo={c['apodo']!r} "
                    f"met={c['met_location']} nv={c['nivel_encuentro']}",
                    flush=True,
                )

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        pass

    guardar(eventos)
    print(f"\nGuardado en {OUTPUT_PATH}.\n")
    print(resumen(eventos, set(args.lugar) if args.lugar else None))

    return 0


if __name__ == "__main__":
    sys.exit(main())

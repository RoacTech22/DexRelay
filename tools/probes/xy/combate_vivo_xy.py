"""
Bloque 15 (ruta multijuego, 04/10/2026): ver QUÉ pasa en memoria durante
el INICIO de un combate de X/Y y qué lo distingue de verdad (salvaje vs
entrenador).

Por qué: con validar_perfil_xy.py la bandera (+0xFF7) dice "entrenador"
durante la animación inicial de combates salvajes y a veces dice "salvaje"
al inicio de los de entrenador. Este probe muestrea cada 0.1 s (no cada
1 s) y registra, en cada cambio: el valor de las celdas de combate
(0x081FB304 y 0x081FB624), el HP (+0x10), 32 bytes alrededor de la
bandera (base+0xFE0 .. +0xFFF) y la especie del rival. Tú le dices qué
tipo de combate es y al final imprime un resumen por combate.

Segunda versión (04/10/2026, tras la primera corrida): la bandera +0xFF7
resultó ser un byte de FASE del combate (0 -> 128 a los 4-7 s -> 192 al
final en salvajes), no una bandera salvaje/entrenador. La celda tomó dos
valores que separaron los 7 combates anotados. Esta versión añade una
señal INDEPENDIENTE para comprobarlo: si el espacio del "último rival
salvaje" (0x08805614) contiene un Pokémon al empezar el combate, el combate
es salvaje; si está vacío, es de entrenador (así lo viste tú en la prueba).
El resumen final cruza celda, esa señal y tu anotación.

Solo lectura. USO (X o Y cargado en una partida):

    python tools/probes/xy/combate_vivo_xy.py

Mientras corre, escribe y pulsa Enter:
    s   = el combate que empieza (o acaba de empezar) es SALVAJE
    e   = es de ENTRENADOR
    n   = anotación libre (p. ej. "n horda", "n doble", "n huí")
    fin = termina y muestra el resumen (Ctrl+C también)

Anota el tipo en cuanto lo sepas (puedes hacerlo tarde: se asocia al
combate en curso). Haz al menos 6 combates salvajes y 6 de entrenador,
variando: otra ruta o ciudad, con el equipo más grande, capturando alguno
(la captura demuestra que era salvaje), y si puedes un combate doble, una
horda o un gimnasio. Pega TODA la salida.
"""

import argparse
import struct
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CELLS = (0x081FB304, 0x081FB624)
WINDOW_START = 0xFE0
WINDOW_SIZE = 0x20
FLAG_OFFSETS = (0xFEE, 0xFF7)
HP_OFFSET = 0x10


def flag_values(window):
    """{offset: byte} de las dos banderas candidatas dentro de la ventana."""
    if window is None:
        return {offset: None for offset in FLAG_OFFSETS}

    return {
        offset: window[offset - WINDOW_START] for offset in FLAG_OFFSETS
    }


def segment_battles(samples):
    """
    Parte la lista de muestras en combates: un combate empieza cuando la
    celda 1 deja de valer 0 y acaba cuando vuelve a 0. Cada muestra es un
    dict con 't', 'cell1', 'flags' y 'label' (el tipo anotado hasta ese
    momento, o None).
    """
    battles = []
    current = None

    for sample in samples:
        if sample["cell1"]:
            if current is None:
                current = []
                battles.append(current)
            current.append(sample)
        else:
            current = None

    return battles


def battle_label(battle):
    """Última etiqueta anotada dentro del combate (o None)."""
    labels = [s["label"] for s in battle if s["label"]]
    return labels[-1] if labels else None


def distinct_in_order(values):
    """Valores distintos conservando el orden de primera aparición."""
    seen = []

    for value in values:
        if value not in seen:
            seen.append(value)

    return seen


def cell_vs_signal(battles):
    """
    Agrupa los combates por valor de la celda y cuenta, para cada grupo,
    cuántos tenían un Pokémon en el espacio del último rival salvaje al
    empezar ("ultimo") y qué tipos anotó el usuario.
    """
    groups = {}

    for battle in battles:
        cell = battle[0]["cell1"]
        group = groups.setdefault(
            cell, {"battles": 0, "ultimo_at_start": 0, "labels": []}
        )
        group["battles"] += 1
        group["ultimo_at_start"] += 1 if battle[0].get("ultimo") else 0
        group["labels"].append(battle_label(battle) or "?")

    return groups


def format_groups(groups):
    lines = []

    for cell, group in sorted(groups.items()):
        lines.append(
            f"celda 0x{cell:08X}: {group['battles']} combates, "
            f"{group['ultimo_at_start']} con 'ultimo' presente al empezar, "
            f"tipos anotados: {', '.join(group['labels'])}"
        )

    return lines


def summarize_battle(battle):
    t0 = battle[0]["t"]
    cells = distinct_in_order([s["cell1"] for s in battle])
    flag_ff7 = [(s["t"] - t0, s["flags"][0xFF7]) for s in battle]
    first_ff7 = flag_ff7[0][1]
    last_ff7 = flag_ff7[-1][1]
    changes = []
    previous = None

    for elapsed, value in flag_ff7:
        if value != previous:
            changes.append((round(elapsed, 1), value))
            previous = value

    return {
        "label": battle_label(battle),
        "duration": round(battle[-1]["t"] - t0, 1),
        "cells": cells,
        "ff7_first": first_ff7,
        "ff7_last": last_ff7,
        "ff7_changes": changes,
    }


def format_summary(index, summary):
    cells = ", ".join(f"0x{c:08X}" for c in summary["cells"])
    changes = " -> ".join(f"{v}@{t}s" for t, v in summary["ff7_changes"])

    return (
        f"#{index} tipo={summary['label'] or '?'} dur={summary['duration']}s\n"
        f"    celda1: {cells}\n"
        f"    bandera+0xFF7: primera={summary['ff7_first']} "
        f"última={summary['ff7_last']}  cambios: {changes}"
    )


def read_state(memory, species_resolver_fn, last_species_fn, captures_fn):
    cell1_raw = memory.read(CELLS[0], 4)
    cell2_raw = memory.read(CELLS[1], 4)

    if cell1_raw is None or cell2_raw is None:
        return None

    cell1 = struct.unpack("<I", cell1_raw)[0]
    cell2 = struct.unpack("<I", cell2_raw)[0]
    window = None
    hp = None

    if cell1:
        window = memory.read(cell1 + WINDOW_START, WINDOW_SIZE)
        hp_raw = memory.read(cell1 + HP_OFFSET, 2)

        if hp_raw is not None and len(hp_raw) == 2:
            hp = struct.unpack("<H", hp_raw)[0]

        if window is not None and len(window) != WINDOW_SIZE:
            window = None

    return {
        "cell1": cell1,
        "cell2": cell2,
        "hp": hp,
        "window": window,
        "flags": flag_values(window),
        "rival": species_resolver_fn(),
        "ultimo": last_species_fn(),
        "capturas": captures_fn(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()

    from app.readers.azahar_reader import AzaharReader

    reader = AzaharReader(process_name=args.process)

    if not reader.connect() or reader.profile is None:
        print("No se pudo conectar con Azahar / no se encontró X o Y.")
        return 1

    print(f"Juego: {reader.profile.display_name}")
    print("Escribe s / e / n <texto> / fin y pulsa Enter.\n", flush=True)

    state = {"label": None, "stop": False, "notes": []}

    def last_species():
        last = reader.read_last_caught()
        return None if last is None else last.get("species")

    captures_address = reader.profile.memory_map.total_caught_address

    def captures():
        data = reader.memory.read(captures_address, 4)

        if data is None or len(data) != 4:
            return None

        return struct.unpack("<I", data)[0]
    t_start = time.monotonic()

    def read_input():
        for line in sys.stdin:
            word = line.strip()

            if word == "fin":
                state["stop"] = True
                return

            if word in ("s", "e"):
                state["label"] = "SALVAJE" if word == "s" else "ENTRENADOR"
                t = time.monotonic() - t_start
                print(f"{t:8.1f}s  >>> anotado: {state['label']}", flush=True)
            elif word.startswith("n"):
                t = time.monotonic() - t_start
                print(f"{t:8.1f}s  >>> nota: {word[1:].strip()}", flush=True)

    threading.Thread(target=read_input, daemon=True).start()

    samples = []
    previous_key = None
    battle_active = False

    try:
        while not state["stop"]:
            current = read_state(
                reader.memory,
                reader.read_wild_rival_species,
                last_species,
                captures,
            )
            t = time.monotonic() - t_start

            if current is not None:
                if current["cell1"] and not battle_active:
                    state["label"] = None  # etiqueta nueva por combate

                battle_active = bool(current["cell1"])

                samples.append(
                    {
                        "t": t,
                        "cell1": current["cell1"],
                        "flags": current["flags"],
                        "label": state["label"],
                        "ultimo": current["ultimo"],
                    }
                )

                window_hex = (
                    current["window"].hex() if current["window"] else "-"
                )
                key = (
                    current["cell1"],
                    current["cell2"],
                    current["hp"],
                    window_hex,
                    current["rival"],
                    current["ultimo"],
                    current["capturas"],
                )

                if key != previous_key:
                    print(
                        f"{t:8.1f}s  celda1=0x{current['cell1']:08X} "
                        f"celda2=0x{current['cell2']:08X} hp={current['hp']} "
                        f"rival={current['rival']} "
                        f"ultimo={current['ultimo']} "
                        f"capturas={current['capturas']} "
                        f"FF7={current['flags'][0xFF7]} "
                        f"FEE={current['flags'][0xFEE]}\n"
                        f"           ventana[+0xFE0..]={window_hex}",
                        flush=True,
                    )
                    previous_key = key

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass

    print("\n===== RESUMEN POR COMBATE =====")

    battles = segment_battles(samples)

    for index, battle in enumerate(battles, start=1):
        print(format_summary(index, summarize_battle(battle)))

    print("\n===== CELDA vs 'ULTIMO' PRESENTE AL EMPEZAR =====")

    for line in format_groups(cell_vs_signal(battles)):
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())

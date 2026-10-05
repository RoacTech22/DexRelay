"""
Paso 7 del Bloque 14 (ruta multijuego, 04/10/2026): encontrar en RAM de
Pokémon X/Y el PUNTERO DE COMBATE: una dirección fija que contiene la base
de la estructura de batalla (que se reubica en cada combate), y el
desplazamiento dentro de esa estructura donde está el HP actual del
Pokémon que tienes en combate. En ORAS: puntero en 0x083F8658 y HP en
base + 0x404 (combat_pointer_address / combat_hp_offset del perfil).

Método: en cada combate escribes el HP ACTUAL de tu Pokémon activo (lo ves
en pantalla). El probe escanea 32 MB buscando (a) todas las posiciones que
valen ese HP como entero de 16 bits y (b) las celdas de 32 bits que apuntan
a "esa posición menos un desplazamiento" (hasta 0x800). Una celda real
apunta a la estructura de batalla con el MISMO desplazamiento en todos los
combates, así que se intersecta entre combates. Se descartan las celdas de
la tabla del equipo (0x08CE1C60-0x08CE1CF0), que apuntan a tus Pokémon.

Solo lectura. USO (Azahar con X o Y cargado; cada escaneo tarda 1-2
minutos y el combate espera, es por turnos):

    python tools/probes/xy/combate_xy.py

  1. Entra a un combate (salvaje o de entrenador, da igual) y, con el menú
     de comandos en pantalla, escribe:   h HP_ACTUAL
     por ejemplo "h 187". Espera el resultado.
  2. Repite en 3 o 4 combates, SACANDO A PELEAR A POKÉMON DISTINTOS (otro
     puesto del equipo) y con HP distintos; mejor si tienen daño, así los
     números no se repiten. Si usas siempre el mismo líder, la tabla del
     equipo puede colarse como candidato.
  3. Escribe "fin" para ver el resumen. El avance se guarda en
     logs/combate_xy.json y se retoma si cierras el script.

"borrar" quita la última muestra. Pega la salida completa en el chat.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.readers.citra import Citra  # noqa: E402
from buscar_party_xy import (  # noqa: E402
    DEFAULT_SIZE,
    DEFAULT_START,
    read_snapshot,
)
from investigar_trainer_xy import select_process  # noqa: E402

MAX_OFFSET = 0x800
MAX_HP_HITS = 3000
EXCLUDED_CELLS = ((0x08CE1C60, 0x08CE1CF0),)
STATE_FILE = PROJECT_ROOT / "logs" / "combate_xy.json"
MAX_PRINT = 30


def find_hp_positions(snapshot, base_address, hp):
    """Direcciones (pares) donde hay un entero de 16 bits igual a `hp`."""
    needle = hp.to_bytes(2, "little")
    positions = []
    offset = snapshot.find(needle)

    while offset >= 0:
        if offset % 2 == 0:
            positions.append(base_address + offset)

        offset = snapshot.find(needle, offset + 1)

    return positions


def find_hp_pointers(snapshot, base_address, hp, max_offset=MAX_OFFSET,
                     excluded=EXCLUDED_CELLS):
    """Celdas de 32 bits que apuntan a (posición del HP - desplazamiento).

    Devuelve {(celda, desplazamiento): valor_de_la_celda}.
    """
    positions = find_hp_positions(snapshot, base_address, hp)

    if len(positions) > MAX_HP_HITS:
        raise ValueError(
            f"El HP {hp} aparece {len(positions)} veces en memoria: usa una "
            "muestra con un HP menos común."
        )

    targets = {}

    for position in positions:
        for offset in range(0, max_offset + 1, 2):
            targets.setdefault(position - offset, []).append(offset)

    usable = len(snapshot) - len(snapshot) % 4
    cells = memoryview(snapshot[:usable]).cast("I")
    found = {}

    for index, value in enumerate(cells):
        offsets = targets.get(value)

        if offsets is None:
            continue

        cell = base_address + index * 4

        if any(low <= cell < high for low, high in excluded):
            continue

        for offset in offsets:
            found[(cell, offset)] = value

    return found


def intersect_samples(samples):
    """samples: [(hp, {(celda, desplazamiento): valor})] -> claves comunes."""
    common = None

    for _, found in samples:
        keys = set(found)
        common = keys if common is None else common & keys

    return sorted(common or [])


def load_state(path=STATE_FILE):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    return [
        (entry["hp"], {(c, o): v for c, o, v in entry["found"]})
        for entry in raw
    ]


def save_state(samples, path=STATE_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"hp": hp, "found": [[c, o, v] for (c, o), v in found.items()]}
        for hp, found in samples
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def parse_command(text):
    """'h 187' -> ('h', 187); 'fin'/'borrar' -> (palabra, None); si no, None."""
    parts = text.strip().lower().split()

    if len(parts) == 1 and parts[0] in ("fin", "borrar"):
        return parts[0], None

    if len(parts) == 2 and parts[0] == "h" and parts[1].isdigit():
        hp = int(parts[1])

        if 1 <= hp <= 999:
            return "h", hp

    return None


def summarize(samples):
    hps = ", ".join(str(hp) for hp, _ in samples) or "ninguna"
    common = intersect_samples(samples)
    lines = [
        f"COMBATE: {len(samples)} muestras (HP {hps}) -> "
        f"{len(common)} candidatos (celda, desplazamiento)"
    ]

    for cell, offset in common[:MAX_PRINT]:
        values = ", ".join(f"0x{found[(cell, offset)]:08X}" for _, found in samples)
        lines.append(
            f"    celda 0x{cell:08X}  HP en base + 0x{offset:X}  "
            f"(valor de la celda por combate: {values})"
        )

    if len(common) > MAX_PRINT:
        lines.append(f"    ... y {len(common) - MAX_PRINT} más")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=DEFAULT_START)
    parser.add_argument("--size", type=lambda v: int(v, 0), default=DEFAULT_SIZE)
    args = parser.parse_args()

    citra = Citra()

    try:
        selected = select_process(citra, args.process)
    except OSError as error:
        print(f"No se pudo hablar con Azahar: {error!r}")
        return 1

    if selected is None:
        print("No se encontró el proceso de X/Y. Corre listar_procesos_xy.py.")
        return 1

    pid, name = selected
    citra.set_process(pid)
    print(f"Proceso: {name}  (PID {pid})")

    samples = load_state()

    if samples:
        print("Se retoman las muestras guardadas:\n" + summarize(samples))

    print("\nComandos: h HP_ACTUAL (en combate), borrar, fin")

    while True:
        try:
            text = input("> ")
        except EOFError:
            break

        command = parse_command(text)

        if command is None:
            print("No entendí. Ejemplos: 'h 187', 'borrar', 'fin'.")
            continue

        tag, hp = command

        if tag == "fin":
            break

        if tag == "borrar":
            if samples:
                removed = samples.pop()
                save_state(samples)
                print(f"Quitada la muestra con HP {removed[0]}.")

            continue

        snapshot, unreadable = read_snapshot(citra, args.start, args.size)

        if unreadable:
            print(f"(bloques ilegibles: {unreadable}; muestra descartada)")
            continue

        try:
            found = find_hp_pointers(snapshot, args.start, hp)
        except ValueError as error:
            print(error)
            continue

        samples.append((hp, found))
        save_state(samples)
        print(f"  {len(found)} celdas apuntan cerca de un HP {hp}")
        print(summarize(samples))

    print("\n=== RESUMEN ===\n" + summarize(samples))
    print("\nSon candidatos: no se fija nada en el perfil hasta confirmarlos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

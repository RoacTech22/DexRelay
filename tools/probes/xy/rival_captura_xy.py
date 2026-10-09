"""
Paso 6 del Bloque 14 (ruta multijuego, 04/10/2026): encontrar en RAM de
Pokémon X/Y (a) al Pokémon RIVAL de un combate salvaje y (b) al "último
capturado". En ORAS son direcciones fijas con una estructura PK6 completa
(wild_rival_addresses y wild_rival_copy_address del perfil) y alimentan al
Nuzlocke: saber contra qué especie peleaste y qué acabas de capturar.

Método (el mismo de buscar_rival_pk6_absoluto.py de ORAS): escanear 32 MB
buscando estructuras PK6 con checksum válido cuya especie sea la que tú
indicas, en varios combates con especies DISTINTAS, e intersectar. Solo
queda la dirección que coincide SIEMPRE. Se excluyen la party y las cajas
ya confirmadas (no son el rival). Solo lectura.

USO (Azahar con X o Y cargado; cada escaneo tarda 1-2 minutos y el juego
puede seguir en pausa dentro del combate, es por turnos):

    python tools/probes/xy/rival_captura_xy.py

  1. Entra a un combate SALVAJE y, ya dentro (sin capturar ni huir), escribe
     en la terminal:        b NUMERO_POKEDEX_DEL_RIVAL
     por ejemplo "b 661" para Fletchling. Espera el resultado.
  2. Repite en 3 o 4 combates con especies DISTINTAS.
  3. Captura un Pokémon salvaje y, al volver al mapa (sin menús), escribe:
                            c NUMERO_POKEDEX_DEL_CAPTURADO
     Repite con 2 o 3 capturas de especies distintas.
  4. Escribe "fin" para ver el resumen. El avance se guarda en
     logs/rival_captura_xy.json y se retoma si cierras el script.

Si te equivocas en un número, escribe "borrar" para quitar la última muestra.
Pega la salida completa en el chat.
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
    find_pk6_candidates,
    read_snapshot,
)
from investigar_trainer_xy import select_process  # noqa: E402

# Zonas ya confirmadas (paso 3): copia contigua del equipo, cajas y buffer
# del equipo. Un PK6 ahí no es el rival ni "el último capturado".
DEFAULT_EXCLUDED = (
    (0x08C79000, 0x08C7B000),
    (0x08C86000, 0x08CB2000),
    (0x08CE1000, 0x08CE3000),
)
STATE_FILE = PROJECT_ROOT / "logs" / "rival_captura_xy.json"


def addresses_for_species(candidates, species, excluded=DEFAULT_EXCLUDED):
    """Direcciones de `candidates` ([(dirección, datos)]) con esa especie."""
    result = set()

    for address, data in candidates:
        if data["species"] != species:
            continue

        if any(low <= address < high for low, high in excluded):
            continue

        result.add(address)

    return result


def intersect_samples(samples):
    """samples: [(especie, {direcciones})]. Direcciones comunes a todas."""
    common = None

    for _, addresses in samples:
        common = set(addresses) if common is None else common & addresses

    return sorted(common or [])


def load_state(path=STATE_FILE):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"b": [], "c": []}

    return {
        tag: [(entry[0], set(entry[1])) for entry in raw.get(tag, [])]
        for tag in ("b", "c")
    }


def save_state(state, path=STATE_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        tag: [[species, sorted(addresses)] for species, addresses in samples]
        for tag, samples in state.items()
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def parse_command(text):
    """'b 661' -> ('b', 661); 'fin'/'borrar' -> (palabra, None); si no, None."""
    parts = text.strip().lower().split()

    if len(parts) == 1 and parts[0] in ("fin", "borrar"):
        return parts[0], None

    if len(parts) == 2 and parts[0] in ("b", "c") and parts[1].isdigit():
        species = int(parts[1])

        if 1 <= species <= 721:
            return parts[0], species

    return None


def summarize(state):
    lines = []
    titles = {"b": "RIVAL SALVAJE", "c": "ÚLTIMO CAPTURADO"}

    for tag in ("b", "c"):
        samples = state[tag]
        species = ", ".join(str(s) for s, _ in samples) or "ninguna"
        common = intersect_samples(samples)
        lines.append(
            f"{titles[tag]}: {len(samples)} muestras (especies {species}) -> "
            f"{len(common)} direcciones comunes"
        )

        for address in common:
            lines.append(f"    0x{address:08X}")

    both = set(intersect_samples(state["b"])) & set(
        intersect_samples(state["c"])
    )

    if both and state["b"] and state["c"]:
        lines.append(
            "Coinciden en rival y capturado (mismo buffer, como en ORAS): "
            + ", ".join(f"0x{a:08X}" for a in sorted(both))
        )

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

    state = load_state()

    if state["b"] or state["c"]:
        print("Se retoman las muestras guardadas:\n" + summarize(state))

    print("\nComandos: b N (rival en combate), c N (capturado), borrar, fin")

    while True:
        try:
            text = input("> ")
        except EOFError:
            break

        command = parse_command(text)

        if command is None:
            print("No entendí. Ejemplos: 'b 661', 'c 25', 'borrar', 'fin'.")
            continue

        tag, species = command

        if tag == "fin":
            break

        if tag == "borrar":
            last = "b" if len(state["b"]) >= len(state["c"]) else "c"

            if state[last]:
                removed = state[last].pop()
                save_state(state)
                print(f"Quitada la muestra {last} {removed[0]}.")

            continue

        snapshot, unreadable = read_snapshot(citra, args.start, args.size)

        if unreadable:
            print(f"(bloques ilegibles: {unreadable}; muestra descartada)")
            continue

        candidates = find_pk6_candidates(snapshot, args.start)
        addresses = addresses_for_species(candidates, species)
        state[tag].append((species, addresses))
        save_state(state)

        print(f"  {len(addresses)} PK6 de la especie {species} fuera de party/cajas")
        print(summarize(state))

    print("\n=== RESUMEN ===\n" + summarize(state))
    print("\nSon candidatos: no se fija nada en el perfil hasta confirmarlos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

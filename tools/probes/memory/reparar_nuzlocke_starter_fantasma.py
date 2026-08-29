"""
Reparación de una sola vez para archivos data/nuzlocke.json que ya
quedaron con el bug del inicial fantasma (ver Documento Maestro,
27/08/2026, y test_starter_rename_reconciliation.py) ANTES de que
el fix de NuzlockeService._reconcile_starter_rename() existiera.

El bug: el inicial se registraba dos veces (una vez con el nombre
por defecto durante la pelea contra el Pokémon salvaje que ataca
al profesor, otra vez con el nickname real puesto en el
laboratorio). El fix nuevo previene que esto vuelva a pasar hacia
adelante, pero NO repara datos que ya se guardaron mal -- una vez
que el nickname real ya está en el roster, la reconciliación no
tiene motivo para volver a dispararse.

Qué hace este script:
    1. Busca el encuentro "Inicial" en encounters.
    2. Busca en el roster si hay MÁS de una entrada con la misma
       speciesId que el Inicial registrado (el fantasma + el real).
    3. Si encuentra exactamente ese patrón, se queda con la entrada
       de mayor nivel (o la de caughtAt más reciente si empatan --
       el fantasma siempre se registra primero, con nivel menor o
       igual), borra la otra, y actualiza el encuentro "Inicial"
       para que apunte al nickname que sobrevive.
    4. Si el patrón no coincide exactamente (por ejemplo, hay una
       tercera entrada de la misma especie por una captura legítima
       distinta), NO toca nada y avisa -- mejor no adivinar.

USO:
    python -m tools.probes.memory.reparar_nuzlocke_starter_fantasma \
        --archivo data/nuzlocke.json

Por defecto, sin --archivo, usa data/nuzlocke.json relativo a la
raíz del proyecto. Hace un backup (.bak) antes de escribir.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def reparar(path: Path) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    roster = data.get("roster", [])
    encounters = data.get("encounters", [])

    starter_encounter = next(
        (e for e in encounters if e.get("location") == "Inicial"),
        None,
    )

    if starter_encounter is None:
        print("No hay ningún encuentro 'Inicial' registrado -- nada que reparar.")
        return False

    starter_species_id = None

    for entry in roster:
        if entry.get("nickname") == starter_encounter.get("nickname"):
            starter_species_id = entry.get("speciesId")
            break

    if starter_species_id is None:
        print(
            "El nickname de 'Inicial' no aparece en el roster "
            "-- estado raro, no se toca nada."
        )
        return False

    candidates = [
        entry
        for entry in roster
        if entry.get("speciesId") == starter_species_id
    ]

    if len(candidates) != 2:
        print(
            f"Se esperaban exactamente 2 entradas de la especie del "
            f"Inicial (fantasma + real), se encontraron "
            f"{len(candidates)} -- no coincide con el patrón "
            f"conocido del bug, no se toca nada. Candidatos: "
            f"{[c.get('nickname') for c in candidates]}"
        )
        return False

    # Se queda con la de mayor nivel (el real, nombrado después en
    # el laboratorio, normalmente tiene nivel >= al fantasma). Si
    # empatan, la de caughtAt más reciente.
    survivor, ghost = sorted(
        candidates,
        key=lambda e: (e.get("level", 0), e.get("caughtAt", "")),
        reverse=True,
    )

    if survivor["nickname"] == starter_encounter["nickname"]:
        # El que sobrevive ya es el que "Inicial" tiene registrado
        # -- no hay nada para migrar, solo sobra el fantasma.
        pass

    print(
        f"Fantasma detectado: {ghost['nickname']!r} "
        f"(nivel {ghost.get('level')}) -- se elimina."
    )
    print(
        f"Real: {survivor['nickname']!r} "
        f"(nivel {survivor.get('level')}) -- se conserva."
    )

    roster.remove(ghost)

    starter_encounter["nickname"] = survivor["nickname"]
    starter_encounter["species"] = survivor.get("species")

    backup_path = path.with_suffix(path.suffix + ".bak")
    shutil.copy(path, backup_path)
    print(f"Backup guardado en {backup_path}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"'{path}' reparado. 'Inicial' ahora apunta a {survivor['nickname']!r}.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archivo",
        default="data/nuzlocke.json",
        help="Ruta al nuzlocke.json a reparar (default: data/nuzlocke.json)",
    )
    args = parser.parse_args()

    path = Path(args.archivo)

    if not path.exists():
        print(f"No existe {path}")
        return

    reparar(path)


if __name__ == "__main__":
    main()

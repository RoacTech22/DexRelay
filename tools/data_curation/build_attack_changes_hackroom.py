"""
Fase E -- overrides de tipo/poder/precisión/PP de movimiento para
Rising Ruby / Sinking Sapphire, parseados de AttackChanges.txt
(documento oficial del hack, subido por el usuario).

ALCANCE: tipo, poder, precisión y PP -- los 4 campos que
DexRelay ya muestra en el modal de movimiento (Api.get_move_modal_data(),
ver merge_move_details()). "Effect %"/"Effect" (texto libre sobre
mecánicas de efecto secundario, ej. "High Critical Rate") se ignoran
a propósito -- DexRelay no muestra ningún campo de efecto secundario
hoy, no hay dónde mostrarlos sin agregar una sección nueva.

FORMATO (documento pequeño, 21 movimientos, verificado a mano antes
de escribir el parser):

    Nombre Del Movimiento
    ============================
    Type        Normal >> Grass      (poco común, solo 1 caso: Cut)
    Power       50 >> 70
    Accuracy    95 >> 100
    PP          30 >> 15
    Effect      High Critical Rate   (ignorado, ver arriba)
    Effect %    10 >> 5              (ignorado, ver arriba)

El nombre del movimiento se resuelve a id vía
MoveDescriptionCatalog.get_id_by_name() (mismo dataset ya usado
para las habilidades/movimientos de líderes de gimnasio) -- no
hace falta el bridge para esto, get_id_by_name() solo lee
data/move_descriptions.json en disco.

SALIDA: data/attack_changes_rrss.json, {move_id (str): {"typeKey"?,
"power"?, "accuracy"?, "pp"?}} -- todas las claves opcionales, solo
las que cambiaron para ese movimiento.

USO:
    python -m tools.data_curation.build_attack_changes_hackroom
"""

import json
import re

from app.core import paths
from app.services.move_description import MoveDescriptionCatalog

ATTACK_CHANGES_PATH = paths.path(
    "tools", "data_curation", "hackroom_source", "AttackChanges.txt"
)
OUTPUT_PATH = paths.path("data", "attack_changes_rrss.json")

TYPE_PATTERN = re.compile(r"^Type\s+.+?\s*>>\s*(?P<new>.+?)\s*$")
POWER_PATTERN = re.compile(r"^Power\s+\d+\s*>>\s*(?P<new>\d+)\s*$")
ACCURACY_PATTERN = re.compile(r"^Accuracy\s+\d+\s*>>\s*(?P<new>\d+)\s*$")
PP_PATTERN = re.compile(r"^PP\s+\d+\s*>>\s*(?P<new>\d+)\s*$")


def main():

    with open(ATTACK_CHANGES_PATH, "r", encoding="utf-8") as file:
        lines = [line.rstrip("\r\n") for line in file.readlines()]

    move_description_catalog = MoveDescriptionCatalog()

    changes = {}
    unresolved = []
    current_move_name = None
    current_entry = None

    def close_current():
        if current_move_name and current_entry:
            move_id = move_description_catalog.get_id_by_name(
                current_move_name
            )
            if move_id is None:
                unresolved.append(current_move_name)
            else:
                changes[str(move_id)] = current_entry

    for index, line in enumerate(lines):

        # Nombre de movimiento: línea seguida de una de "======".
        # Más confiable que matchear el nombre por forma de texto
        # solo (evita falsos positivos con líneas del encabezado).
        is_move_header = (
            index + 1 < len(lines)
            and lines[index + 1].startswith("===")
            and line.strip()
            and not line.startswith("|")
            and not line.startswith("o-")
        )

        if is_move_header:
            close_current()
            current_move_name = line.strip()
            current_entry = {}
            continue

        if current_entry is None:
            continue

        type_match = TYPE_PATTERN.match(line)
        if type_match:
            current_entry["typeKey"] = type_match.group("new").strip()
            continue

        power_match = POWER_PATTERN.match(line)
        if power_match:
            current_entry["power"] = int(power_match.group("new"))
            continue

        accuracy_match = ACCURACY_PATTERN.match(line)
        if accuracy_match:
            current_entry["accuracy"] = int(accuracy_match.group("new"))
            continue

        pp_match = PP_PATTERN.match(line)
        if pp_match:
            current_entry["pp"] = int(pp_match.group("new"))
            continue

    close_current()

    if unresolved:
        print(
            f"ADVERTENCIA: {len(unresolved)} movimientos sin "
            f"resolver contra move_descriptions.json: {unresolved}"
        )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(changes, file, ensure_ascii=False, indent=2)

    print(f"Listo: {len(changes)} movimientos escritos en {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()

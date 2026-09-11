"""
Fase E -- overrides de tipo/habilidad/stats base para Rising Ruby /
Sinking Sapphire, parseados de PokemonChanges.txt (documento
oficial del hack, subido por el usuario).

ALCANCE DE ESTA PASADA (a pedido explícito del usuario: "tipos
habilidades y stats"): SOLO estos 3 campos. El documento también
trae moveset de subida de nivel completo, compatibilidad de MT/MO,
EVs otorgados, y ubicación -- eso queda para otra pasada si hace
falta, no se toca acá.

POR QUÉ HACE FALTA UN OVERRIDE: species_details() (Program.cs)
resuelve tipo/habilidad/stats desde las tablas INTERNAS de
PKHeX.Core (info.Type1/Type2/HP/ATK/etc, la PersonalInfo del juego
BASE) -- no tiene forma de saber que el ROM está parcheado.

FORMATO DEL DOCUMENTO (confirmado leyendo bloques reales antes de
escribir el parser, no adivinado):

    #NNN NOMBRE
    =======================
    Location: ...
    Type: Normal/Flying >> Fighting/Flying      (SOLO si cambió)
    Ability 1: Run Away >> Limber **             (SOLO si cambió)
    Ability 2: Effect Spore **                   (SOLO si cambió;
                                                   sin ">>" cuando
                                                   el doc no aclaró
                                                   el valor viejo,
                                                   no importa para
                                                   el override, solo
                                                   se usa el nuevo)
    New TM/HMs: ...                              (ignorado en esta
                                                   pasada)
    EVs: ...                                     (ignorado en esta
                                                   pasada)

    HP          52 >> 65                         (SOLO las líneas
    Attack      65 >> 130                         de stats que
    ...                                            cambiaron, no
    Total       352 >> 475                        las 6 siempre)

    1   Tackle                                   (moveset de nivel,
    ...                                            ignorado en esta
                                                    pasada)

El número de Pokédex del encabezado (#NNN) ES el species_id real
-- no hace falta resolver nombres contra species_cache.json como
con los líderes (ahí el documento solo daba nombres).

Las HABILIDADES se guardan en INGLÉS tal cual el documento (ej.
"Limber") -- se resuelven a español en el momento en api.py, igual
que ya se hace con las habilidades de líderes (mismo
AbilityDescriptionCatalog.get_id_by_name() + AbilityCatalog).

SALIDA: data/pokemon_changes_rrss.json, {species_id (str): {
"type1"?, "type2"?, "ability1"?, "ability2"?, "baseStats"?: {
"hp"?, "attack"?, "defense"?, "spAttack"?, "spDefense"?, "speed"?
}}} -- todas las claves son opcionales, solo aparecen las que
realmente cambiaron para esa especie.

USO:
    python -m tools.data_curation.build_pokemon_changes_hackroom
"""

import json
import re

from app.core import paths

POKEMON_CHANGES_PATH = paths.path(
    "tools", "data_curation", "hackroom_source", "PokemonChanges.txt"
)
OUTPUT_PATH = paths.path("data", "pokemon_changes_rrss.json")

HEADER_PATTERN = re.compile(r"^#(\d+)\s+(.+?)\s*$")

TYPE_PATTERN = re.compile(
    r"^Type:\s*.+?\s*>>\s*(?P<new>.+?)\s*$"
)

ABILITY_1_PATTERN = re.compile(r"^Ability 1:\s*(?P<rest>.+?)\s*$")
ABILITY_2_PATTERN = re.compile(r"^Ability 2:\s*(?P<rest>.+?)\s*$")

STAT_LINE_PATTERN = re.compile(
    r"^(?P<stat>HP|Attack|Defense|Sp\. Attack|Sp\. Defense|Speed)"
    r"\s+\d+\s*>>\s*(?P<new>\d+)\s*$"
)

STAT_NAME_TO_KEY = {
    "HP": "hp",
    "Attack": "attack",
    "Defense": "defense",
    "Sp. Attack": "spAttack",
    "Sp. Defense": "spDefense",
    "Speed": "speed",
}


def clean_ability_name(rest):
    """
    "Run Away >> Limber **" -> "Limber"
    "Adaptability **" -> "Adaptability" (sin ">>", ver docstring)
    """

    # Si hay ">>", nos quedamos con lo que sigue (el valor nuevo).
    if ">>" in rest:
        rest = rest.split(">>")[-1]

    # Sacar asteriscos de legalidad (*/**) y espacios sobrantes.
    return rest.replace("*", "").strip()


def parse_types(new_types_text):
    """
    "Fighting/Flying" o "Bug / Water" (espacios inconsistentes en
    el documento, se normalizan acá) -> ("Fighting", "Flying") o
    ("Bug", None) si es un solo tipo.
    """

    parts = [part.strip() for part in new_types_text.split("/")]

    type1 = parts[0] if parts else None
    type2 = parts[1] if len(parts) > 1 else None

    return type1, type2


def main():

    with open(POKEMON_CHANGES_PATH, "r", encoding="utf-8") as file:
        lines = file.readlines()

    changes = {}
    current_species_id = None
    current_entry = None

    for line in lines:

        line = line.rstrip("\r\n")

        header_match = HEADER_PATTERN.match(line)

        if header_match:
            current_species_id = int(header_match.group(1))
            current_entry = {}
            continue

        if current_species_id is None:
            continue

        type_match = TYPE_PATTERN.match(line)
        if type_match:
            type1, type2 = parse_types(type_match.group("new"))
            current_entry["type1"] = type1
            if type2:
                current_entry["type2"] = type2
            continue

        ability1_match = ABILITY_1_PATTERN.match(line)
        if ability1_match:
            current_entry["ability1"] = clean_ability_name(
                ability1_match.group("rest")
            )
            continue

        ability2_match = ABILITY_2_PATTERN.match(line)
        if ability2_match:
            current_entry["ability2"] = clean_ability_name(
                ability2_match.group("rest")
            )
            continue

        stat_match = STAT_LINE_PATTERN.match(line)
        if stat_match:
            stat_key = STAT_NAME_TO_KEY[stat_match.group("stat")]
            current_entry.setdefault("baseStats", {})[stat_key] = int(
                stat_match.group("new")
            )
            continue

        # Al llegar a la primera línea de moveset (empieza con un
        # número seguido de espacio y un nombre de movimiento) ya
        # terminaron los campos que nos interesan de este bloque --
        # se cierra la entrada acá para no seguir escaneando de más
        # por cada especie (rendimiento, documento de 17578 líneas).
        if re.match(r"^\d+\s+\S", line) and current_entry is not None:
            if current_entry:
                changes[str(current_species_id)] = current_entry
            current_species_id = None
            current_entry = None

    # Por si el archivo termina sin una línea de moveset final que
    # cierre la última especie.
    if current_species_id is not None and current_entry:
        changes[str(current_species_id)] = current_entry

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(changes, file, ensure_ascii=False, indent=2)

    with_type = sum(1 for e in changes.values() if "type1" in e)
    with_ability = sum(
        1 for e in changes.values() if "ability1" in e or "ability2" in e
    )
    with_stats = sum(1 for e in changes.values() if "baseStats" in e)

    print(
        f"Listo: {len(changes)} especies con cambios en "
        f"{OUTPUT_PATH} ({with_type} con tipo, {with_ability} con "
        f"habilidad, {with_stats} con stats)."
    )


if __name__ == "__main__":
    main()

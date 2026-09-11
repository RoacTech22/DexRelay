"""
Fase E (09/09/2026): soporte para el hack Rising Ruby / Sinking
Sapphire (Drayano, base Omega Ruby/Alpha Sapphire). Primer recorte
elegido por el usuario: equipos reales de los 8 líderes de gimnasio.

FUENTE: AreaChanges.txt, uno de los 5-6 documentos de cambios
oficiales del hack (subidos por el usuario, no descargados por
este script -- el link de descarga original del hack está roto).
Cada líder tiene un bloque "Special Battle - <nombre>" con una
tabla Pokemon/Lv/Item/Ability/Moves -- se parsea tal cual, sin
completar ni corregir nada a mano.

Los 8 bloques reales (verificado a mano antes de escribir esto,
un solo Special Battle por líder salvo Wallace que aparece 2 veces
-- se toma la PRIMERA aparición, la batalla de gimnasio real, no la
segunda que es la revancha de después):

    Special Battle - Leader Roxanne
    Special Battle - Leader Brawly
    Special Battle - Wattson
    Special Battle - Flannery
    Special Battle - Norman
    Special Battle - Winona
    Special Battle - Liza & Tate   (el doc los nombra al revés que
                                     el juego base, que dice
                                     "Tate & Liza" -- se normaliza)
    Special Battle - Wallace

order/typeKey/badgeName/gymLocation NO cambian respecto al juego
base (el hack no reubica gimnasios ni cambia insignias) -- se
mantienen iguales a data/gym_leaders.json. Lo que sí es 100% del
hack es el equipo: especie, nivel, objeto, habilidad y los 4
movimientos reales, tal cual salen en el documento.

`speciesId` se resuelve contra data/species_cache.json (ya
construido desde el bridge PKHeX, mismo dataset que usa
ItemCatalog/SpeciesCatalog para el resto de la app) -- si un
nombre de la tabla no matchea ningún species_cache conocido, se
imprime como advertencia y se salta ese Pokémon en vez de
inventarle un id.

`typeKeys` por Pokémon queda vacío a propósito -- el hack SÍ
cambia el tipo de algunas especies (PokemonChanges.txt, todavía sin
curar, es la próxima parte de esta fase), así que poner el tipo
del juego base sería un dato potencialmente incorrecto. Mejor vacío
y honesto que una suposición.

`isAce` se marca en el último miembro de cada equipo, mismo
criterio que ya usa data/gym_leaders.json.

SALIDA: data/gym_leaders_rrss.json, mismo formato exacto que
data/gym_leaders.json (rss = Rising Ruby / Sinking Sapphire) para
que GymLeaderCatalog pueda leer cualquiera de los dos sin cambios
de forma -- solo cambia qué archivo se le pasa.

USO:
    python -m tools.data_curation.build_gym_leaders_hackroom
"""

import json
import re

from app.core import paths

AREA_CHANGES_PATH = paths.path(
    "tools", "data_curation", "hackroom_source", "AreaChanges.txt"
)
SPECIES_CACHE_PATH = paths.path("data", "species_cache.json")
VANILLA_GYM_LEADERS_PATH = paths.path("data", "gym_leaders.json")
OUTPUT_PATH = paths.path("data", "gym_leaders_rrss.json")

# Nombre del bloque "Special Battle - X" en el documento -> nombre
# real del líder tal como lo usa data/gym_leaders.json (para poder
# copiarle order/typeKey/badgeName/gymLocation sin repetirlos a
# mano). Normaliza el único caso donde el doc invierte el nombre
# compuesto (Liza & Tate -> Tate & Liza).
BLOCK_NAME_TO_LEADER_NAME = {
    "Leader Roxanne": "Roxanne",
    "Leader Brawly": "Brawly",
    "Wattson": "Wattson",
    "Flannery": "Flannery",
    "Norman": "Norman",
    "Winona": "Winona",
    "Liza & Tate": "Tate & Liza",
    "Wallace": "Wallace",
}

ROW_PATTERN = re.compile(
    r"^\|\s*(?P<species>[^|]+?)\s*\|\s*(?P<level>\d+)\s*\|"
    r"\s*(?P<item>[^|]+?)\s*\|\s*(?P<ability>[^|]+?)\s*\|"
    r"\s*(?P<moves>[^|]+?)\s*\|\s*$"
)


def load_species_name_to_id():

    with open(SPECIES_CACHE_PATH, "r", encoding="utf-8") as file:
        entries = json.load(file)

    # Último id gana si hay nombres repetidos (no debería pasar
    # para especies base, solo para formas alternativas que caen
    # después en el archivo) -- para gimnasio no hace falta más
    # precisión que esta.
    return {entry["name"]: entry["id"] for entry in entries}


def load_vanilla_leader_fields():

    with open(VANILLA_GYM_LEADERS_PATH, "r", encoding="utf-8") as file:
        raw = json.load(file)

    return {
        leader["name"]: leader
        for leader in raw.get("leaders", [])
    }


def find_special_battle_blocks(lines):
    """
    Devuelve [(nombre_del_bloque, indice_de_la_linea), ...] para
    cada aparición de "Special Battle - X" en el documento, en
    orden. Wallace aparece 2 veces -- el llamador se queda con la
    primera.
    """

    blocks = []
    pattern = re.compile(r"^\|\s*Special Battle - (.+?)\s*\|\s*$")

    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            blocks.append((match.group(1).strip(), index))

    return blocks


def parse_team(lines, start_index):
    """
    A partir de la línea del título "Special Battle - X", busca la
    tabla Pokemon/Lv/Item/Ability/Moves que sigue (después de 3
    líneas de encabezado: separador, encabezado de columnas,
    separador) y devuelve la lista de miembros hasta la línea de
    cierre (una línea de puros guiones/o, sin "|" de datos).
    """

    team = []

    # Saltar: separador, fila de encabezado ("Pokemon | Lv | ..."),
    # separador -- 3 líneas fijas antes de la primera fila de datos
    # real, confirmado a mano contra el documento.
    row_index = start_index + 4

    while row_index < len(lines):

        line = lines[row_index]

        if not line.strip().startswith("|"):
            break

        match = ROW_PATTERN.match(line.rstrip("\r\n"))

        if not match:
            break

        moves = [
            move.strip()
            for move in match.group("moves").split(",")
            if move.strip()
        ]

        team.append({
            "species": match.group("species").strip(),
            "level": int(match.group("level")),
            "item": match.group("item").strip(),
            "ability": match.group("ability").strip(),
            "moves": moves,
        })

        row_index += 1

    return team


def main():

    with open(AREA_CHANGES_PATH, "r", encoding="utf-8") as file:
        lines = file.readlines()

    species_name_to_id = load_species_name_to_id()
    vanilla_fields = load_vanilla_leader_fields()

    blocks = find_special_battle_blocks(lines)

    seen_block_names = set()
    leaders = []
    unresolved_species = []

    for block_name, index in blocks:

        if block_name not in BLOCK_NAME_TO_LEADER_NAME:
            continue

        # Wallace aparece 2 veces -- primera aparición = gimnasio
        # real, se descarta la segunda (revancha).
        if block_name in seen_block_names:
            continue

        seen_block_names.add(block_name)

        leader_name = BLOCK_NAME_TO_LEADER_NAME[block_name]
        vanilla = vanilla_fields.get(leader_name)

        if vanilla is None:
            print(
                f"ADVERTENCIA: '{leader_name}' no está en "
                f"gym_leaders.json vanilla -- salteado."
            )
            continue

        raw_team = parse_team(lines, index)
        team = []

        for position, member in enumerate(raw_team):

            species_id = species_name_to_id.get(member["species"])

            if species_id is None:
                unresolved_species.append(
                    (leader_name, member["species"])
                )
                continue

            team.append({
                "speciesId": species_id,
                "species": member["species"],
                "level": member["level"],
                "typeKeys": [],
                "moves": member["moves"],
                "item": member["item"] if member["item"] != "None" else None,
                "isAce": position == len(raw_team) - 1,
                "ability": member["ability"],
            })

        leaders.append({
            "order": vanilla["order"],
            "name": leader_name,
            "typeKey": vanilla.get("typeKey"),
            "badgeName": vanilla.get("badgeName"),
            "gymLocation": vanilla.get("gymLocation"),
            "team": team,
        })

    leaders.sort(key=lambda leader: leader["order"])

    if unresolved_species:
        print(
            f"ADVERTENCIA: {len(unresolved_species)} especies sin "
            f"resolver contra species_cache.json (revisar nombres "
            f"a mano):"
        )
        for leader_name, species in unresolved_species:
            print(f"  {leader_name}: {species!r}")

    output = {
        "_source": (
            "Rising Ruby / Sinking Sapphire (Drayano), "
            "AreaChanges.txt -- parseado 09/09/2026 por "
            "build_gym_leaders_hackroom.py. typeKeys por Pokémon "
            "vacío a propósito (pendiente: cruzar con "
            "PokemonChanges.txt en la próxima parte de la Fase E)."
        ),
        "leaders": leaders,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(
        f"Listo: {len(leaders)} líderes escritos en {OUTPUT_PATH} "
        f"({sum(len(l['team']) for l in leaders)} Pokémon en total)."
    )


if __name__ == "__main__":
    main()

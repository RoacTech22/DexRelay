"""
Curación de una sola vez: potencia, precisión y categoría
(físico/especial/estado) de todos los movimientos, FIJADOS a como
eran en Generación 6 (Rubí Omega/Zafiro Alfa) -- confirmado el
06/09/2026 que PKHeX.Core NO trae estos datos (ver comentario largo
en HandleMoveDetails(), dotnet/DexRelay.PKHeX/Program.cs), así que
DexRelay necesita su propia fuente.

DECISIÓN (06/09/2026, roadmap sección 6 pregunta 1, alcance
ampliado): dataset propio embebido, NO una API en vivo -- sería la
única dependencia de internet de toda la app.

POR QUÉ "FIJADO A GEN 6" Y NO "VALOR ACTUAL" (corrección real,
06/09/2026, misma sesión): la primera versión de este script usaba
el CSV `moves.csv` de PokéAPI tal cual, que trae el valor ACTUAL
(el más reciente, no uno fijo de Gen 6) -- Nintendo/Game Freak sí
rebalancea movimientos entre generaciones (caso real confirmado:
Recover/Descanso/Roost y el resto de la familia de movimientos de
curación bajaron de 10 a 5 PP recién en Generación 9; en ORAS
siguen siendo 10). Si DexRelay mostrara el valor actual sin más, un
movimiento así mostraría un número que ORAS nunca tuvo.

Solución: PokéAPI expone el historial de cambios por movimiento vía
su endpoint REST (`past_values`, ligado a en qué "version_group" se
originó cada cambio) -- no está en el CSV masivo, así que este
script pide cada movimiento INDIVIDUALMENTE (937 llamadas al momento
de escribir esto) para resolver el valor que corresponde a Gen 6.

Lógica de resolución (verificada contra dos casos reales conocidos
antes de confiar en ella -- ver verify_resolution_logic()): cada
entrada de `past_values` representa el valor que rigió HASTA
(inclusive) la generación de su `version_group`, después de la cual
cambió a otra cosa (el siguiente past_value más nuevo, o el valor
"actual" si no hay ninguno más nuevo). Para Gen 6: se busca, entre
los past_values, el de MENOR generación que sea >= 6 -- si existe,
esa es la respuesta (el cambio a otra cosa todavía no había pasado
en Gen 6). Si ninguno califica (todos los cambios fueron ANTES de
Gen 6, o no hay historial), Gen 6 usa el valor actual.

Este script SÍ necesita internet -- por eso es una herramienta de
curación aparte (mismo espíritu que un probe de investigación de
memoria), no parte de la app en sí. Se corre UNA vez acá, con
internet real, y el resultado (data/move_data.json) queda commiteado
como dataset estático -- la app en producción nunca vuelve a pedir
nada por red para esto.

USO:
    python -m tools.data_curation.build_move_data

Tarda varios minutos (una llamada HTTP por movimiento, con una
pausa chica entre cada una para no golpear la API de golpe). Es
normal. Solo hace falta correrlo una vez.
"""

import csv
import io
import json
import time
import urllib.request

from app.core import paths


MOVES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/moves.csv"
)

MOVE_DAMAGE_CLASSES_CSV_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/move_damage_classes.csv"
)

MOVE_REST_URL_TEMPLATE = "https://pokeapi.co/api/v2/move/{id}/"

OUTPUT_PATH = paths.path("data", "move_data.json")

# Pausa entre pedidos individuales (fair use -- no hay motivo para
# golpear la API más rápido de lo necesario en un script que se
# corre una sola vez).
REQUEST_DELAY_SECONDS = 0.1

# Generación objetivo: Alpha Sapphire / Omega Ruby.
TARGET_GENERATION = 6

# Clave estable en inglés (mismo criterio que TypeKey en el bridge
# PKHeX: nombre fijo, no localizado, para que el FRONTEND traduzca)
# -- se arma dinámicamente desde move_damage_classes.csv (el
# "identifier" de ese CSV, ej. "physical"/"special"/"status"), no
# se asume el ID numérico a mano.
CATEGORY_KEY_BY_IDENTIFIER = {
    "physical": "Physical",
    "special": "Special",
    "status": "Status",
}

# Identifier de version_group -> número de generación. Dato
# estructural público y permanente (las generaciones ya cerradas no
# se renumeran) -- mismo criterio que la tabla de Title IDs de
# pointers.py. No hace falta pedirlo por red: es la misma lista fija
# que cualquier fuente pública sobre las versiones del juego.
VERSION_GROUP_GENERATION = {
    "red-blue": 1,
    "yellow": 1,
    "gold-silver": 2,
    "crystal": 2,
    "ruby-sapphire": 3,
    "emerald": 3,
    "firered-leafgreen": 3,
    "diamond-pearl": 4,
    "platinum": 4,
    "heartgold-soulsilver": 4,
    "black-white": 5,
    "black-2-white-2": 5,
    "x-y": 6,
    "omega-ruby-alpha-sapphire": 6,
    "sun-moon": 7,
    "ultra-sun-ultra-moon": 7,
    "lets-go-pikachu-lets-go-eevee": 7,
    "sword-shield": 8,
    "brilliant-diamond-and-shining-pearl": 8,
    "legends-arceus": 8,
    "scarlet-violet": 9,
}


def fetch_csv_rows(url):
    """
    Descarga un CSV de PokéAPI y devuelve sus filas como lista de
    dicts (usa la primera fila como cabecera, igual que
    csv.DictReader).
    """

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DexRelay-DataCuration/1.0"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        raw_bytes = response.read()

    text = raw_bytes.decode("utf-8")

    reader = csv.DictReader(io.StringIO(text))

    return list(reader)


def fetch_json(url):

    # BUG REAL encontrado en la corrida real (06/09/2026): pokeapi.co
    # está detrás de Cloudflare, que bloquea con 403 Forbidden el
    # User-Agent por defecto de urllib ("Python-urllib/3.x") como
    # filtro básico anti-bot -- no es un límite real de fair use de
    # PokéAPI (la API en sí es pública y sin autenticación). Se
    # soluciona mandando un User-Agent normal, como haría cualquier
    # navegador o herramienta legítima.
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DexRelay-DataCuration/1.0"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        raw_bytes = response.read()

    return json.loads(raw_bytes.decode("utf-8"))


def build_category_key_by_id(damage_class_rows):
    """
    damage_class_id (columna real de moves.csv, confirmado en la
    corrida del 06/09/2026 -- la fuente vieja lo llamaba
    "move_damage_class_id", nombre que ya no existe) -> clave
    estable ("Physical"/"Special"/"Status"). Se arma leyendo el
    "identifier" real de move_damage_classes.csv en vez de asumir
    a mano que 1=status/2=physical/3=special -- mismo criterio de
    siempre (nunca un ID mapeado sin confirmar contra la fuente
    real).
    """

    mapping = {}

    for row in damage_class_rows:
        damage_class_id = row["id"]
        identifier = row["identifier"]

        category_key = CATEGORY_KEY_BY_IDENTIFIER.get(identifier)

        if category_key is None:
            continue

        mapping[damage_class_id] = category_key

    return mapping


def resolve_generation_6_value(current_value, past_values, field_name):
    """
    Devuelve el valor de `field_name` (ej. "power"/"accuracy") que
    regía en Generación 6, a partir del valor actual y el historial
    `past_values` de PokéAPI para un movimiento. Ver la lógica
    completa en el docstring del módulo.
    """

    candidates = []

    for entry in past_values:

        version_group_name = entry["version_group"]["name"]
        generation = VERSION_GROUP_GENERATION.get(version_group_name)

        if generation is None:
            # version_group desconocido (no debería pasar con la
            # tabla de arriba, pero mejor no reventar el script
            # entero por un movimiento raro) -- se ignora esta
            # entrada puntual.
            continue

        # El campo puede venir ausente/null en esta entrada puntual
        # del historial (algunos cambios solo tocaron OTRO campo,
        # ej. cambió el PP pero no la potencia) -- en ese caso esta
        # entrada no aporta nada para ESTE campo en particular.
        value = entry.get(field_name)

        if value is None:
            continue

        candidates.append((generation, value))

    if not candidates:
        return current_value

    # De las entradas con generación >= 6 (el cambio todavía no
    # había pasado en Gen 6), la de generación más CHICA es la más
    # cercana a Gen 6 -- esa es la que regía en ese momento.
    applicable = [
        (generation, value)
        for generation, value in candidates
        if generation >= TARGET_GENERATION
    ]

    if not applicable:
        # Todos los cambios registrados fueron ANTES de Gen 6 --
        # para Gen 6 ya regía el valor actual.
        return current_value

    applicable.sort(key=lambda item: item[0])

    return applicable[0][1]


def verify_resolution_logic():
    """
    Chequeo contra dos casos reales conocidos ANTES de confiar en
    la lógica para las 937 llamadas reales -- mismo criterio de
    siempre (nunca dar por buena una fórmula sin probarla contra un
    caso conocido).

    Caso 1 (Recover): PP bajó de 10 a 5 recién en Generación 9. En
    Gen 6 (ORAS) tenía que seguir siendo 10.
    Caso 2 (Vine Whip): potencia subió a 45 justo al empezar
    Generación 6 (X/Y), y se mantuvo así desde entonces -- en Gen 6
    ya es 45, no el valor viejo de antes.
    """

    recover_past_values = [
        {"pp": 10, "version_group": {"name": "sword-shield"}},
    ]

    recover_pp_gen6 = resolve_generation_6_value(
        current_value=5,
        past_values=recover_past_values,
        field_name="pp",
    )

    assert recover_pp_gen6 == 10, (
        f"Lógica de resolución mal: Recover en Gen 6 debería dar "
        f"10 PP, dio {recover_pp_gen6}."
    )

    vine_whip_past_values = [
        {"power": 35, "version_group": {"name": "black-white"}},
    ]

    vine_whip_power_gen6 = resolve_generation_6_value(
        current_value=45,
        past_values=vine_whip_past_values,
        field_name="power",
    )

    assert vine_whip_power_gen6 == 45, (
        f"Lógica de resolución mal: Vine Whip en Gen 6 debería dar "
        f"45 de potencia, dio {vine_whip_power_gen6}."
    )


def main():
    print("================================")
    print("   CURAR DATOS DE MOVIMIENTOS")
    print("   (fijado a Generación 6 / ORAS)")
    print("================================")
    print()

    print("Verificando la lógica de resolución contra casos conocidos...")
    verify_resolution_logic()
    print("  OK.")
    print()

    print("Descargando move_damage_classes.csv...")
    damage_class_rows = fetch_csv_rows(MOVE_DAMAGE_CLASSES_CSV_URL)

    category_key_by_id = build_category_key_by_id(damage_class_rows)

    print(f"  {len(category_key_by_id)} categorías reconocidas.")
    print()

    print("Descargando moves.csv...")
    move_rows = fetch_csv_rows(MOVES_CSV_URL)

    print(f"  {len(move_rows)} movimientos encontrados en PokéAPI.")
    print()

    if move_rows and "damage_class_id" not in move_rows[0]:
        print(
            "AVISO: la columna 'damage_class_id' no existe "
            "en el CSV real. Columnas disponibles:"
        )
        print(f"  {list(move_rows[0].keys())}")
        return

    print(
        "Pidiendo el detalle de cada movimiento para resolver el "
        "valor real de Gen 6 (una llamada por movimiento -- va a "
        "tardar varios minutos, es esperable)..."
    )
    print()

    moves = {}

    skipped_category = 0
    failed_requests = 0

    total = len(move_rows)

    for index, row in enumerate(move_rows, start=1):

        move_id = row["id"]
        damage_class_id = row["damage_class_id"]

        category_key = category_key_by_id.get(damage_class_id, "")

        if not category_key:
            skipped_category += 1

        # Valores actuales del CSV -- usados como respaldo si el
        # pedido individual falla, y como "current_value" de
        # partida para resolve_generation_6_value().
        csv_power = row["power"]
        csv_accuracy = row["accuracy"]

        current_power = int(csv_power) if csv_power else None
        current_accuracy = int(csv_accuracy) if csv_accuracy else None

        power = current_power
        accuracy = current_accuracy

        try:
            detail = fetch_json(
                MOVE_REST_URL_TEMPLATE.format(id=move_id)
            )

            past_values = detail.get("past_values") or []

            power = resolve_generation_6_value(
                current_power, past_values, "power"
            )
            accuracy = resolve_generation_6_value(
                current_accuracy, past_values, "accuracy"
            )

        except Exception as error:
            # No abortar la corrida entera por un movimiento que
            # falló -- se cuenta y se sigue con el valor actual del
            # CSV como respaldo para ese movimiento puntual (mejor
            # eso que perder los otros 900+ ya resueltos).
            failed_requests += 1
            print(f"  Aviso: falló {row['identifier']} ({error}).")

        moves[move_id] = {
            "power": power,
            "accuracy": accuracy,
            "categoryKey": category_key,
        }

        if index % 50 == 0 or index == total:
            print(f"  ... {index}/{total}")

        time.sleep(REQUEST_DELAY_SECONDS)

    print()

    if skipped_category:
        print(
            f"Aviso: {skipped_category} movimiento(s) sin "
            "categoría reconocida."
        )

    if failed_requests:
        print(
            f"Aviso: {failed_requests} movimiento(s) usaron el "
            "valor ACTUAL como respaldo (falló el pedido "
            "individual) -- revisar la lista de arriba si "
            "importa tener el valor exacto de Gen 6 para esos "
            "casos puntuales."
        )

    print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(moves, file, ensure_ascii=False, indent=2)

    print(f"Guardado en: {OUTPUT_PATH}")
    print(f"Total: {len(moves)} movimientos.")
    print()
    print(
        "Listo -- este archivo queda commiteado como dataset "
        "estático, fijado a Generación 6. La app nunca vuelve a "
        "pedir esto por red."
    )


if __name__ == "__main__":
    main()

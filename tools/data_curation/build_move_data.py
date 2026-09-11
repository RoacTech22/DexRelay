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
de escribir esto) para resolver el valor que corresponde a ORAS.

BUG REAL encontrado y corregido (07/09/2026, reportado por el
usuario tras verificar Rayo/Thunderbolt contra la API real): la
primera versión de esta lógica resolvía por NÚMERO DE GENERACIÓN
(x-y y omega-ruby-alpha-sapphire ambos mapeados a "6"), perdiendo
la granularidad DENTRO de una misma generación. Rayo tiene un
`past_value` marcado específicamente en "x-y" con potencia 95 -- el
cambio a 90 (valor actual, confirmado contra pokeapi.co/api/v2/move/85/
en vivo) pasó ENTRE X/Y y ORAS, dos version_groups de la misma
Generación 6 (Game Freak sí aplicó ajustes de potencia a varios
movimientos especiales -- Rayo, y probablemente otros como
Lanzallamas/Rayo Hielo -- específicamente al lanzar ORAS, no al
lanzar X/Y). Al resolver por "generación 6" en bloque, el algoritmo
viejo devolvía 95 (el valor de X/Y) para ORAS, que es exactamente
lo que ORAS NO tiene.

Corrección: en vez de VERSION_GROUP_GENERATION (número de
generación, demasiado grueso), ahora se usa VERSION_GROUP_ORDER
(posición cronológica exacta de cada version_group, curada a mano
en orden real de lanzamiento -- no reutiliza los IDs numéricos
internos de PokéAPI, que NO respetan orden cronológico real: por
ejemplo Colosseum/XD tienen IDs más altos que Corazón de Oro/Alma
de Plata pese a haber salido varios años antes). El objetivo ya no
es "Generación 6" en general sino el version_group específico
"omega-ruby-alpha-sapphire" -- así se distingue correctamente un
cambio que pasó entre X/Y y ORAS de uno que pasó en cualquier otro
punto.

Lógica de resolución (verificada contra TRES casos reales conocidos
antes de confiar en ella -- ver verify_resolution_logic(), el
tercero agregado tras este bug): cada entrada de `past_values`
representa el valor que rigió HASTA (inclusive) el version_group
indicado, después del cual cambió a otra cosa (el siguiente
past_value más nuevo, o el valor "actual" si no hay ninguno más
nuevo). Para ORAS: se busca, entre los past_values, el de MENOR
orden cronológico que sea >= el de "omega-ruby-alpha-sapphire" -- si
existe, esa es la respuesta (el cambio a otra cosa todavía no había
pasado en ORAS). Si ninguno califica (todos los cambios fueron ANTES
de ORAS, o no hay historial), ORAS usa el valor actual.

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

IMPORTANTE (07/09/2026): si ya corriste este script antes del
07/09/2026 (antes de esta corrección), `data/move_data.json` tiene
el bug de arriba -- hay que VOLVER A CORRERLO para regenerar el
dataset completo con la lógica corregida. No alcanza con parchear
Rayo a mano: cualquier otro movimiento que haya cambiado
específicamente entre X/Y y ORAS tiene el mismo problema.
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

# version_group objetivo exacto -- ya no alcanza con "Generación 6"
# a secas (ver el bug real corregido en el docstring del módulo):
# X/Y y ORAS son dos version_groups DISTINTOS dentro de la misma
# generación, y al menos un movimiento (Rayo/Thunderbolt) cambió de
# potencia específicamente entre uno y otro.
#
# PENDIENTE A FUTURO (07/09/2026, a pedido del usuario -- anotado
# para cuando DexRelay dé soporte también a Pokémon X/Y, no solo
# ORAS): hoy este valor está fijo a "omega-ruby-alpha-sapphire"
# porque DexRelay solo lee memoria de ORAS. Si en algún momento se
# agrega soporte para X/Y, ESTE dataset no sirve tal cual para esa
# versión -- Rayo/Lanzallamas/Rayo Hielo (y probablemente más) YA
# CONFIRMADO que tienen valores distintos entre X/Y (95) y ORAS
# (90), justamente el bug que motivó este archivo. Habría que:
#   1. Parametrizar TARGET_VERSION_GROUP en vez de dejarlo fijo acá.
#   2. Correr build_move_data.py una segunda vez con
#      TARGET_VERSION_GROUP="x-y" para generar un dataset SEPARADO
#      (ej. move_data_xy.json), no pisar move_data.json.
#   3. MoveDataCatalog (app/services/move_data.py) necesitaría
#      elegir qué archivo cargar según la versión de juego conectada
#      (mismo patrón multi-versión que ya usa pointers.py para
#      direcciones de memoria por process_name).
# No se resuelve ahora porque no hay soporte de X/Y todavía en
# ningún otro lado del proyecto (memoria, PKHeX bridge, etc.) --
# hacerlo bien acá solo, sin lo demás, no serviría de nada.
TARGET_VERSION_GROUP = "omega-ruby-alpha-sapphire"

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

# Orden CRONOLÓGICO real de cada version_group (07/09/2026,
# reemplaza a VERSION_GROUP_GENERATION -- ver el bug real corregido
# en el docstring del módulo). El número es solo una posición
# relativa en la secuencia de lanzamiento real -- NO son los IDs
# internos de PokéAPI (esos NO respetan orden cronológico: por
# ejemplo Colosseum/XD tienen IDs más altos que Corazón de Oro/Alma
# de Plata pese a haber salido varios años antes -- confirmado
# comparando los IDs reales que trae el campo "machines" de
# pokeapi.co/api/v2/move/85/ contra las fechas de lanzamiento
# reales de cada juego).
#
# Los pares japoneses de Gen 1 (red-green-japan/blue-japan)
# salieron ANTES que red-blue internacional, pero no importan para
# ningún cambio relevante a Gen 6 -- se dejan fuera de esta tabla a
# propósito (si algún movimiento tuviera un past_value marcado ahí,
# el script lo ignora igual que cualquier version_group desconocido,
# ver resolve_target_value()).
VERSION_GROUP_ORDER = {
    "red-blue": 1,
    "yellow": 2,
    "gold-silver": 3,
    "crystal": 4,
    "ruby-sapphire": 5,
    "colosseum": 6,
    "firered-leafgreen": 7,
    "emerald": 8,
    "xd": 9,
    "diamond-pearl": 10,
    "platinum": 11,
    "heartgold-soulsilver": 12,
    "black-white": 13,
    "black-2-white-2": 14,
    "x-y": 15,
    "omega-ruby-alpha-sapphire": 16,
    "sun-moon": 17,
    "ultra-sun-ultra-moon": 18,
    "lets-go-pikachu-lets-go-eevee": 19,
    "sword-shield": 20,
    "brilliant-diamond-and-shining-pearl": 21,
    "legends-arceus": 22,
    "scarlet-violet": 23,
}

# Orden del version_group objetivo -- se resuelve una sola vez acá
# en vez de buscarlo en cada llamada a resolve_target_value().
TARGET_VERSION_GROUP_ORDER = VERSION_GROUP_ORDER[
    TARGET_VERSION_GROUP
]


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


def resolve_target_value(current_value, past_values, field_name):
    """
    Devuelve el valor de `field_name` (ej. "power"/"accuracy") que
    regía en TARGET_VERSION_GROUP (Omega Ruby/Alpha Sapphire), a
    partir del valor actual y el historial `past_values` de PokéAPI
    para un movimiento. Ver la lógica completa y el bug real que
    corrige (resolver por version_group exacto, no por generación
    en bloque) en el docstring del módulo.
    """

    candidates = []

    for entry in past_values:

        version_group_name = entry["version_group"]["name"]
        order = VERSION_GROUP_ORDER.get(version_group_name)

        if order is None:
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

        candidates.append((order, value))

    if not candidates:
        return current_value

    # De las entradas con orden >= el de ORAS (el cambio todavía no
    # había pasado en ORAS), la de orden más CHICO es la más
    # cercana a ORAS -- esa es la que regía en ese momento.
    applicable = [
        (order, value)
        for order, value in candidates
        if order >= TARGET_VERSION_GROUP_ORDER
    ]

    if not applicable:
        # Todos los cambios registrados fueron ANTES de ORAS -- en
        # ORAS ya regía el valor actual.
        return current_value

    applicable.sort(key=lambda item: item[0])

    return applicable[0][1]


def verify_resolution_logic():
    """
    Chequeo contra TRES casos reales conocidos ANTES de confiar en
    la lógica para las 937 llamadas reales -- mismo criterio de
    siempre (nunca dar por buena una fórmula sin probarla contra un
    caso conocido).

    Caso 1 (Recover): PP bajó de 10 a 5 recién en Generación 9. En
    ORAS tenía que seguir siendo 10.
    Caso 2 (Vine Whip): potencia subió a 45 justo al empezar
    Generación 6 (X/Y), y se mantuvo así desde entonces -- en ORAS
    ya es 45, no el valor viejo de antes.
    Caso 3 (Rayo/Thunderbolt, agregado 07/09/2026 tras el bug real
    encontrado por el usuario): potencia bajó de 95 a 90
    ESPECÍFICAMENTE entre X/Y y ORAS -- el past_value real de
    PokéAPI está marcado en "x-y" (confirmado contra
    pokeapi.co/api/v2/move/85/ en vivo), no en una generación
    completa. En ORAS ya tiene que dar 90 (el valor actual), NO 95
    -- este es exactamente el caso que la versión vieja de esta
    función (por generación) resolvía mal.
    """

    recover_past_values = [
        {"pp": 10, "version_group": {"name": "sword-shield"}},
    ]

    recover_pp_oras = resolve_target_value(
        current_value=5,
        past_values=recover_past_values,
        field_name="pp",
    )

    assert recover_pp_oras == 10, (
        f"Lógica de resolución mal: Recover en ORAS debería dar "
        f"10 PP, dio {recover_pp_oras}."
    )

    vine_whip_past_values = [
        {"power": 35, "version_group": {"name": "black-white"}},
    ]

    vine_whip_power_oras = resolve_target_value(
        current_value=45,
        past_values=vine_whip_past_values,
        field_name="power",
    )

    assert vine_whip_power_oras == 45, (
        f"Lógica de resolución mal: Vine Whip en ORAS debería dar "
        f"45 de potencia, dio {vine_whip_power_oras}."
    )

    thunderbolt_past_values = [
        {
            "accuracy": None,
            "power": 95,
            "pp": None,
            "version_group": {"name": "x-y"},
        },
    ]

    thunderbolt_power_oras = resolve_target_value(
        current_value=90,
        past_values=thunderbolt_past_values,
        field_name="power",
    )

    assert thunderbolt_power_oras == 90, (
        f"Lógica de resolución mal: Rayo en ORAS debería dar 90 "
        f"de potencia (el cambio de 95 a 90 fue ANTES de ORAS, "
        f"entre X/Y y ORAS), dio {thunderbolt_power_oras}."
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
        # partida para resolve_target_value().
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

            power = resolve_target_value(
                current_power, past_values, "power"
            )
            accuracy = resolve_target_value(
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

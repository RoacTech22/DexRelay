"""
Traducción de `methodKey` de evolución (roadmap 06/09/2026, sección
4.2 -- última pieza de datos pendiente del modal "Pokédex" de
detalle de especie) a texto legible en español.

Confirmado (07/09/2026, tools/probes/recolectar_evolution_method_keys.py):
exactamente 33 valores de `methodKey` distintos aparecen entre las
721 especies de Kalos hacia atrás (hasta Gen 6/ORAS inclusive) --
esta tabla cubre EXACTAMENTE esos 33, ni uno más. NO se tradujo el
enum completo `EvolutionType` de PKHeX.Core (que tiene variantes de
generaciones posteriores, ej. formas de Alola/Galar/Paldea, que
ORAS nunca va a mostrar) -- mismo criterio de siempre: traducir
solo lo que el probe confirmó que existe de verdad en el rango que
importa.

LIMITACIÓN CONOCIDA: ya ninguna -- las tres categorías de
`argument` (objeto, movimiento, especie compañera) están resueltas
(07/09/2026, a pedido del usuario: primero "cerrá también con los
nombres/sprite de los ítems", después "sí también lo de
movimientos y especie") vía ItemCatalog/MoveDescriptionCatalog/
SpeciesCatalog respectivamente, todas ya existentes en el
proyecto -- no hizo falta ningún dataset nuevo. Ver
METHOD_KEYS_USING_ITEM_ARGUMENT/METHOD_KEYS_USING_MOVE_ARGUMENT/
METHOD_KEYS_USING_TEAMMATE_ARGUMENT más abajo para saber cuál de
los 33 methodKey usa cuál categoría -- el llamador
(get_species_modal_data() en api.py) las consulta para saber qué
catálogo golpear antes de llamar a describe_evolution(), en vez de
pedirle a los tres catálogos para cada uno de los 33 sin
necesidad.

Los 8 métodos con nivel real (`level > 0` en los datos de PKHeX,
distinto de los que solo usan `argument` como condición sin nivel)
usan `{level}` en la plantilla. El resto no depende del nivel para
la condición en sí (aunque casi todos técnicamente "suben de
nivel" en el sentido de que evolucionan en cualquier level-up
mientras se cumpla la condición, no en un nivel FIJO).
"""


# methodKey -> plantilla de texto en español. Usar {level} donde
# corresponda -- se completa en describe_evolution() de abajo.
EVOLUTION_METHOD_TEMPLATES = {
    "LevelUp": "Sube al nivel {level}",
    "LevelUpATK": (
        "Sube de nivel con Ataque mayor que Defensa "
        "(nivel {level})"
    ),
    "LevelUpAeqD": (
        "Sube de nivel con Ataque igual a Defensa (nivel {level})"
    ),
    "LevelUpDEF": (
        "Sube de nivel con Defensa mayor que Ataque "
        "(nivel {level})"
    ),
    "LevelUpAffection50MoveType": (
        "Sube de nivel con cariño alto y conociendo un movimiento "
        "de un tipo específico"
    ),
    "LevelUpBeauty": "Sube de nivel con Belleza alta",
    "LevelUpCold": "Sube de nivel cerca de la Roca Helada",
    "LevelUpForest": "Sube de nivel cerca de la Roca Musgo",
    "LevelUpElectric": (
        "Sube de nivel en una zona con fuerte carga eléctrica"
    ),
    "LevelUpECgeq5": "Sube de nivel (variante determinada al azar)",
    "LevelUpECl5": "Sube de nivel (variante determinada al azar)",
    "LevelUpFemale": "Sube de nivel siendo hembra (nivel {level})",
    "LevelUpMale": "Sube de nivel siendo macho (nivel {level})",
    "LevelUpFormFemale1": (
        "Sube de nivel siendo hembra (nivel {level}, forma "
        "distinta a la del macho)"
    ),
    "LevelUpFriendship": "Sube de nivel con amistad alta",
    "LevelUpFriendshipMorning": "Sube de nivel con amistad alta, de día",
    "LevelUpFriendshipNight": "Sube de nivel con amistad alta, de noche",
    "LevelUpMorning": "Sube de nivel de día (nivel {level})",
    "LevelUpNight": "Sube de nivel de noche (nivel {level})",
    "LevelUpInverted": (
        "Sube de nivel con la consola boca abajo (nivel {level})"
    ),
    "LevelUpMoveType": (
        "Sube de nivel conociendo un movimiento de un tipo "
        "específico (nivel {level})"
    ),
    "LevelUpKnowMove": "Sube de nivel conociendo {move}",
    "LevelUpWithTeammate": (
        "Sube de nivel con {teammate} en el equipo"
    ),
    "LevelUpHeldItemDay": "Sube de nivel de día llevando {item}",
    "LevelUpHeldItemNight": "Sube de nivel de noche llevando {item}",
    "LevelUpNinjask": "Sube al nivel {level}",
    "LevelUpShedinja": (
        "Aparece al evolucionar Nincada (con una Poké Ball libre "
        "y un espacio libre en el equipo)"
    ),
    "Trade": "Se intercambia",
    "TradeHeldItem": "Se intercambia llevando {item}",
    "TradeShelmetKarrablast": (
        "Se intercambia por la otra especie de este par "
        "(Karrablast/Shelmet)"
    ),
    "UseItem": "Se usa {item}",
    "UseItemMale": "Se usa {item}, siendo macho",
    "UseItemFemale": "Se usa {item}, siendo hembra",
}


# Etiqueta CORTA (2-4 palabras) para el conector visual entre
# etapas en el modal Pokédex (roadmap 4.2, 08/09/2026 -- bug real
# reportado por el usuario: "Azurill evoluciona a Marill por
# amistad no está saliendo eso"). Causa real: el frontend mostraba
# el nivel/objeto/movimiento/compañero en el conector, pero varios
# de los 33 methodKey reales no tienen NINGUNO de esos cuatro (ej.
# amistad, intercambio simple, belleza) -- level=0 en esos casos
# (JS trata 0 como "falso", ver el fix en app.js), así que el
# conector caía a una flecha genérica sin decir nada de la
# condición real. Esta tabla cubre EXACTAMENTE esos casos --
# métodos que YA tienen {level}/{item}/{move}/{teammate} en su
# plantilla no necesitan entrada acá, el frontend prioriza esos
# primero.
EVOLUTION_METHOD_COMPACT_LABELS = {
    "LevelUpAffection50MoveType": "Cariño alto",
    "LevelUpBeauty": "Belleza alta",
    "LevelUpCold": "Roca Helada",
    "LevelUpForest": "Roca Musgo",
    "LevelUpElectric": "Zona eléctrica",
    "LevelUpECgeq5": "Al azar",
    "LevelUpECl5": "Al azar",
    "LevelUpFriendship": "Amistad",
    "LevelUpFriendshipMorning": "Amistad (día)",
    "LevelUpFriendshipNight": "Amistad (noche)",
    "LevelUpShedinja": "Al evolucionar Nincada",
    "Trade": "Intercambio",
    "TradeShelmetKarrablast": "Intercambio",
}


# Subconjunto de los 33 methodKey reales cuyo `argument` es un ID
# de OBJETO (no de movimiento ni de especie compañera) -- fuente
# única de verdad para que el llamador (get_species_modal_data() en
# api.py) sepa cuándo vale la pena resolver el nombre vía
# ItemCatalog antes de llamar a describe_evolution(), en vez de
# hacerlo para los 33 sin necesidad.
METHOD_KEYS_USING_ITEM_ARGUMENT = {
    "UseItem",
    "UseItemMale",
    "UseItemFemale",
    "TradeHeldItem",
    "LevelUpHeldItemDay",
    "LevelUpHeldItemNight",
}


# methodKey cuyo `argument` es un id de MOVIMIENTO (distinto de
# los de objeto de arriba) -- hoy solo LevelUpKnowMove (ej.
# Lickilicky necesita conocer Rollout).
METHOD_KEYS_USING_MOVE_ARGUMENT = {
    "LevelUpKnowMove",
}

# methodKey cuyo `argument` es un id de ESPECIE compañera -- hoy
# solo LevelUpWithTeammate (ej. Mantyke necesita a Remoraid en el
# equipo).
METHOD_KEYS_USING_TEAMMATE_ARGUMENT = {
    "LevelUpWithTeammate",
}


def describe_evolution(
    method_key,
    level=None,
    argument=None,
    item_name=None,
    move_name=None,
    teammate_name=None,
):
    """
    Devuelve el texto en español para un método de evolución dado
    (methodKey/level/argument, tal como los devuelve
    species_details() del bridge). Si el methodKey no está en la
    tabla (no debería pasar dentro de especies 1-721, ver docstring
    del módulo), devuelve el methodKey crudo entre corchetes en vez
    de fallar o inventar un texto -- señal visible de que hace
    falta agregar ese caso a la tabla.

    `item_name`/`move_name`/`teammate_name` (07/09/2026, a pedido
    del usuario: "sí también lo de movimientos y especie") -- mismo
    criterio para los tres: si no se pudo resolver (bridge caído,
    o el llamador no lo necesitaba para este methodKey puntual), se
    usa un texto genérico ("un objeto"/"un movimiento
    específico"/"un compañero específico") en vez de dejar un
    placeholder crudo sin reemplazar o inventar un nombre.
    """

    template = EVOLUTION_METHOD_TEMPLATES.get(method_key)

    if template is None:
        return f"[{method_key}]"

    return template.format(
        level=level,
        item=item_name or "un objeto",
        move=move_name or "un movimiento específico",
        teammate=teammate_name or "un compañero específico",
    )

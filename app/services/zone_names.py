from __future__ import annotations

# ============================================================
# TABLA ID DE ZONA -> NOMBRE
# ============================================================
#
# Usada por la detección automática del estado "perdido" del
# Nuzlocke Tracker (27/08/2026, ver
# DexRelay_Contexto_Deteccion_Perdido.md): cuando el primer
# combate salvaje en una ruta termina sin captura, esa ruta se
# registra sola como "perdido" en /api/nuzlocke -> encounters.
#
# IMPORTANTE: esta tabla es NUEVA y está separada a propósito de
# app/services/location_catalog.py / hoenn_locations_es.py (la
# que usa PKHeX para resolver `Met_Location` de una captura real).
# No hay ninguna garantía de que los IDs de CURRENT_ZONE_ID_ADDRESS
# coincidan con los IDs de PKHeX -- son dos sistemas de IDs
# distintos del juego, no mezclar.
#
# Generada (27-28/08/2026) a partir de
# tools/probes/memory/zonas_recolectadas.json -- el catálogo
# nombre-interno -> id recolectado en el juego real con
# mapear_zonas.py/observar_zonas_nuevas.py (116 lugares al cierre
# de esa sesión). Los nombres internos crudos (ej. "CiudadFerrica",
# "Ruta111_b") se convirtieron a este diccionario ID -> nombre
# visible con las siguientes reglas:
#
# 1. Donde el lugar ya tenía traducción verificada en
#    hoenn_locations_es.py (WikiDex/PokéWiki, ver ese archivo), se
#    reusa esa misma traducción -- para que, si algún día las dos
#    tablas terminan describiendo la misma ruta real, el texto
#    coincida.
# 2. Variantes internas de una misma ruta visible (sufijos "_b",
#    "_c", etc. -- sub-zonas/salas contiguas sin pantalla de carga
#    entre medio, ej. las 9 salas de CavernaAbisal) se unifican al
#    mismo nombre visible, tal como se dejó planeado en el
#    Documento Maestro.
# 3. Para el resto (sin traducción verificada todavía), se separan
#    las palabras del nombre interno y se corrigen solo tildes de
#    ortografía española básica y segura (ej. "Pokemon" ->
#    "Pokémon", "Meteorologico" -> "Meteorológico") -- NO se
#    inventa ninguna traducción/nombre de lugar que no estuviera
#    ya en el nombre interno recolectado en el juego real (regla
#    #12: no adivinar).
#
# Sigue incompleta a propósito: cualquier ID no listado acá (fuera
# de los 116 ya recolectados) cae al placeholder "Zona {id}" en
# resolve_zone_name(), en vez de fallar -- esto es un sistema de
# IDs completamente distinto del de hoenn_locations_es.py (ver
# nota arriba), así que no tiene relación con las traducciones de
# Met_Location ya completadas ahí el 09/09/2026 (92 de 93). Acá se
# completa con tools/probes/memory/mapear_zonas.py (modo dirigido)
# u observar_zonas_nuevas.py (modo pasivo), a medida que aparezcan
# zonas nuevas todavía no recolectadas.
ZONE_ID_TO_NAME: dict[int, str] = {
    6: "Villa Raíz",
    7: "Pueblo Escaso",
    8: "Pueblo Azuliza",
    9: "Pueblo Lavacalda",
    10: "Pueblo Pardal",
    11: "Pueblo Verdegal",
    12: "Pueblo Oromar",
    13: "Ciudad Petalia",
    14: "Ciudad Portual",
    15: "Ciudad Malvalona",
    16: "Ciudad Férrica",
    17: "Ciudad Arborada",
    18: "Ciudad Calagua",
    19: "Ciudad Algaria",
    20: "Arrecípolis",
    21: "Ciudad Colosalia",
    22: "Liga Pokémon Exterior",
    23: "Ruta 101",
    24: "Ruta 102",
    25: "Ruta 103",
    26: "Ruta 104",
    27: "Ruta 104",
    28: "Ruta 105",
    29: "Ruta 106",
    30: "Ruta 107",
    31: "Ruta 108",
    32: "Ruta 109",
    33: "Ruta 110",
    34: "Ruta 110",
    35: "Ruta 111",
    36: "Ruta 111",
    37: "Ruta 111",
    38: "Ruta 112",
    39: "Ruta 112",
    40: "Ruta 113",
    41: "Ruta 114",
    42: "Ruta 115",
    43: "Ruta 116",
    44: "Ruta 117",
    45: "Ruta 118",
    46: "Ruta 119",
    47: "Ruta 119",
    48: "Ruta 120",
    49: "Ruta 120",
    50: "Ruta 121",
    51: "Ruta 122",
    52: "Ruta 123",
    53: "Ruta 124",
    54: "Ruta 125",
    55: "Ruta 126",
    56: "Ruta 127",
    57: "Ruta 128",
    58: "Ruta 129",
    59: "Ruta 130",
    60: "Ruta 131",
    61: "Ruta 132",
    62: "Ruta 133",
    63: "Ruta 134",
    66: "Ruta 126 Buceo",
    67: "Ruta 127 Buceo",
    68: "Ruta 128 Buceo",
    71: "Cascada Meteoro",
    75: "Túnel Fervegal",
    76: "Arrecípolis Buceo",
    78: "Cueva Granito",
    81: "Centro Espacial Algaria",
    82: "Bosque Petalia",
    83: "Monte Cenizo",
    84: "Desfiladero",
    85: "Senda Ígnea",
    86: "Monte Pírico",
    87: "Monte Pírico",
    88: "Monte Pírico",
    89: "Monte Pírico",
    90: "Monte Pírico Exterior",
    91: "Monte Pírico Exterior",
    92: "Guarida Aqua Magma",
    93: "Guarida Aqua Magma",
    98: "Caverna Abisal",
    99: "Caverna Abisal",
    100: "Caverna Abisal",
    101: "Caverna Abisal",
    102: "Caverna Abisal",
    104: "Caverna Abisal",
    105: "Caverna Abisal",
    106: "Caverna Abisal",
    107: "Caverna Abisal",
    108: "Liga Pokémon",
    110: "Caverna Abisal Kyogre Groudon",
    112: "Cueva Ancestral",
    113: "Cueva Ancestral",
    114: "Carretera Bici",
    123: "Calle Victoria",
    124: "Calle Victoria",
    125: "Calle Victoria",
    126: "Calle Victoria",
    127: "Calle Victoria",
    128: "Cueva Cardumen",
    139: "Malvalanova",
    145: "Malvamar",
    146: "Malvamar",
    147: "Malvamar",
    148: "Malvamar",
    154: "Malvamar",
    155: "Malvamar",
    164: "Gruta Solar",
    184: "Gimnasio Malvalona",
    189: "Ciudad Malvalona",
    190: "Ciudad Malvalona",
    191: "Ciudad Malvalona",
    198: "Arrecípolis",
    219: "Zona Safari",
    220: "Zona Safari",
    221: "Zona Safari",
    222: "Zona Safari",
    228: "Centro Pokémon Escaso",
}


def resolve_zone_name(zone_id: int | None) -> str | None:
    """
    Devuelve el nombre de la zona para `zone_id`, o un placeholder
    "Zona {id}" si todavía no está mapeada en ZONE_ID_TO_NAME.

    Devuelve None solo si `zone_id` es None (lectura de memoria
    fallida) -- ese caso no debe registrar nada, a diferencia de un
    ID válido pero no mapeado, que sí debe poder registrarse (con
    el placeholder) para no perder el evento.
    """

    if zone_id is None:
        return None

    return ZONE_ID_TO_NAME.get(
        zone_id,
        f"Zona {zone_id}",
    )

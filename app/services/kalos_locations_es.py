"""
Nombres de ubicaciones de Kalos (Pokémon X/Y) por ID de PKHeX.

P1 de la guía de paridad X/Y (05/10/2026). PKHeX ya devuelve estos
nombres en español (volcado real del bridge con X, Y y AS el
05/10/2026: las tres listas traen los mismos 82 IDs de Kalos con los
mismos textos, ver tools/probes/xy/volcar_ubicaciones_xy.py), así que
no se traduce nada a mano: solo se QUITA el aclaratorio entre
paréntesis que PKHeX agrega a rutas y algunos lugares ("Ruta 1
(Sendero Boceto)" -> "Ruta 1", "Liga Pokémon (X/Y)" -> "Liga Pokémon"),
para que el panel muestre el nombre corto que usa el juego en el mapa
y quede como las rutas de Hoenn ("Ruta 101"). La línea comentada de
cada entrada con aclaratorio conserva el texto crudo de PKHeX.

Se usa en DOS lugares a la vez, igual que hoenn_locations_es.py:
LocationCatalog (la lista precargada) y LocationResolver (el lugar de
encuentro de una captura real), para que el nombre de la fila y el de
la captura coincidan siempre.

IDs que no están en esta tabla (transferencias 30000+, eventos
40000+, regalos 60000+, cualquier ID nuevo) devuelven el texto crudo
de PKHeX, sin tocar.
"""

KALOS_LOCATION_NAMES_ES = {
    2: "Lugar misterioso",
    6: "Pueblo Boceto",
    8: "Ruta 1",  # Ruta 1 (Sendero Boceto)
    10: "Pueblo Acuarela",
    12: "Ruta 2",  # Ruta 2 (Vía del Avance)
    14: "Bosque de Novarte",
    16: "Ruta 3",  # Ruta 3 (Senda Despejada)
    18: "Ciudad Novarte",
    20: "Ruta 4",  # Ruta 4 (Senda del Parterre)
    22: "Ciudad Luminalia",
    24: "Torre Prisma",
    26: "Laboratorios Lysson",
    28: "Ruta 5",  # Ruta 5 (Vía Repecho)
    30: "Pueblo Vánitas",
    32: "Castillo Caduco",
    34: "Ruta 6",  # Ruta 6 (Alameda del Palacio)
    36: "Palacio Cénit",
    38: "Ruta 7",  # Ruta 7 (Paseo de la Ribera)
    40: "Ciudad Relieve",
    42: "Ruta 8",  # Ruta 8 (Muralla Costera)
    44: "Pueblo Petroglifo",
    46: "Ruta 9",  # Ruta 9 (Paso de Rhyhorn)
    48: "Bastión Batalla",
    50: "Ruta 10",  # Ruta 10 (Camino Menhires)
    52: "Pueblo Crómlech",
    54: "Ruta 11",  # Ruta 11 (Senda Reflejos)
    56: "Cueva Reflejos",
    58: "Ciudad Yantra",
    60: "Torre Maestra",
    62: "Ruta 12",  # Ruta 12 (Vereda del Heno)
    64: "Ciudad Témpera",
    66: "Ruta 13",  # Ruta 13 (Páramo de Luminalia)
    68: "Ruta 14",  # Ruta 14 (Arboleda Romantis)
    70: "Ciudad Romantis",
    72: "Fábrica Poké Balls",
    74: "Ruta 15",  # Ruta 15 (Sendero Hojarasca)
    76: "Pueblo Fresco",
    78: "Ruta 16",  # Ruta 16 (Senda Melancolía)
    82: "Gruta Helada",
    84: "Ruta 17",  # Ruta 17 (Sendero Mamoswine)
    86: "Ciudad Fluxus",
    88: "Ruta 18",  # Ruta 18 (Senda Valle Angosto)
    90: "Pueblo Mosaico",
    92: "Ruta 19",  # Ruta 19 (Senda del Gran Valle)
    94: "Ciudad Fractal",
    96: "Ruta 20",  # Ruta 20 (Bosque Errantes)
    98: "Villa Pokémon",
    100: "Ruta 21",  # Ruta 21 (Vía Ultimia)
    102: "Ruta 22",  # Ruta 22 (Vía Desvío)
    104: "Calle Victoria",  # Calle Victoria (X/Y)
    106: "Liga Pokémon",  # Liga Pokémon (X/Y)
    108: "Ciudad Batik",
    110: "Mansión Batalla",
    112: "Bahía Azul",
    114: "Acceso a Fresco",
    116: "Acceso a Mosaico",
    118: "Acceso a Petroglifo",
    120: "Acceso a Luminalia",
    122: "Acceso a Yantra",
    124: "Acceso a Témpera",
    126: "Acceso a Romantis",
    128: "Acceso a Fluxus",
    130: "Acceso a Fractal",
    132: "Cueva Brillante",
    134: "Gruta Tierraunida",  # Gruta Tierraunida (Escondrijo Zubat)
    136: "Central de Kalos",
    138: "Guarida Team Flare",
    140: "Cueva Desenlace",
    142: "Hotel Desolación",
    144: "Estancia Vacua",
    146: "Cueva Talasia",
    148: "Safari Amistad",
    150: "Sala de las Llamas",
    152: "Sala de la Esclusa",
    154: "Sala del Metal",
    156: "Sala del Draco",
    158: "Sala de la Luz",
    160: "Acceso Liga Pokémon",
    162: "Estación Luminalia",
    164: "Estación Batik",
    166: "Acuario Petroglifo",
    168: "Mazmorra Rara",
}


def translate_location_name(location_id, fallback_name):
    """Nombre mostrado de una ubicación de Kalos; crudo si no está en la tabla."""

    return KALOS_LOCATION_NAMES_ES.get(location_id, fallback_name)

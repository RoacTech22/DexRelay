"""
Catálogo de ubicaciones de Kalos (Pokémon X/Y) -- P1 de la guía de
paridad X/Y (05/10/2026).

Origen de los datos:
- RANGO: volcado real del bridge con X, Y y AS (05/10/2026,
  tools/probes/xy/volcar_ubicaciones_xy.py): X e Y devuelven la MISMA
  lista (270 entradas) y Kalos son 82 IDs pares entre 2 y 168 (faltan
  el 4 y el 80), idénticos a los que trae la lista de AS. Hoenn
  arranca en 170, así que los rangos no se pisan.
- EXCLUSIONES: decisión explícita de Ronald (05/10/2026), mismo criterio
  que las 14 de Hoenn. Solo afecta la lista PRECARGADA del panel: una
  captura real en un ID excluido igual se registra (el panel le crea la
  fila sobre la marcha).
- ORDEN NARRATIVO: borrador armado con Ronald (05/10/2026), corregido por
  él (Ciudad Fluxus = Anistar, gimnasio 7; Ciudad Fractal = Snowbelle,
  gimnasio 8; Pueblo Mosaico = Couriway; Gruta Tierraunida entre Ruta 7
  y Ruta 8; Hotel Desolación tras la Ruta 15; Guarida Team Flare antes
  de la Ruta 20; Ruta 22 justo después de Ciudad Novarte). Confirmado
  por Ronald con una partida real (05/10/2026).
"""

from __future__ import annotations

KALOS_ID_MIN = 2
KALOS_ID_MAX = 168

EXCLUDED_LOCATION_IDS = frozenset({
    # Accesos a ciudades, a la Liga y estaciones: sin encuentros salvajes.
    114,  # Acceso a Fresco
    116,  # Acceso a Mosaico
    118,  # Acceso a Petroglifo
    120,  # Acceso a Luminalia
    122,  # Acceso a Yantra
    124,  # Acceso a Témpera
    126,  # Acceso a Romantis
    128,  # Acceso a Fluxus
    130,  # Acceso a Fractal
    160,  # Acceso Liga Pokémon
    162,  # Estación Luminalia
    164,  # Estación Batik
    # Salas y edificios sin encuentros salvajes normales.
    150,  # Sala de las Llamas
    152,  # Sala de la Esclusa
    154,  # Sala del Metal
    156,  # Sala del Draco
    158,  # Sala de la Luz
    26,   # Laboratorios Lysson
    24,   # Torre Prisma
    60,   # Torre Maestra
    136,  # Central de Kalos
    72,   # Fábrica Poké Balls
    # Post-juego y especiales.
    2,    # Lugar misterioso
    8,    # Ruta 1 (sin Pokémon salvajes; confirmado por Ronald 06/10/2026)
    148,  # Safari Amistad
    168,  # Mazmorra Rara
    48,   # Bastión Batalla
    110,  # Mansión Batalla
    166,  # Acuario Petroglifo
})

STORY_ORDER_IDS = (
    6,    # Pueblo Boceto
    10,   # Pueblo Acuarela
    12,   # Ruta 2
    14,   # Bosque de Novarte
    18,   # Ciudad Novarte
    102,  # Ruta 22 (tras Ciudad Novarte, ajuste de Ronald)
    16,   # Ruta 3
    20,   # Ruta 4
    22,   # Ciudad Luminalia
    28,   # Ruta 5
    30,   # Pueblo Vánitas
    32,   # Castillo Caduco
    34,   # Ruta 6
    36,   # Palacio Cénit
    38,   # Ruta 7
    134,  # Gruta Tierraunida
    40,   # Ciudad Relieve
    42,   # Ruta 8
    44,   # Pueblo Petroglifo
    46,   # Ruta 9
    132,  # Cueva Brillante
    50,   # Ruta 10
    52,   # Pueblo Crómlech
    54,   # Ruta 11
    56,   # Cueva Reflejos
    58,   # Ciudad Yantra
    62,   # Ruta 12
    64,   # Ciudad Témpera
    66,   # Ruta 13
    68,   # Ruta 14
    70,   # Ciudad Romantis
    74,   # Ruta 15
    142,  # Hotel Desolación
    76,   # Pueblo Fresco
    78,   # Ruta 16
    82,   # Gruta Helada
    84,   # Ruta 17
    86,   # Ciudad Fluxus (Anistar, gimnasio 7)
    88,   # Ruta 18
    90,   # Pueblo Mosaico (Couriway)
    92,   # Ruta 19
    94,   # Ciudad Fractal (Snowbelle, gimnasio 8)
    138,  # Guarida Team Flare
    96,   # Ruta 20
    98,   # Villa Pokémon (tiene capturas; Ronald 06/10/2026)
    100,  # Ruta 21
    104,  # Calle Victoria
    106,  # Liga Pokémon
)

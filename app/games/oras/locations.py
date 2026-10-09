"""
Ubicaciones de Hoenn (ORAS) -- movidas desde location_catalog.py en el
Bloque 13 (ruta multijuego). Los valores NO cambiaron.
"""

from __future__ import annotations

# Rango de IDs de ubicaciones de Hoenn (ORAS) confirmado con datos
# reales de /api/locations (24/08/2026): todo lo de Hoenn cae entre
# 170 ("Littleroot Town") y 354 ("Secret Base"), sin excepciones.
# Fuera de ese rango queda todo lo que NO es parte del recorrido:
# Kalos/X-Y (IDs 2-168), eventos y torneos (40000+), transferencias
# entre juegos/regiones (30000+), y regalos especiales (60000+).
HOENN_ID_MIN = 170
HOENN_ID_MAX = 354

# Ubicaciones de Hoenn excluidas a propósito del catálogo
# (29/08/2026, decisión explícita del usuario) -- no son
# relevantes para un Nuzlocke normal: mirage spots de DexNav que
# aparecen al azar (nunca forman parte de un recorrido real),
# las cuevas de los Regis (post-juego, muy raras), y la base
# secreta del propio jugador (no es un lugar de encuentro
# salvaje). Esto SOLO afecta la lista precargada del panel (no
# aparecen como fila esperando captura) -- si por algún motivo
# rarísimo una captura real reportara uno de estos IDs, igual se
# registraría normal (LocationResolver es un módulo aparte, no
# consulta esta exclusión); el panel simplemente le crearía una
# fila nueva sobre la marcha, como con cualquier ubicación no
# precargada.
EXCLUDED_LOCATION_IDS = frozenset({
    276,  # "???" -- ID interno sin uso real, no una ubicación
          # jugable (nombre crudo de PKHeX, nunca se pudo
          # confirmar qué es)
    278,  # Desert Ruins / "Ruinas del Desierto"
    306,  # Island Cave / "Cueva Insular"
    308,  # Ancient Tomb / "Tumba Antigua"
    310,  # Sealed Chamber / "Cámara Sellada"
    334,  # Trackless Forest / "Bosque Virgen"
    336,  # Pathless Plain / "Llanura Sinnombre"
    338,  # Nameless Cavern / "Cueva Ignota"
    340,  # Fabled Cave / "Cueva Incierta"
    342,  # Gnarled Den / "Boquete Irregular"
    344,  # Crescent Isle / "Isla Creciente"
    354,  # Secret Base / "Base Secreta"
    350,  # Secret Shore / "Costa Secreta"
    352,  # Secret Meadow / "Prado Secreto"
})

# Actualización (09/09/2026): las 13 de acá abajo (todas menos 276)
# ya tienen traducción real en hoenn_locations_es.py -- esta lista
# sigue existiendo igual (sigue siendo una decisión de UX sobre qué
# precargar en el panel, no sobre qué traducir), pero ya no hay que
# leerla como "sin traducción" -- eso quedó resuelto.

# Orden narrativo aproximado (progresión de historia de ORAS), por
# ID -- no por nombre, para que funcione sin importar en qué idioma
# termine devolviendo el texto PKHeX. Lo que no está en este mapa
# (áreas post-juego/DexNav: mirages, cuevas secretas, etc.) se
# agrega al final, ordenado por ID, para no perder ninguna
# ubicación real aunque no tenga un lugar fijo asignado acá.
STORY_ORDER_IDS = (
    170,  # Littleroot Town
    204,  # Route 101
    172,  # Oldale Town
    206,  # Route 102
    208,  # Route 103
    184,  # Petalburg City
    210,  # Route 104
    282,  # Petalburg Woods
    190,  # Rustboro City
    234,  # Route 116
    274,  # Rusturf Tunnel
    212,  # Route 105
    174,  # Dewford Town
    280,  # Granite Cave
    214,  # Route 106
    216,  # Route 107
    218,  # Route 108
    220,  # Route 109
    186,  # Slateport City
    222,  # Route 110
    224,  # Route 111
    226,  # Route 112
    284,  # Mt. Chimney
    286,  # Jagged Pass
    178,  # Fallarbor Town
    228,  # Route 113
    230,  # Route 114
    272,  # Meteor Falls
    232,  # Route 115
    176,  # Lavaridge Town
    288,  # Fiery Path
    188,  # Mauville City
    236,  # Route 117
    180,  # Verdanturf Town
    302,  # New Mauville
    238,  # Route 118
    240,  # Route 119
    192,  # Fortree City
    242,  # Route 120
    244,  # Route 121
    324,  # Safari Zone
    246,  # Route 122
    290,  # Mt. Pyre
    248,  # Route 123
    194,  # Lilycove City
    292,  # Team Aqua Hideout
    314,  # Team Magma Hideout
    250,  # Route 124
    304,  # Sea Mauville
    252,  # Route 125
    254,  # Route 126
    256,  # Route 127
    258,  # Route 128
    294,  # Seafloor Cavern
    196,  # Mossdeep City
    260,  # Route 129
    262,  # Route 130
    264,  # Route 131
    182,  # Pacifidlog Town
    266,  # Route 132
    268,  # Route 133
    270,  # Route 134
    198,  # Sootopolis City
    296,  # Cave of Origin
    300,  # Shoal Cave
    316,  # Sky Pillar
    200,  # Ever Grande City
    202,  # Pokémon League (OR/AS)
    298,  # Victory Road (OR/AS)
)

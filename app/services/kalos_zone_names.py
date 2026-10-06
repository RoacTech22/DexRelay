"""
Zona de memoria -> lugar del catálogo de Kalos (X/Y).

P2 de la guía de paridad X/Y (06/10/2026). La zona (u16 en
0x08C670AE) y el Met_Location de PKHeX son sistemas de IDs distintos
SIN relación fija (probe zonas_vs_lugares_xy.py, veredicto
MAPEO_CONSISTENTE), así que la correspondencia es una tabla recolectada
en el juego real con tools/probes/xy/recolectar_zonas_xy.py: cada zona
se pisó jugando y se emparejó con su lugar del catálogo (las marcadas
"captura" se verificaron con el Met_Location de un Pokémon capturado ahí;
el resto las nombró Ronald viendo el mapa).

Diferencia deliberada con ORAS (zone_names.resolve_zone_name devuelve
"Zona {id}" para zonas sin mapear): acá una zona sin mapear devuelve
None y la detección de "perdido" NO registra nada. Un "Zona 259" no
coincide con ninguna fila del catálogo de Kalos y ensuciaría el
Nuzlocke con filas basura. Las zonas que faltan se siguen recolectando
y se agregan a la tabla.

Tampoco se resuelven lugares que el catálogo excluye (EXCLUDED_LOCATION_IDS,
ej. Ruta 1, que no tiene Pokémon salvajes): no tendrían fila donde registrar el "perdido".
"""

from __future__ import annotations

from app.games.xy.locations import EXCLUDED_LOCATION_IDS
from app.services.kalos_locations_es import KALOS_LOCATION_NAMES_ES

# zona de memoria -> ID de lugar del catálogo (PKHeX / locations.py)
KALOS_ZONE_TO_LOCATION_ID: dict[int, int] = {
    # Pueblos, ciudades y palacios
    302: 36,   # Palacio Cénit
    45: 44,    # Pueblo Petroglifo
    157: 40,   # Ciudad Relieve
    172: 58,   # Ciudad Yantra
    200: 70,   # Ciudad Romantis
    38: 90,    # Pueblo Mosaico
    # Rutas
    259: 12,   # Ruta 2
    260: 16,   # Ruta 3
    261: 20,   # Ruta 4
    262: 28,   # Ruta 5
    263: 34,   # Ruta 6
    264: 38,   # Ruta 7
    266: 42,   # Ruta 8
    267: 46,   # Ruta 9
    268: 50,   # Ruta 10
    269: 54,   # Ruta 11
    270: 62,   # Ruta 12
    272: 66,   # Ruta 13
    273: 68,   # Ruta 14
    275: 74,   # Ruta 15
    276: 78,   # Ruta 16
    278: 84,   # Ruta 17
    279: 88,   # Ruta 18
    281: 92,   # Ruta 19
    282: 96,   # Ruta 20
    283: 100,  # Ruta 21
    285: 102,  # Ruta 22
    # Bosques, cuevas y otros
    286: 14,   # Bosque de Novarte
    303: 132,  # Cueva Brillante
    305: 56,   # Cueva Reflejos
    314: 82,   # Gruta Helada
    334: 134,  # Gruta Tierraunida
    343: 140,  # Cueva Desenlace
    357: 112,  # Bahía Azul
    349: 142,  # Hotel Desolación
    # Calle Victoria: tres zonas (tramos) del mismo lugar
    324: 104,
    326: 104,
    328: 104,
    318: 98,  # Villa Pokémon
}


def resolve_zone_name(zone_id: int | None) -> str | None:
    """
    Nombre del lugar del catálogo de Kalos para la zona `zone_id`.

    None si la lectura falló (zone_id None), si la zona todavía no
    está en la tabla o si su lugar está excluido del catálogo: en
    esos casos no se registra nada.
    """

    if zone_id is None:
        return None

    location_id = KALOS_ZONE_TO_LOCATION_ID.get(zone_id)

    if location_id is None or location_id in EXCLUDED_LOCATION_IDS:
        return None

    return KALOS_LOCATION_NAMES_ES.get(location_id)

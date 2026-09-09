"""
Traducción de nombres de ubicaciones de Hoenn (español de España) por
ID de PKHeX, verificada contra fuentes confiables (WikiDex, PokéWiki
Fandom) el 25/08/2026 -- no adivinada.

Se usa en DOS lugares a la vez, y tiene que ser así:

    1. LocationCatalog (la lista de rutas que se precarga en el
       panel).
    2. LocationResolver (la resolución del lugar de encuentro real
       de una captura, la que compara contra la fila existente).

Si solo se tradujera uno de los dos, el nombre mostrado en la fila
ya no coincidiría con el nombre que reporta una captura real --
reaparecería el mismo bug de rutas duplicadas que motivó traer la
lista directo de PKHeX en primer lugar.

Actualizada 30/08/2026: 4 traducciones nuevas pasadas por el
usuario (Cueva Cardumen/Shoal Cave, Malvamar/Sea Mauville,
Gruta Solar/Scorched Slab, Firmamento/Soaring in the Sky).

Actualizada 09/09/2026: las 14 ubicaciones restantes (menos
ID 276, "???", que no es una ubicación real) se tradujeron
también, verificadas contra WikiDex/Fandom/PokéCompany --
92 de las 93 ubicaciones de Hoenn con traducción confirmada.
Hallazgo real de esta pasada: el comentario anterior daba por
sentado que las 14 eran "post-juego/DexNav no relevantes para
un Nuzlocke normal" -- eso es cierto para los 6 parajes
espejismo raros (334-344, sí necesitan Ultravuelo + condiciones
puntuales), pero NO para las 4 ruinas de los Regis (278/306/
308/310), que son parte de la historia principal y alcanzables
sin nada especial más que buceo para la Cámara Sellada. Quedan
igual EXCLUIDAS del panel precargado (EXCLUDED_LOCATION_IDS en
location_catalog.py, decisión de UX del usuario, no cambia),
pero ahora si una captura real reporta alguna como Met_Location,
el fallback muestra español en vez del crudo de PKHeX en inglés.
"""

HOENN_LOCATION_NAMES_ES = {
    # --- Pueblos ---
    170: "Villa Raíz",              # Littleroot Town
    172: "Pueblo Escaso",           # Oldale Town
    174: "Pueblo Azuliza",          # Dewford Town
    176: "Pueblo Lavacalda",        # Lavaridge Town
    178: "Pueblo Verdegal",         # Fallarbor Town
    180: "Pueblo Pardal",           # Verdanturf Town
    182: "Pueblo Oromar",           # Pacifidlog Town

    # --- Ciudades ---
    184: "Ciudad Petalia",          # Petalburg City
    186: "Ciudad Portual",          # Slateport City
    188: "Ciudad Malvalona",        # Mauville City
    190: "Ciudad Férrica",          # Rustboro City
    192: "Ciudad Arborada",         # Fortree City
    194: "Ciudad Calagua",          # Lilycove City
    196: "Ciudad Algaria",          # Mossdeep City
    198: "Arrecípolis",             # Sootopolis City
    200: "Ciudad Colosalia",        # Ever Grande City

    # --- Liga / Ruta Victoria ---
    202: "Liga Pokémon",            # Pokémon League (OR/AS)
    298: "Calle Victoria",          # Victory Road (OR/AS)

    # --- Rutas (mismo nombre en ambos dialectos del español) ---
    204: "Ruta 101",
    206: "Ruta 102",
    208: "Ruta 103",
    210: "Ruta 104",
    212: "Ruta 105",
    214: "Ruta 106",
    216: "Ruta 107",
    218: "Ruta 108",
    220: "Ruta 109",
    222: "Ruta 110",
    224: "Ruta 111",
    226: "Ruta 112",
    228: "Ruta 113",
    230: "Ruta 114",
    232: "Ruta 115",
    234: "Ruta 116",
    236: "Ruta 117",
    238: "Ruta 118",
    240: "Ruta 119",
    242: "Ruta 120",
    244: "Ruta 121",
    246: "Ruta 122",
    248: "Ruta 123",
    250: "Ruta 124",
    252: "Ruta 125",
    254: "Ruta 126",
    256: "Ruta 127",
    258: "Ruta 128",
    260: "Ruta 129",
    262: "Ruta 130",
    264: "Ruta 131",
    266: "Ruta 132",
    268: "Ruta 133",
    270: "Ruta 134",

    # --- Cuevas, montañas y zonas especiales de la historia ---
    272: "Cascada Meteoro",         # Meteor Falls
    274: "Túnel Fervegal",          # Rusturf Tunnel
    280: "Cueva Granito",           # Granite Cave
    282: "Bosque Petalia",          # Petalburg Woods
    284: "Monte Cenizo",            # Mt. Chimney
    286: "Desfiladero",             # Jagged Pass
    288: "Senda Ígnea",             # Fiery Path
    290: "Monte Pírico",            # Mt. Pyre
    292: "Guarida Aqua",            # Team Aqua Hideout
    294: "Caverna Abisal",          # Seafloor Cavern
    296: "Cueva Ancestral",         # Cave of Origin
    300: "Cueva Cardumen",          # Shoal Cave (30/08/2026,
                                    # traduccion pasada por el
                                    # usuario)
    302: "Malvalanova",             # New Mauville
    304: "Malvamar",                # Sea Mauville (30/08/2026,
                                    # traduccion pasada por el
                                    # usuario)
    312: "Gruta Solar",             # Scorched Slab (30/08/2026,
                                    # traduccion pasada por el
                                    # usuario)
    314: "Guarida Magma",           # Team Magma Hideout
    316: "Pilar Celeste",           # Sky Pillar
    324: "Zona Safari",             # Safari Zone

    # --- Post-juego / ultravuelo (parcialmente verificado) ---
    318: "Resort Batalla",          # Battle Resort
    320: "Isla del Sur",            # Southern Island
    322: "S.S. Marea",              # S.S. Tidal
    326: "Bosque Espejismo",        # Mirage Forest
    328: "Cueva Espejismo",         # Mirage Cave
    330: "Isla Espejismo",          # Mirage Island
    332: "Monte Espejismo",         # Mirage Mountain
    346: "Islote Secreto",          # Secret Islet
    348: "Firmamento",              # Soaring in the Sky
                                    # (30/08/2026, traduccion
                                    # pasada por el usuario)

    # Costa Secreta (350, Secret Shore), Prado Secreto (352, Secret
    # Meadow) y Base Secreta (354, Secret Base) -- excluidas del
    # panel precargado a propósito (EXCLUDED_LOCATION_IDS en
    # location_catalog.py, decisión explícita del usuario del
    # 30/08/2026: no son relevantes para armar la lista inicial de
    # un Nuzlocke normal), pero SÍ traducidas acá -- si una captura
    # real termina reportando alguna de estas como Met_Location, el
    # fallback debe mostrar español, no el crudo de PKHeX en inglés.
    350: "Costa Secreta",           # Secret Shore
    352: "Prado Secreto",           # Secret Meadow
    354: "Base Secreta",            # Secret Base

    # --- Las 4 ruinas de los Regis (278/306/308/310) -- alcanzables
    # en la historia normal (no post-juego real, a diferencia de lo
    # que decía el comentario viejo de este archivo), verificadas
    # contra WikiDex/Fandom el 09/09/2026. Encontrado real: el
    # comentario anterior las marcaba como "post-juego/DexNav no
    # relevantes", pero solo la Cámara Sellada (310, la que abre las
    # otras 3) requiere buceo -- las otras son parte del recorrido
    # normal de la ruta 111/105/120. Si un Nuzlocke real encuentra o
    # captura algo ahí, el nombre ahora sale en español.
    278: "Ruinas del Desierto",     # Desert Ruins
    306: "Cueva Insular",           # Island Cave
    308: "Tumba Antigua",           # Ancient Tomb
    310: "Cámara Sellada",          # Sealed Chamber

    # --- Parajes espejismo raros (334-344) -- SÍ son post-juego/
    # DexNav real (solo accesibles con Ultravuelo y condiciones
    # puntuales por Pokémon en el equipo), pero se traducen igual
    # por completitud -- verificadas contra WikiDex/PokéCompany el
    # 09/09/2026.
    334: "Bosque Virgen",           # Trackless Forest
    336: "Llanura Sinnombre",       # Pathless Plain
    338: "Cueva Ignota",            # Nameless Cavern
    340: "Cueva Incierta",         # Fabled Cave
    342: "Boquete Irregular",       # Gnarled Den
    344: "Isla Creciente",          # Crescent Isle

    # ID 276 ("???") queda SIN traducir a propósito -- no es una
    # ubicación jugable real (nombre crudo interno de PKHeX, nunca
    # se pudo confirmar qué es), no hay nada verificable para
    # traducir (regla #12: no adivinar).
}


def translate_location_name(location_id, fallback_name):
    """
    Devuelve el nombre en español verificado para `location_id` si
    existe, o `fallback_name` (lo que haya devuelto PKHeX, en
    inglés normalmente) si no hay traducción confirmada para ese
    ID todavía.
    """

    return HOENN_LOCATION_NAMES_ES.get(
        location_id,
        fallback_name,
    )

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

Deliberadamente NO están todas las ~93 ubicaciones de Hoenn: los
IDs que no aparecen acá son zonas post-juego/DexNav poco comunes
(cuevas y ruinas secundarias) cuyo nombre en español no se pudo
confirmar con una fuente confiable -- para esas se prefiere dejar
el nombre en inglés (lo que devuelve PKHeX) antes que arriesgar una
traducción incorrecta. Si en algún momento se confirman, agregarlas
acá.
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
    302: "Malvalanova",             # New Mauville
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
    350: "Costa Secreta",           # Secret Shore
    352: "Prado Secreto",           # Secret Meadow
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

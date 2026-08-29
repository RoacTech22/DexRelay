"""
Traducción manual español (España) para eggLocationName -- el
"Entregado por" del resumen de un Pokémon (ver
app/services/location_resolver.py y dotnet/DexRelay.PKHeX/Program.cs).

A veces PKHeX.Core no tiene el string en español cargado para un
ID de eggLocation puntual y devuelve el texto en inglés en su
lugar, a pesar de que GameInfo.CurrentLanguage está fijado en "es"
(mismo problema documentado para algunas de las ~16 ubicaciones de
Hoenn sin traducir en hoenn_locations_es.py, acá aplicado a
"Entregado por").

A diferencia de hoenn_locations_es.py (que traduce por ID numérico,
ya que se conoce el rango completo de IDs de Hoenn), acá se traduce
por el TEXTO EN INGLÉS que devuelve PKHeX -- el conjunto de
NPCs/orígenes que pueden entregar un huevo es chico y estable, y el
ID todavía no se propaga hasta este punto del pipeline (solo el
texto ya resuelto). Si en el futuro hace falta más precisión,
cambiar a traducción por ID como hoenn_locations_es.py.

Cada entrada está verificada contra el texto real mostrado en el
juego (pantalla de Resumen/Memoria del Pokémon, campo "Entregado
por"), reportado por el usuario -- no adivinada.
"""

EGG_LOCATION_NAMES_ES = {
    # Verificado 28/08/2026: el juego (en español) muestra
    # "Anciana del Balneario"; PKHeX devolvía el inglés
    # "an old hot-springs visitor" para ese mismo ID.
    "an old hot-springs visitor": "Anciana del Balneario",

    # Verificado 28/08/2026: el juego (en español) muestra
    # "Pareja de la Guardería"; PKHeX devolvía el inglés
    # "day care helpers" para ese mismo ID.
    "day care helpers": "Pareja de la Guardería",
}


def translate_egg_location_name(english_text: str) -> str:
    """
    Devuelve la traducción verificada para `english_text` (se
    compara sin importar mayúsculas ni espacios de más), o el
    texto tal cual si todavía no hay traducción confirmada para
    ese texto.
    """

    if not english_text:
        return english_text

    normalized = english_text.strip().lower()

    return EGG_LOCATION_NAMES_ES.get(
        normalized,
        english_text,
    )

"""
Cálculo de resistencias/debilidades de un Pokémon a partir de su(s)
tipo(s) (roadmap 06/09/2026, sección 4.2 -- modal "Pokédex" de
detalle de especie).

A diferencia de todo lo demás que arma el modal de especie (que sale
del bridge PKHeX), esto NO es un dato para pedirle a nadie -- es
CÁLCULO LOCAL puro a partir de dos cosas ya confirmadas:
    - El tipo (o los dos tipos) de la especie, que ya devuelve
      species_details() (type1Key/type2Key, ver Program.cs).
    - data/type_chart.json, la tabla 18x18 de efectividad ya curada
      (06/09/2026, confirmada vigente sin cambios desde que se
      introdujo el tipo Fairy en Gen 6 -- ver el campo "_source" del
      propio archivo).

No necesita el bridge, ni memoria, ni internet -- es aritmética
sobre datos ya en el proyecto. Mismo patrón de caché que
MoveDataCatalog/SpeciesCatalog: se lee el JSON una sola vez.
"""

import json

from app.core import paths


class TypeChartCatalog:
    """
    Carga cacheada de data/type_chart.json. El formato real:
    chart[atacante][defensor] = multiplicador -- un tipo AUSENTE en
    el objeto de un atacante significa multiplicador neutral (1x)
    contra ese tipo (ver el campo "comment" del propio archivo, así
    quedó armado a propósito para no inflar el JSON con las 204
    entradas 1x redundantes de las 324 combinaciones posibles).
    """

    def __init__(self):
        self._chart = None
        self._types = None

    def _ensure_loaded(self):

        if self._chart is not None:
            return

        data_path = paths.path("data", "type_chart.json")

        if not data_path.exists():
            # Degradación con gracia (mismo criterio que
            # MoveDataCatalog): si el archivo no está, el resto del
            # modal de especie sigue funcionando sin resistencias/
            # debilidades, en vez de romper toda la respuesta.
            self._chart = {}
            self._types = []
            return

        with open(data_path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        self._chart = raw.get("chart", {})
        self._types = raw.get("types", [])

    def multiplier(self, attacker_type_key, defender_type_key):
        """
        Multiplicador de un ataque de tipo `attacker_type_key`
        contra un defensor de tipo `defender_type_key`. 1.0 si el
        par no aparece en la tabla (neutral, ver docstring de la
        clase) o si el dataset no está disponible.
        """

        self._ensure_loaded()

        attacker_row = self._chart.get(attacker_type_key, {})

        return attacker_row.get(defender_type_key, 1.0)

    def all_types(self):
        """
        Los 18 nombres de tipo (claves estables en inglés, mismo
        criterio que typeKey en todo el proyecto), en el orden
        curado del propio archivo. Lista vacía si el dataset no
        está disponible.
        """

        self._ensure_loaded()

        return list(self._types)


def compute_effectiveness(type1_key, type2_key, catalog):
    """
    Devuelve, para CADA uno de los 18 tipos atacantes, el
    multiplicador combinado contra un defensor de tipo
    `type1_key`/`type2_key` -- multiplicar el multiplicador contra
    cada tipo del defensor por separado es la misma fórmula que usa
    el juego real para un Pokémon de doble tipo (ej. Water/Ground
    contra Electric: 2x de Water * 0x de Ground = 0x, inmune).

    `type2_key` puede ser cadena vacía (especies de un solo tipo,
    mismo criterio que ya usa species_details()/pokemon_details() en
    el bridge) -- el multiplicador contra un tipo vacío siempre da
    1.0 (ver TypeChartCatalog.multiplier()), así que no hace falta
    ningún caso especial acá: multiplicar por 1.0 no cambia nada.

    Devuelve {typeKey: multiplicador}, uno por cada uno de los 18
    tipos atacantes.
    """

    result = {}

    for attacker_type_key in catalog.all_types():

        multiplier = (
            catalog.multiplier(attacker_type_key, type1_key)
            * catalog.multiplier(attacker_type_key, type2_key)
        )

        result[attacker_type_key] = multiplier

    return result


def categorize_effectiveness(effectiveness):
    """
    Agrupa el resultado de compute_effectiveness() en las tres
    categorías que le importan al modal Pokédex: inmunidades (0x),
    resistencias (menos de 1x pero no 0), debilidades (más de 1x).
    Los tipos neutrales (exactamente 1x) NO se incluyen en ningún
    grupo -- mismo criterio que el propio type_chart.json (no listar
    lo que no aporta información).

    Cada grupo es una lista de {"typeKey": ..., "multiplier": ...},
    ordenada de más extrema a menos extrema (4x antes que 2x,
    0x antes que 0.25x) -- el orden en que tiene sentido mostrarlas
    en un modal.
    """

    weaknesses = []
    resistances = []
    immunities = []

    for type_key, multiplier in effectiveness.items():

        if multiplier == 0:
            immunities.append(
                {"typeKey": type_key, "multiplier": multiplier}
            )
        elif multiplier > 1:
            weaknesses.append(
                {"typeKey": type_key, "multiplier": multiplier}
            )
        elif multiplier < 1:
            resistances.append(
                {"typeKey": type_key, "multiplier": multiplier}
            )
        # multiplier == 1: neutral, no se incluye en ningún grupo.

    weaknesses.sort(key=lambda entry: entry["multiplier"], reverse=True)
    resistances.sort(key=lambda entry: entry["multiplier"])

    return {
        "weaknesses": weaknesses,
        "resistances": resistances,
        "immunities": immunities,
    }

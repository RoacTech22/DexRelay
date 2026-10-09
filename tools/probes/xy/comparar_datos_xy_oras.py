"""
P6 (paridad X/Y, 09/10/2026), paso 1: medir qué datos de especies y de
movimientos DIFIEREN entre Pokémon X/Y y Pokémon Rubí Omega/Zafiro Alfa,
antes de decidir si Kalos necesita datasets propios.

Hasta hoy toda la app usa datos de ORAS para todo:

  * Especies (tipos, estadísticas base, habilidades, evoluciones): el
    bridge usa `PersonalTable.AO` (ORAS) para cualquier juego.
  * Movimientos (potencia/precisión/categoría): `data/move_data.json`
    está fijado a ORAS (`tools/data_curation/build_move_data.py`).

Regla del proyecto: nada se da por igual ni por distinto sin medirlo.

QUÉ HACE (solo lectura, no escribe en `data/`):

  1. ESPECIES. Pide al bridge `species_details` de las especies 1..721
     para AS (tabla de ORAS), X e Y (tabla de X/Y) y compara tipos,
     estadísticas base, habilidades y evoluciones. Necesita el bridge C#
     publicado con el cambio de P6 (acepta `game` en `species_details`).
  2. MOVIMIENTOS. Descarga de PokéAPI `move_changelog.csv` y
     `version_groups.csv` y lista los cambios de movimientos registrados
     justo en el version_group de ORAS (son, por definición, lo que
     cambió entre X/Y y ORAS). Además cuenta los cambios registrados en
     X/Y (que son anteriores a ORAS y no distinguen un juego de otro).
     Necesita internet.

Cada parte funciona sola: si una falla, la otra se informa igual.

Uso (desde la raíz del proyecto):

    python tools/probes/xy/comparar_datos_xy_oras.py

Pega en el chat el texto que imprime. El detalle completo queda en
tools/probes/xy/salida/comparar_datos_xy_oras.json.
"""

import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = (
    Path(__file__).resolve().parent / "salida" / "comparar_datos_xy_oras.json"
)

# Kalos + las generaciones previas: 1..721 (sin Megas ni formas; las
# formas se revisan aparte en sprites).
SPECIES_MIN = 1
SPECIES_MAX = 721

CHANGELOG_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/move_changelog.csv"
)
VERSION_GROUPS_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/version_groups.csv"
)
MOVES_URL = (
    "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
    "data/v2/csv/moves.csv"
)

XY_GROUP = "x-y"
ORAS_GROUP = "omega-ruby-alpha-sapphire"

_CAMPOS_BASE = ("hp", "attack", "defense", "spAttack", "spDefense", "speed")
_CAMPOS_HABILIDAD = (
    "ability1Id",
    "ability2Id",
    "abilityHiddenId",
)


# ---------------------------------------------------------------- especies


def _evoluciones_normalizadas(detalle):
    """Lista ordenada y comparable de las evoluciones de una especie."""
    resultado = []

    for evo in detalle.get("evolutions") or []:
        resultado.append(
            (
                evo.get("toSpeciesId"),
                evo.get("methodKey"),
                evo.get("level"),
                evo.get("argument"),
            )
        )

    return sorted(resultado, key=repr)


def diferencias_especie(detalle_oras, detalle_xy):
    """
    Compara dos respuestas de `species_details` de la misma especie.
    Devuelve una lista de {campo, oras, xy}; vacía si son iguales.
    """
    diferencias = []

    for campo in ("type1Key", "type2Key"):
        if detalle_oras.get(campo) != detalle_xy.get(campo):
            diferencias.append(
                {
                    "campo": campo,
                    "oras": detalle_oras.get(campo),
                    "xy": detalle_xy.get(campo),
                }
            )

    stats_oras = detalle_oras.get("baseStats") or {}
    stats_xy = detalle_xy.get("baseStats") or {}

    for campo in _CAMPOS_BASE:
        if stats_oras.get(campo) != stats_xy.get(campo):
            diferencias.append(
                {
                    "campo": f"baseStats.{campo}",
                    "oras": stats_oras.get(campo),
                    "xy": stats_xy.get(campo),
                }
            )

    for campo in _CAMPOS_HABILIDAD:
        if detalle_oras.get(campo) != detalle_xy.get(campo):
            diferencias.append(
                {
                    "campo": campo,
                    "oras": (
                        detalle_oras.get(campo),
                        detalle_oras.get(campo.replace("Id", "Name")),
                    ),
                    "xy": (
                        detalle_xy.get(campo),
                        detalle_xy.get(campo.replace("Id", "Name")),
                    ),
                }
            )

    evo_oras = _evoluciones_normalizadas(detalle_oras)
    evo_xy = _evoluciones_normalizadas(detalle_xy)

    if evo_oras != evo_xy:
        diferencias.append(
            {"campo": "evolutions", "oras": evo_oras, "xy": evo_xy}
        )

    return diferencias


def comparar_especies(por_id_oras, por_id_xy):
    """
    Compara {id: detalle} de ORAS contra {id: detalle} de X/Y.
    Devuelve {"comparadas", "iguales", "distintas": [{id, name,
    diferencias}], "sin_datos": [ids]}.
    """
    distintas = []
    sin_datos = []
    iguales = 0

    for especie_id in sorted(set(por_id_oras) | set(por_id_xy)):
        a = por_id_oras.get(especie_id)
        b = por_id_xy.get(especie_id)

        if not a or not b or "error" in a or "error" in b:
            sin_datos.append(especie_id)
            continue

        difs = diferencias_especie(a, b)

        if difs:
            distintas.append(
                {
                    "id": especie_id,
                    "name": a.get("name", ""),
                    "diferencias": difs,
                }
            )
        else:
            iguales += 1

    return {
        "comparadas": iguales + len(distintas),
        "iguales": iguales,
        "distintas": distintas,
        "sin_datos": sin_datos,
    }


# -------------------------------------------------------------- movimientos


def _id_de_grupo(filas_grupos, identificador):
    for fila in filas_grupos:
        if fila.get("identifier") == identificador:
            return str(fila.get("id"))

    return None


def analizar_changelog(filas_changelog, filas_grupos, nombres=None):
    """
    A partir de `move_changelog.csv` y `version_groups.csv` de PokéAPI.

    Cada fila del changelog dice "en el version_group indicado este
    movimiento cambió", y trae los valores ANTERIORES al cambio (por
    ejemplo, Látigo Cepa: 35 de potencia y 15 PP hasta Gen 5; en X/Y ya
    es 45 y 25). Por lo tanto:

      * filas en el grupo de ORAS = lo que cambió entre X/Y y ORAS;
      * filas en el grupo de X/Y = lo que cambió entre Gen 5 y X/Y
        (X/Y y ORAS ya comparten el valor nuevo).

    `nombres` ({move_id: nombre}) es opcional, solo para el informe.
    """
    nombres = nombres or {}
    id_xy = _id_de_grupo(filas_grupos, XY_GROUP)
    id_oras = _id_de_grupo(filas_grupos, ORAS_GROUP)

    if id_xy is None or id_oras is None:
        return {
            "error": "version_groups.csv no trae x-y u omega-ruby-alpha-sapphire",
            "id_xy": id_xy,
            "id_oras": id_oras,
        }

    campos = ("type_id", "power", "pp", "accuracy", "priority", "target_id", "effect_id", "effect_chance")

    def _fila(fila):
        move_id = int(fila["move_id"])
        return {
            "move_id": move_id,
            "name": nombres.get(move_id, ""),
            "valores_anteriores": {
                campo: fila.get(campo)
                for campo in campos
                if fila.get(campo) not in (None, "")
            },
        }

    en_oras = [
        _fila(f)
        for f in filas_changelog
        if str(f.get("changed_in_version_group_id")) == id_oras
    ]
    en_xy = [
        f
        for f in filas_changelog
        if str(f.get("changed_in_version_group_id")) == id_xy
    ]

    return {
        "id_xy": id_xy,
        "id_oras": id_oras,
        "cambios_entre_xy_y_oras": en_oras,
        "cantidad_cambiados_en_xy_gen5_a_gen6": len(en_xy),
    }


def _descargar_csv(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "DexRelay-Probe/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as respuesta:
        texto = respuesta.read().decode("utf-8")

    return list(csv.DictReader(io.StringIO(texto)))


# ------------------------------------------------------------------ informe


def formatear(especies, movimientos):
    lineas = []

    lineas.append("=== ESPECIES (tabla personal XY vs AO, especies 1..721) ===")

    if especies is None:
        lineas.append("  (no se pudo medir; ver el error de arriba)")
    else:
        lineas.append(
            f"  comparadas={especies['comparadas']}  "
            f"iguales={especies['iguales']}  "
            f"distintas={len(especies['distintas'])}  "
            f"sin_datos={len(especies['sin_datos'])}"
        )

        if especies["sin_datos"]:
            lineas.append(f"  sin datos: {especies['sin_datos'][:40]}")

        for entrada in especies["distintas"]:
            lineas.append(f"  #{entrada['id']} {entrada['name']}")

            for dif in entrada["diferencias"]:
                lineas.append(
                    f"      {dif['campo']}: ORAS={dif['oras']}  X/Y={dif['xy']}"
                )

    lineas.append("")
    lineas.append("=== MOVIMIENTOS (move_changelog de PokéAPI) ===")

    if movimientos is None:
        lineas.append("  (no se pudo medir; ver el error de arriba)")
    elif "error" in movimientos:
        lineas.append(f"  {movimientos['error']}")
    else:
        cambios = movimientos["cambios_entre_xy_y_oras"]
        lineas.append(
            f"  version_group x-y={movimientos['id_xy']}  "
            f"oras={movimientos['id_oras']}"
        )
        lineas.append(
            f"  cambios registrados ENTRE X/Y y ORAS: {len(cambios)}"
        )

        for cambio in cambios:
            lineas.append(
                f"      #{cambio['move_id']} {cambio['name']}: "
                f"valores anteriores (X/Y) = {cambio['valores_anteriores']}"
            )

        lineas.append(
            "  cambios registrados en X/Y (Gen 5 -> X/Y, no distinguen "
            f"X/Y de ORAS): {movimientos['cantidad_cambiados_en_xy_gen5_a_gen6']}"
        )

    return "\n".join(lineas)


# --------------------------------------------------------------------- main


def medir_especies(bridge):
    por_id = {"AS": {}, "X": {}, "Y": {}}

    for juego in ("AS", "X", "Y"):
        for especie_id in range(SPECIES_MIN, SPECIES_MAX + 1):
            por_id[juego][especie_id] = bridge.species_details(
                especie_id, game=juego
            )

    resultado = {
        "oras_vs_x": comparar_especies(por_id["AS"], por_id["X"]),
        "x_vs_y": comparar_especies(por_id["X"], por_id["Y"]),
    }

    return resultado


def main() -> int:
    especies = None
    movimientos = None

    try:
        from app.services.pkhex.bridge import PKHeXBridge

        bridge = PKHeXBridge.shared()
        prueba = bridge.species_details(25, game="X")

        if "error" in prueba:
            raise RuntimeError(
                f"el bridge respondió {prueba['error']!r}: ¿está publicado "
                "con el cambio de P6 (species_details acepta 'game')?"
            )

        especies = medir_especies(bridge)
    except Exception as error:
        print(f"Especies: falló ({error!r})")

    try:
        filas_cambios = _descargar_csv(CHANGELOG_URL)
        filas_grupos = _descargar_csv(VERSION_GROUPS_URL)
        nombres = {}

        try:
            for fila in _descargar_csv(MOVES_URL):
                nombres[int(fila["id"])] = fila.get("identifier", "")
        except Exception:
            nombres = {}

        movimientos = analizar_changelog(filas_cambios, filas_grupos, nombres)
    except Exception as error:
        print(f"Movimientos: falló ({error!r})")

    oras_vs_x = None if especies is None else especies["oras_vs_x"]

    print(formatear(oras_vs_x, movimientos))

    if especies is not None:
        x_vs_y = especies["x_vs_y"]
        print("")
        print(
            "X vs Y (misma tabla esperada): "
            f"distintas={len(x_vs_y['distintas'])} "
            f"sin_datos={len(x_vs_y['sin_datos'])}"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            {"especies": especies, "movimientos": movimientos},
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    print(f"\nVolcado completo guardado en: {OUTPUT_PATH}")

    return 0 if (especies is not None or movimientos is not None) else 1


if __name__ == "__main__":
    sys.exit(main())

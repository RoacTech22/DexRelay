"""
P1 (paridad X/Y, 05/10/2026), paso A: volcar la lista de ubicaciones
que PKHeX devuelve para Pokémon X y Pokémon Y.

Por qué existe: el catálogo de Kalos (rango de IDs, exclusiones, orden
narrativo) NO se fija de memoria ni a partir de la lista de Alpha
Sapphire (que también trae IDs de Kalos). Antes de escribir
app/games/xy/locations.py hay que ver lo que el bridge devuelve de
verdad para "X" y para "Y" y responder tres preguntas:

  1. ¿X e Y devuelven la MISMA lista? (si sí, comparten LocationSpec y
     caché `location_cache_xy.json`, como OR/AS.)
  2. ¿En qué rango de IDs cae Kalos y qué hay fuera del rango (Hoenn,
     eventos, transferencias, regalos)?
  3. ¿Los IDs/nombres de Kalos coinciden con los que ya aparecen en la
     lista de AS? (la caché data/location_cache.json los trae.)

Solo lectura: habla con el bridge de PKHeX (no necesita Azahar ni el
juego abierto) y no escribe en data/. La salida completa se guarda en
tools/probes/xy/salida/ubicaciones_xy.json para adjuntarla al chat.

Uso (desde la raíz del proyecto):

    python tools/probes/xy/volcar_ubicaciones_xy.py

Pega en el chat el texto que imprime (y adjunta el JSON si es largo).
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Kalos en la lista cruda de PKHeX: IDs bajos (los de Hoenn arrancan en
# 170). El límite superior es solo para clasificar en el informe, NO es
# una constante del perfil: el rango real se decide con el volcado.
ZONA_BAJA_MAX = 169
HOENN_MIN = 170
HOENN_MAX = 354

OUTPUT_PATH = Path(__file__).resolve().parent / "salida" / "ubicaciones_xy.json"


def _por_id(lista):
    """{id: nombre} de una lista [{'id','name'}, ...]; ignora entradas rotas."""
    resultado = {}

    for entrada in lista or []:
        try:
            resultado[int(entrada["id"])] = str(entrada.get("name", ""))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue

    return resultado


def clasificar(location_id):
    """Cubo informativo de un ID (solo para el informe)."""
    if location_id <= 0:
        return "cero"
    if location_id <= ZONA_BAJA_MAX:
        return "kalos(<=169)"
    if HOENN_MIN <= location_id <= HOENN_MAX:
        return "hoenn(170-354)"
    if 30000 <= location_id < 40000:
        return "transferencia(30000+)"
    if 40000 <= location_id < 60000:
        return "evento(40000+)"
    if location_id >= 60000:
        return "regalo(60000+)"
    return "otro"


def analizar(x, y, as_=None):
    """
    Compara las listas crudas de X, Y (y AS si se da). Función pura:
    recibe listas [{'id','name'}] y devuelve un dict con los hallazgos.
    """
    mx, my = _por_id(x), _por_id(y)
    mas = _por_id(as_) if as_ is not None else None

    solo_x = sorted(set(mx) - set(my))
    solo_y = sorted(set(my) - set(mx))
    nombres_distintos = sorted(
        i for i in set(mx) & set(my) if mx[i] != my[i]
    )

    cubos = {}
    for location_id in mx:
        cubos.setdefault(clasificar(location_id), []).append(location_id)
    cubos = {k: sorted(v) for k, v in sorted(cubos.items())}

    kalos_x = {i: n for i, n in sorted(mx.items()) if 0 < i <= ZONA_BAJA_MAX}

    # Nombres repetidos dentro de Kalos (dos IDs con el mismo texto
    # romperían el "una captura encuentra su fila").
    por_nombre = {}
    for i, n in kalos_x.items():
        por_nombre.setdefault(n, []).append(i)
    repetidos = {n: ids for n, ids in por_nombre.items() if len(ids) > 1}

    huecos_pares = sorted(
        set(range(2, max(kalos_x) + 1, 2)) - set(kalos_x)
    ) if kalos_x else []

    resultado = {
        "total_x": len(mx),
        "total_y": len(my),
        "x_igual_a_y": not (solo_x or solo_y or nombres_distintos),
        "solo_en_x": solo_x,
        "solo_en_y": solo_y,
        "nombre_distinto_xy": [
            {"id": i, "x": mx[i], "y": my[i]} for i in nombres_distintos
        ],
        "cubos_x": {k: len(v) for k, v in cubos.items()},
        "kalos_min": min(kalos_x) if kalos_x else None,
        "kalos_max": max(kalos_x) if kalos_x else None,
        "kalos_cantidad": len(kalos_x),
        "kalos_ids_pares_ausentes": huecos_pares,
        "nombres_repetidos_en_kalos": repetidos,
        "hoenn_en_lista_x": len(cubos.get("hoenn(170-354)", [])),
    }

    if mas is not None:
        kalos_as = {i: n for i, n in mas.items() if 0 < i <= ZONA_BAJA_MAX}
        resultado["kalos_x_vs_as"] = {
            "mismos_ids": sorted(kalos_x) == sorted(kalos_as),
            "solo_en_x": sorted(set(kalos_x) - set(kalos_as)),
            "solo_en_as": sorted(set(kalos_as) - set(kalos_x)),
            "nombre_distinto": [
                {"id": i, "x": kalos_x[i], "as": kalos_as[i]}
                for i in sorted(set(kalos_x) & set(kalos_as))
                if kalos_x[i] != kalos_as[i]
            ],
        }

    return resultado


def formatear(hallazgos, x):
    """Informe de texto para pegar en el chat."""
    lineas = []
    h = hallazgos

    lineas.append(f"Entradas: X={h['total_x']}  Y={h['total_y']}")
    lineas.append(
        "X e Y devuelven la MISMA lista: "
        + ("SÍ" if h["x_igual_a_y"] else "NO")
    )

    if not h["x_igual_a_y"]:
        lineas.append(f"  solo en X: {h['solo_en_x']}")
        lineas.append(f"  solo en Y: {h['solo_en_y']}")
        for d in h["nombre_distinto_xy"]:
            lineas.append(f"  nombre distinto id {d['id']}: X={d['x']!r} Y={d['y']!r}")

    lineas.append("")
    lineas.append("IDs de X por cubo: " + ", ".join(
        f"{k}={v}" for k, v in h["cubos_x"].items()
    ))
    lineas.append(
        f"Kalos (1..{ZONA_BAJA_MAX}): {h['kalos_cantidad']} entradas, "
        f"min={h['kalos_min']} max={h['kalos_max']}"
    )
    lineas.append(f"IDs pares ausentes dentro de Kalos: {h['kalos_ids_pares_ausentes']}")
    lineas.append(f"Hoenn (170-354) presente en la lista de X: {h['hoenn_en_lista_x']}")

    if h["nombres_repetidos_en_kalos"]:
        lineas.append(f"NOMBRES REPETIDOS en Kalos: {h['nombres_repetidos_en_kalos']}")

    cmp_as = h.get("kalos_x_vs_as")
    if cmp_as is not None:
        lineas.append("")
        lineas.append(
            "Kalos de X vs lista de AS: "
            + ("idénticos" if cmp_as["mismos_ids"] and not cmp_as["nombre_distinto"] else "DIFIEREN")
        )
        if cmp_as["solo_en_x"]:
            lineas.append(f"  solo en X: {cmp_as['solo_en_x']}")
        if cmp_as["solo_en_as"]:
            lineas.append(f"  solo en AS: {cmp_as['solo_en_as']}")
        for d in cmp_as["nombre_distinto"]:
            lineas.append(f"  id {d['id']}: X={d['x']!r} AS={d['as']!r}")

    lineas.append("")
    lineas.append("Kalos según X (id  nombre):")
    for location_id, name in sorted(_por_id(x).items()):
        if 0 < location_id <= ZONA_BAJA_MAX:
            lineas.append(f"  {location_id:>3}  {name}")

    return "\n".join(lineas)


def main() -> int:
    from app.services.pkhex.bridge import PKHeXBridge

    bridge = PKHeXBridge.shared()
    listas = {}

    for juego in ("X", "Y", "AS"):
        try:
            respuesta = bridge.location_list(juego)
        except Exception as error:  # el bridge puede no estar publicado
            print(f"location_list({juego!r}) falló: {error!r}")
            print(
                "Revisa que el bridge C# esté publicado con el cambio del "
                "Bloque 13 (acepta 'game')."
            )
            return 1

        listas[juego] = respuesta.get("locations", [])

    hallazgos = analizar(listas["X"], listas["Y"], listas["AS"])

    print(formatear(hallazgos, listas["X"]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            {"hallazgos": hallazgos, "listas": listas},
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    print(f"\nVolcado completo guardado en: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

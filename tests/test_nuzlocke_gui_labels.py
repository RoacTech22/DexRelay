"""
Etiquetas y orden de la tabla de Nuzlocke de la GUI (06/10/2026):
- un especial muestra solo su origen ("Fósil"), sin "Especial/";
- un Pokémon que se fue por intercambio muestra "Intercambiado" con su
  propio color;
- una fila con ancla se ubica justo debajo de su ruta, no al final.

La GUI vive en un IIFE de app.js, así que las funciones se extraen del
texto y se ejecutan con Node (si no está instalado, el test se salta).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[1] / "app" / "gui_web" / "web" / "js" / "app.js"


def _function_source(source, name):
    start = source.index(f"function {name}(")
    depth = 0

    for index in range(source.index("{", start), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1

            if depth == 0:
                return source[start:index + 1]

    raise AssertionError(name)


def _run(expression, order_map=None):
    node = shutil.which("node")

    if node is None:
        pytest.skip("Node no está instalado")

    source = APP_JS.read_text(encoding="utf-8")
    labels = re.search(r"var NZ_STATUS_LABELS = \{.*?\};", source, re.S).group(0)
    origins = re.search(r"var NZ_ORIGIN_LABELS = \{.*?\};", source, re.S).group(0)
    functions = "\n".join(
        _function_source(source, name)
        for name in ("nuzlockeStatusLabel", "nuzlockeStatusClass", "encounterSortKey")
    )
    script = (
        f"{labels}\n{origins}\n"
        f"var nuzlockeLocationOrderMap = {json.dumps(order_map)};\n"
        f"{functions}\n"
        f"console.log(JSON.stringify({expression}));"
    )
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stderr

    return json.loads(result.stdout)


def test_un_especial_muestra_solo_su_origen():
    for origin, label in (
        ("fosil", "Fósil"), ("shiny", "Shiny"), ("huevo", "Huevo"),
        ("intercambio", "Intercambio"), ("regalo", "Regalo"), ("evento", "Evento"),
    ):
        assert _run(
            f'nuzlockeStatusLabel({{status: "especial", origin: "{origin}"}})'
        ) == label


def test_estados_normales_conservan_su_etiqueta():
    assert _run('nuzlockeStatusLabel({status: "capturado"})') == "Capturado"
    assert _run('nuzlockeStatusLabel({status: "muerto"})') == "Muerto"
    assert _run('nuzlockeStatusLabel({status: "capturado", extraCapture: true})') == "Captura Extra"
    assert _run('nuzlockeStatusLabel({status: "especial"})') == "Especial"


def test_el_pokemon_intercambiado_tiene_etiqueta_y_color_propios():
    entry = '{status: "capturado", tradedAway: true}'

    assert _run(f"nuzlockeStatusLabel({entry})") == "Intercambiado"
    assert _run(f"nuzlockeStatusClass({entry})") == "intercambiado"
    assert _run('nuzlockeStatusClass({status: "muerto"})') == "muerto"
    # Gana sobre cualquier otro estado: el Pokémon ya no está en el juego.
    assert _run(
        'nuzlockeStatusLabel({status: "especial", origin: "fosil", tradedAway: true})'
    ) == "Intercambiado"


def test_una_fila_anclada_va_justo_despues_de_su_ruta():
    order = {"ruta 2": 3, "pueblo petroglifo": 20, "ruta 9": 21}

    ancla = _run(
        'encounterSortKey({location: "Fósil", anchorLocation: "Pueblo Petroglifo"}, 99)',
        order,
    )

    assert order["pueblo petroglifo"] < ancla < order["ruta 9"]
    # Sin ancla ni match sigue yendo al final.
    assert _run('encounterSortKey({location: "Fósil"}, 5)', order) >= 100000

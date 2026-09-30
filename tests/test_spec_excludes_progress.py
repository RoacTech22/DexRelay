"""
Regla 10 del Documento Maestro: el progreso real del usuario NUNCA se
distribuye. Bloque 5 (24/09/2026): con los archivos por partida
(nuzlocke_<juego>_<tid>_<sid>.json, badges_<juego>_<tid>_<sid>.json)
el spec dejaba pasar los badges_* porque solo excluía "badges.json"
por nombre exacto.

Este test ejecuta el bucle REAL de DexRelay.spec (el fragmento que
arma `datas` desde data/) sobre una carpeta data/ de prueba, en vez
de repetir la regla acá -- si alguien la rompe en el spec, falla.
"""

import os
import tempfile
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / "DexRelay.spec"


def _spec_data_loop_source() -> str:
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("import os\n\n_USER_PROGRESS_FILES")
    end = text.index("binaries = []")
    return text[start:end]


def _run_loop(file_names):
    previous = os.getcwd()

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "data" / "backups").mkdir(parents=True)

        for name in file_names:
            (Path(tmp) / "data" / name).write_text("{}", encoding="utf-8")

        os.chdir(tmp)

        try:
            scope = {"datas": []}
            exec(_spec_data_loop_source(), scope)
        finally:
            os.chdir(previous)

    return sorted(Path(source).name for source, _dest in scope["datas"])


def test_el_spec_excluye_todo_el_progreso_del_usuario():
    shipped = _run_loop([
        "nuzlocke_omega_ruby_29153_54059.json",
        "nuzlocke_alpha_sapphire_23756_50341.json",
        "nuzlocke_omega_ruby.json",
        "badges.json",
        "badges_omega_ruby_29153_54059.json",
        "badges_alpha_sapphire_23756_50341.json",
        "team_overlay_settings.json",
        "move_data.json",
        "type_chart.json",
        "species_cache.json",
    ])

    assert shipped == ["move_data.json", "species_cache.json", "type_chart.json"]

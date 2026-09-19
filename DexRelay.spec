# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# NOTA (05/09/2026, junto con app/core/version.py): antes de correr
# `pyinstaller DexRelay.spec`, generar el archivo VERSION en la raíz
# del proyecto con el tag real de Git -- NO escribirlo a mano:
#
#   git describe --tags --always --dirty > VERSION
#
# Sin ese archivo en el build empaquetado, get_app_version() (ver
# app/core/version.py) no tiene de dónde leer la versión (no hay
# `.git` real dentro del .exe) y la GUI muestra "versión
# desconocida" en vez de inventar un número -- no es un bug, es la
# consecuencia esperada de no haber generado VERSION antes de
# empaquetar.
# NOTA (06/09/2026, revisión previa al lanzamiento): faltaba
# ('app/gui_web/web', 'app/gui_web/web') en `datas` -- sin esa
# entrada, un build empaquetado arranca sin la GUI v2 (pywebview
# busca `app/gui_web/web/index.html` relativo a `paths.base_dir()`,
# ver `app/gui_web/window.py`, y ese árbol de archivos -- HTML/CSS/
# JS -- nunca se copiaba adentro del build). Bug real, no una
# mejora opcional -- sin esto el .exe empaquetado no llega a
# mostrar ninguna pantalla. Los sprites (assets/pokemon_full,
# assets/gym_leaders, assets/pokemon_shuffle) sí estaban cubiertos
# porque cuelgan de `assets/`, que ya estaba en la lista.
datas = [('config.json', '.'), ('VERSION', '.'), ('assets', 'assets'), ('overlays', 'overlays'), ('panels', 'panels'), ('app/gui_web/web', 'app/gui_web/web'), ('releases/pkhex-bridge', 'releases/pkhex-bridge')]

# NOTA (18/09/2026, revisión previa al tag v0.3.0-alpha): faltaba
# empaquetar data/. Los catálogos estáticos curados (type_chart,
# gym_leaders*, move_data, *_descriptions, species_extra,
# pre_evolution_index, item_sprite_id_map, *_changes_rrss...) los
# leen los servicios con paths.path("data", ...) -- en un build sin
# esos JSON, Pokédex/Líderes/Movimientos no cargan. Se incluye todo
# data/*.json EXCEPTO el progreso real del usuario (badges,
# nuzlocke_*, team_overlay_settings): eso NUNCA se distribuye, cada
# instalación arranca con el suyo vacío (los servicios lo crean).
# Los cachés regenerables (species/location/ability/item/move_cache)
# sí van: evitan la primera espera al llamar al bridge PKHeX.
import os

_USER_PROGRESS_FILES = {"badges.json", "team_overlay_settings.json"}

for _name in sorted(os.listdir("data")):
    if not _name.endswith(".json"):
        continue

    if _name in _USER_PROGRESS_FILES or _name.startswith("nuzlocke"):
        continue

    datas.append((os.path.join("data", _name), "data"))

binaries = []
hiddenimports = []
tmp_ret = collect_all('ttkbootstrap')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['dexrelay_launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DexRelay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # DECISIÓN (09/09/2026, pendiente heredado desde FASE 6/25-08 --
    # ver sección 6/8 del roadmap): False, una sola ventana sin
    # consola de fondo. Se acepta el riesgo de quedar a ciegas ante
    # un fallo MUY temprano (antes de que la GUI llegue a cargar,
    # ej. DLL faltante o pywebview que no arranca) -- para cualquier
    # fallo posterior a eso, la pestaña "Logs" de la GUI v2 ya
    # muestra en vivo el mismo stdout/stderr que iría a la consola
    # (ver app/core/log_capture.py), así que la consola aparte había
    # quedado redundante para el caso normal.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DexRelay',
)

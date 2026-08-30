"""
Resolucion de rutas de DexRelay, consciente de si la app corre
desde el codigo fuente o empaquetada con PyInstaller (FASE 6,
29/08/2026 -- ver Documento Maestro seccion 21).

Antes, cada modulo calculaba la raiz del proyecto a mano con
`Path(__file__).resolve().parents[N]` (o directamente con rutas
relativas tipo "data/badges.json", que dependen de que el
directorio de trabajo actual sea la raiz del proyecto). Los dos
enfoques se rompen al empaquetar con PyInstaller:

- `__file__` dentro de un build congelado apunta a una carpeta
  temporal de extraccion, no a la estructura de carpetas real del
  proyecto -- sirve para encontrar recursos EMPAQUETADOS DENTRO
  del ejecutable, no archivos externos como el bridge PKHeX
  publicado aparte.
- El directorio de trabajo actual depende de como el usuario abra
  el .exe (doble click, acceso directo, simbolo del sistema) --
  no hay garantia de que sea la carpeta del propio ejecutable.

Este modulo centraliza el criterio: `base_dir()` siempre devuelve
la carpeta donde hay que buscar todo lo demas (config.json,
data/, overlays/, panels/, assets/, releases/) -- la carpeta del
proyecto en modo desarrollo, o la carpeta del propio .exe en un
build empaquetado. Se asume PyInstaller en modo --onedir (la
modalidad elegida para DexRelay, ver seccion 15/21 del Documento
Maestro): el .exe y sus datos conviven en la misma carpeta
persistente, a diferencia de --onefile, que extrae a una carpeta
temporal descartable en cada corrida y no es apta para guardar
config/datos de partida que tienen que sobrevivir entre sesiones.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """
    True si estamos corriendo dentro de un build de PyInstaller.
    """

    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    """
    Carpeta base para resolver todo lo que no sea codigo Python
    puro: config.json, data/, overlays/, panels/, assets/,
    releases/.
    """

    if is_frozen():
        return Path(sys.executable).resolve().parent

    # app/core/paths.py -> parents[2] es la raiz del proyecto
    return Path(__file__).resolve().parents[2]


def path(*parts: str) -> Path:
    """
    Atajo para `base_dir().joinpath(*parts)`.
    """

    return base_dir().joinpath(*parts)

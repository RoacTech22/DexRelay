from __future__ import annotations

import copy
import json
from pathlib import Path

from app.core import paths
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


# Nombre de archivo por juego (02/09/2026) -- antes de esto había
# un solo data/nuzlocke.json sin importar qué juego estuviera
# corriendo, lo que hacía que /overlay/nuzlocke mostrara la
# partida de Omega Ruby con Alpha Sapphire abierto (bug real
# reportado por el usuario) o viceversa. Un slug legible en vez
# del process_name crudo ("sango-1"/"sango-2") para que el nombre
# de archivo tenga sentido si alguien lo mira directo.
_GAME_STORAGE_SLUGS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: "alpha_sapphire",
    PROCESS_NAME_OMEGA_RUBY: "omega_ruby",
}


# Reglas por defecto de una partida Nuzlocke nueva (GUI v2, página
# Nuzlocke, 04/09/2026) -- editable de verdad desde la GUI
# (agregar/quitar/tildar, ver NuzlockeService.save_ruleset()), esto
# es solo el punto de partida la primera vez que se lee el archivo.
# Los `id` son fijos para las reglas de este set inicial -- una
# regla agregada a mano por el usuario después lleva un id nuevo
# (ver Api.nuzlocke_add_ruleset_rule() en app/gui_web/api.py).
#
# AJUSTE (09/09/2026, a pedido del usuario): de las 7 reglas, solo
# 3 vienen tildadas por defecto ahora (primer_encuentro,
# muerte_permanente, nickname_obligatorio) -- las demás quedan
# definidas (visibles y editables en el modal) pero destildadas de
# entrada. También se renombró "muerte_permanente" para que quede
# claro que aplica al Pokémon debilitado. "nickname_obligatorio" es
# nueva en este set por defecto -- ya existía como regla agregada a
# mano en el save real de Alpha Sapphire del usuario (id
# custom_..., ver Documento Maestro de esta sesión), ahora pasa a
# ser parte del set base para que Omega Ruby también la tenga sin
# tener que agregarla de nuevo a mano.
DEFAULT_RULESET = [
    {
        "id": "primer_encuentro",
        "label": "Solo el primer encuentro por ruta",
        "enabled": True,
    },
    {
        "id": "muerte_permanente",
        "label": "Muerte permanente del Pokémon debilitado",
        "enabled": True,
    },
    {
        "id": "objetos_encontrados",
        "label": "Solo objetos de curación encontrados",
        "enabled": False,
    },
    {
        "id": "nivel_maximo_lider",
        "label": "Nivel máximo según siguiente líder",
        "enabled": False,
    },
    {
        "id": "sin_tradeos",
        "label": "Sin tradeos",
        "enabled": False,
    },
    {
        "id": "sin_legendarios",
        "label": "Sin legendarios (opcional)",
        "enabled": False,
    },
    {
        "id": "nickname_obligatorio",
        "label": "Todos los pokemon deben llevar un nombre/nickname",
        "enabled": True,
    },
]


class NuzlockeStorage:
    """Persists the current Nuzlocke run (roster + graveyard) to disk."""

    def __init__(self, path: str | Path | None = None) -> None:
        # Sin path explícito, resuelve data/nuzlocke.json relativo
        # a la carpeta del proyecto o del .exe empaquetado -- ver
        # app/core/paths.py. Esto queda como el archivo "legacy"
        # (pre-multi-juego) -- Application ya no lo usa directo,
        # usa for_game(), pero se deja este comportamiento para no
        # romper tests/probes que instancian NuzlockeStorage() sin
        # argumentos.
        self.path = (
            Path(path) if path is not None else paths.path("data", "nuzlocke.json")
        )

    @classmethod
    def for_game(cls, process_name: str) -> "NuzlockeStorage":
        """
        Resuelve el archivo de guardado del juego indicado
        (`data/nuzlocke_alpha_sapphire.json` /
        `data/nuzlocke_omega_ruby.json`) -- cada juego tiene el
        suyo, para que el roster/cementerio de una partida no se
        mezcle con la del otro.

        Migración única: si el archivo nuevo todavía no existe
        pero SÍ existe el `data/nuzlocke.json` viejo (de antes de
        este cambio, cuando había uno solo para cualquier juego),
        se MUEVE (no se copia) como punto de partida.

        Bug real corregido (02/09/2026): la primera versión de esto
        copiaba (`read_text`/`write_text`) en vez de mover, así que
        el archivo viejo seguía existiendo después -- si el usuario
        después probaba el OTRO juego y ese archivo nuevo todavía
        no existía tampoco, la migración se disparaba DE NUEVO con
        el mismo `nuzlocke.json` viejo, y los dos juegos terminaban
        con una copia de los mismos datos (reportado por el
        usuario: los tres archivos mostraban la partida de Omega
        Ruby). Al mover en vez de copiar, el archivo viejo deja de
        existir apenas se usa una vez -- el segundo juego que lo
        busque ya no lo encuentra y arranca vacío de verdad, en vez
        de heredar los datos del primero.

        Si el proceso no es conocido, usa el nombre crudo como slug
        (no debería pasar en la práctica, pero mejor que reventar).
        """

        slug = _GAME_STORAGE_SLUGS.get(process_name, process_name)
        target_path = paths.path("data", f"nuzlocke_{slug}.json")
        legacy_path = paths.path("data", "nuzlocke.json")

        if not target_path.exists() and legacy_path.exists():
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                legacy_path.rename(target_path)
            except OSError:
                # Si la migración falla por lo que sea, seguimos
                # con un archivo nuevo vacío en vez de romper el
                # arranque -- no es peor que el estado antes de
                # este cambio.
                pass

        return cls(target_path)

    def load(self) -> dict:
        """
        Load the current Nuzlocke run, or an empty one if no file
        exists yet (first run).
        """

        if not self.path.exists():
            return {
                "roster": [],
                "graveyard": [],
                "encounters": [],
                "pending_encounters": [],
                "starter_assigned": False,
                # copy.deepcopy -- setdefault() más abajo hace lo
                # mismo para el caso "el archivo existe pero es de
                # antes de que existiera ruleset". Sin la copia,
                # todas las partidas nuevas compartirían la MISMA
                # lista en memoria y tildar una regla en una
                # afectaría a la otra.
                "ruleset": copy.deepcopy(DEFAULT_RULESET),
            }

        with self.path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        data.setdefault("roster", [])
        data.setdefault("graveyard", [])
        data.setdefault("encounters", [])
        data.setdefault("pending_encounters", [])
        data.setdefault("starter_assigned", False)
        data.setdefault("ruleset", copy.deepcopy(DEFAULT_RULESET))

        return data

    def save(self, data: dict) -> None:
        """Save the current Nuzlocke run as JSON."""

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")

from __future__ import annotations

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

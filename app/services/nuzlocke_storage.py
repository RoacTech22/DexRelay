from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime
from pathlib import Path

from app.core import paths
from app.core.atomic_write import write_json_atomic
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
# (ver Api.nuzlocke_add_ruleset_rule() en app/gui_web/api_nuzlocke.py).
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

    # Bloque 4.2 (guía siguiente versión, 23/09/2026): cuántos
    # respaldos conservar POR JUEGO antes de empezar a borrar los
    # más viejos -- 10 por defecto (sugerencia de la guía, sin
    # confirmar todavía con Ronald, ver "Decisiones abiertas" de la
    # guía). Un valor de clase, fácil de ajustar acá si decide otro
    # número.
    BACKUP_KEEP_COUNT = 10

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

    @classmethod
    def for_identity(
        cls,
        process_name: str,
        tid: int,
        sid: int,
        known_nicknames=None,
        data_dir: str | Path | None = None,
    ) -> "NuzlockeStorage":
        """
        Bloque 5 (guía siguiente versión, 24/09/2026): un archivo por
        PARTIDA, no solo por juego --
        `data/nuzlocke_<juego>_<tid>_<sid>.json`. Dos partidas del
        mismo juego (dos saves distintos) ya no mezclan roster,
        cementerio ni encuentros. TID y SID juntos (32 bits) para que
        dos entrenadores distintos casi nunca colisionen.

        Adopción del archivo por juego existente
        (`nuzlocke_<juego>.json`, de antes de este bloque): si el
        archivo de esta partida todavía no existe, se le MUEVE ese
        archivo (no se copia: mismo criterio que la migración de
        for_game(), una copia duplicaría datos) -- pero SOLO si
        pertenece a esta partida, cosa que se decide comparando los
        nicknames de su roster/cementerio contra los Pokémon que se
        ven ahora mismo (`known_nicknames`: iterable o función que
        lo devuelve; solo se llama si hace falta). Si no coincide (es
        de otra partida del mismo juego), NO se toca: queda esperando
        a que se cargue la partida a la que pertenece. Nunca borra
        nada.

        `data_dir` solo existe para poder probar esto sin tocar la
        carpeta real `data/`.
        """

        slug = _GAME_STORAGE_SLUGS.get(process_name, process_name)

        base = (
            Path(data_dir)
            if data_dir is not None
            else paths.path("data")
        )

        target_path = base / f"nuzlocke_{slug}_{tid}_{sid}.json"
        game_path = base / f"nuzlocke_{slug}.json"

        if not target_path.exists() and game_path.exists():
            known = (
                known_nicknames()
                if callable(known_nicknames)
                else known_nicknames
            )

            if cls._game_file_belongs_to(game_path, known):
                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    game_path.rename(target_path)
                except OSError:
                    # Sin poder mover el archivo, esta partida
                    # arranca con uno nuevo -- el viejo queda intacto.
                    pass

        return cls(target_path)

    @staticmethod
    def _game_file_belongs_to(game_path: Path, known_nicknames) -> bool:
        """
        ¿El archivo por juego `game_path` es de la partida que se ve
        ahora? Compara los nicknames de su roster+cementerio contra
        `known_nicknames` (party + cajas actuales). Exige coincidir
        con al menos min(2, cantidad) de ellos: con un solo nickname
        en común, dos partidas que nombraron igual a su inicial se
        confundirían. Un archivo sin ningún nickname (vacío) no se
        adopta: no hay nada que perder ni que reconocer.
        """

        if not known_nicknames:
            return False

        try:
            with game_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError):
            return False

        stored = {
            entry.get("nickname")
            for key in ("roster", "graveyard")
            for entry in data.get(key, [])
            if isinstance(entry, dict) and entry.get("nickname")
        }

        if not stored:
            return False

        required = min(2, len(stored))

        return len(stored & set(known_nicknames)) >= required

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
                # Bloque 4.4 (23/09/2026): archivo recién creado
                # (primera vez que se ve esta partida) -- el
                # Nuzlocke todavía no arrancó de verdad, ver el
                # comentario junto a `nuzlocke_started` en
                # NuzlockeService.update().
                "nuzlocke_started": False,
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

        # Bloque 4.4 (23/09/2026): el ARCHIVO YA EXISTÍA -- es una
        # partida que ya se venía trackeando antes de que existiera
        # este flag. Se la considera ya iniciada por defecto (True,
        # no False) para no bloquear de golpe el registro de
        # encuentros/muertes de una partida en curso -- decisión
        # explícita para no romper nada retroactivo (ver "Partidas
        # ya en curso" en el comentario de update()). Si el archivo
        # YA TRAE la clave (partida creada después de este bloque),
        # setdefault no la toca.
        data.setdefault("nuzlocke_started", True)

        return data

    def save(self, data: dict) -> None:
        """Save the current Nuzlocke run as JSON."""

        # Bloque 4.1 (23/09/2026): escritura atómica -- ver
        # app/core/atomic_write.py. Antes: open("w") + json.dump()
        # directo sobre el archivo final.
        write_json_atomic(self.path, data)

    def backup(self) -> Path | None:
        """
        Bloque 4.2 (guía siguiente versión, 23/09/2026): copia el
        archivo TAL COMO ESTÁ HOY en disco a data/backups/, con
        fecha y hora en el nombre, antes de una operación
        destructiva (borrar un encuentro, "Reiniciar todo" -- ver
        NuzlockeService.delete_encounter()/reset_all()). Progreso
        real de partida (regla 10 del Documento Maestro): sin esto,
        "no se puede deshacer" era literal.

        No respalda desde `self._data` en memoria -- copia el
        archivo real con `shutil.copy2` para no depender de que la
        memoria y el disco coincidan. Si el archivo todavía no
        existe (partida recién arrancada, nada que perder todavía),
        no hace nada.

        Conserva los últimos BACKUP_KEEP_COUNT respaldos de ESTE
        archivo (por juego, ya que cada juego tiene su propio
        NuzlockeStorage/path) y borra los más viejos -- el nombre
        con timestamp ISO ordena cronológicamente como texto, así
        que no hace falta parsear fechas para saber cuáles son los
        más viejos.
        """

        if not self.path.exists():
            return None

        backups_dir = self.path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backups_dir / f"{self.path.stem}.{timestamp}.json"

        # Si ya existe un backup con el mismo segundo (dos
        # operaciones destructivas seguidas muy rápido), se suma un
        # sufijo en vez de pisar el anterior.
        suffix = 2
        while backup_path.exists():
            backup_path = backups_dir / f"{self.path.stem}.{timestamp}-{suffix}.json"
            suffix += 1

        shutil.copy2(self.path, backup_path)

        self._prune_old_backups(backups_dir)

        return backup_path

    def _prune_old_backups(self, backups_dir: Path) -> None:
        prefix = f"{self.path.stem}."
        existing = sorted(
            backups_dir.glob(f"{prefix}*.json"),
            key=lambda backup_path: backup_path.name,
        )

        excess_count = len(existing) - self.BACKUP_KEEP_COUNT

        for old_backup in existing[: max(excess_count, 0)]:
            try:
                old_backup.unlink()
            except OSError:
                # Un backup que no se puede borrar (en uso, permisos)
                # no debería impedir que la operación destructiva
                # que disparó todo esto siga adelante.
                pass

    def list_backups(self) -> list[Path]:
        """
        Respaldos existentes de ESTE archivo, del más reciente al
        más viejo -- usado por la GUI para ofrecer "Restaurar
        último respaldo" (Bloque 4.2).
        """

        backups_dir = self.path.parent / "backups"

        if not backups_dir.exists():
            return []

        prefix = f"{self.path.stem}."

        return sorted(
            backups_dir.glob(f"{prefix}*.json"),
            key=lambda backup_path: backup_path.name,
            reverse=True,
        )

    def restore_latest_backup(self) -> bool:
        """
        Bloque 4.2: restaura el respaldo más reciente sobre el
        archivo actual (con os.replace() vía write_json_atomic, así
        que también queda a salvo de un corte a mitad de camino).
        Devuelve False sin tocar nada si no hay ningún respaldo.
        """

        backups = self.list_backups()

        if not backups:
            return False

        latest_backup = backups[0]

        with latest_backup.open("r", encoding="utf-8") as file:
            data = json.load(file)

        write_json_atomic(self.path, data)

        return True


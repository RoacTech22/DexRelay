from __future__ import annotations

import json
from pathlib import Path

from app.core import paths
from app.services.pkhex.bridge import PKHeXBridge


class MoveCatalog:
    """
    Lista completa {id, name} de movimientos conocidos por PKHeX,
    en español (mismo paquete de GameStrings que species/ítems/
    habilidades -- ver HandleMoveList() en Program.cs).

    Mismo patrón exacto que ItemCatalog/AbilityCatalog: se resuelve
    UNA vez vía el bridge (acción 'move_list') y se cachea en
    memoria y en disco (data/move_cache.json) -- los nombres de
    movimiento no cambian.

    Fase E (09/09/2026, soporte hackroom Rising Ruby/Sinking
    Sapphire) -- reemplaza MOVE_NAME_ES (diccionario a mano con 64
    movimientos, en app.js/leader_team_window.js, pensado solo para
    el juego base) por el mismo mecanismo ya confirmado 100%
    correcto para nombres de movimiento (ver
    tools/probes/verificar_nombres_movimiento_es.py, 09/09/2026).
    """

    def __init__(
        self,
        bridge=None,
        cache_path=None,
    ):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        self.cache_path = (
            Path(cache_path)
            if cache_path is not None
            else paths.path("data", "move_cache.json")
        )
        self._moves = None
        self._by_id = None

    def _ensure_loaded(self):

        if self._moves is not None:
            return

        cached = self._load_from_disk()

        if cached:
            self._moves = cached
            self._by_id = {
                entry["id"]: entry["name"] for entry in cached
            }
            return

        try:
            result = self.bridge.move_list()
            moves = result.get("moves", [])

        except Exception:
            moves = []

        self._moves = moves
        self._by_id = {
            entry["id"]: entry["name"] for entry in moves
        }

        if moves:
            self._save_to_disk(moves)

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...]. Vacía si el
        bridge no está disponible y tampoco hay caché en disco --
        nunca lanza. Un resultado vacío NO se cachea en memoria a
        propósito (mismo motivo que ItemCatalog: el bridge puede
        tardar unos segundos en arrancar la primera vez).
        """

        self._ensure_loaded()

        return self._moves or []

    def get_name(self, move_id):
        """
        Nombre en español de un movimiento puntual, o None si no
        se pudo resolver (bridge caído, id fuera de rango) -- nunca
        inventa un nombre de respaldo.
        """

        self._ensure_loaded()

        if not self._by_id:
            return None

        return self._by_id.get(move_id)

    def _load_from_disk(self):

        if not self.cache_path.exists():
            return None

        try:

            with self.cache_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except Exception:
            return None

    def _save_to_disk(self, moves):

        try:

            self.cache_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self.cache_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as file:

                json.dump(
                    moves,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write("\n")

        except Exception:
            pass

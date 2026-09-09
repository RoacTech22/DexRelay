from __future__ import annotations

import json
from pathlib import Path

from app.core import paths
from app.services.pkhex.bridge import PKHeXBridge


class ItemCatalog:
    """
    Lista completa {id, name} de ítems conocidos por PKHeX, en
    español (mismo paquete de GameStrings que
    species/movimientos/habilidades -- ver HandleItemList() en
    Program.cs).

    Mismo patrón exacto que SpeciesCatalog: se resuelve UNA vez vía
    el bridge (acción 'item_list') y se cachea en memoria y en
    disco (data/item_cache.json) -- los nombres de ítem no cambian.

    07/09/2026 (roadmap 4.2, a pedido del usuario: "cerrá también
    con los nombres/sprite de los ítems") -- usado para completar
    las evoluciones que dependen de un objeto puntual
    (UseItem/TradeHeldItem/LevelUpHeldItemDay/Night), que hasta
    ahora mostraban el texto genérico del método sin decir CUÁL
    objeto hacía falta (ver evolution_translations.py).
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
            else paths.path("data", "item_cache.json")
        )
        self._items = None
        self._by_id = None

    def _ensure_loaded(self):

        if self._items is not None:
            return

        cached = self._load_from_disk()

        if cached:
            self._items = cached
            self._by_id = {
                entry["id"]: entry["name"] for entry in cached
            }
            return

        try:
            result = self.bridge.item_list()
            items = result.get("items", [])

        except Exception:
            items = []

        self._items = items
        self._by_id = {
            entry["id"]: entry["name"] for entry in items
        }

        if items:
            self._save_to_disk(items)

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...]. Vacía si el
        bridge no está disponible y tampoco hay caché en disco --
        nunca lanza. Un resultado vacío NO se cachea en memoria a
        propósito (mismo motivo que SpeciesCatalog: el bridge
        puede tardar unos segundos en arrancar la primera vez).
        """

        self._ensure_loaded()

        return self._items or []

    def get_name(self, item_id):
        """
        Nombre en español de un ítem puntual, o None si no se
        pudo resolver (bridge caído, id fuera de rango) -- nunca
        inventa un nombre de respaldo.
        """

        self._ensure_loaded()

        if not self._by_id:
            return None

        return self._by_id.get(item_id)

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

    def _save_to_disk(self, items):

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
                    items,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write("\n")

        except Exception:
            pass

from __future__ import annotations

import json
from pathlib import Path

from app.core import paths
from app.services.pkhex.bridge import PKHeXBridge


class AbilityCatalog:
    """
    Lista completa {id, name} de habilidades conocidas por PKHeX,
    en español (mismo paquete de GameStrings que species/
    movimientos/ítems -- ver HandleAbilityList() en Program.cs).

    Mismo patrón exacto que ItemCatalog: se resuelve UNA vez vía el
    bridge (acción 'ability_list') y se cachea en memoria y en
    disco (data/ability_cache.json) -- los nombres de habilidad no
    cambian.

    Fase E (09/09/2026, soporte hackroom Rising Ruby/Sinking
    Sapphire) -- hacía falta reemplazar GYM_ABILITY_NAMES_ES (un
    diccionario a mano con las 24 habilidades del juego base) por
    algo que cubra CUALQUIER habilidad real de Gen 6, porque el
    hack usa muchas más de las 24 originales y quedaban mostrando
    el nombre en inglés en la pestaña Líderes.
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
            else paths.path("data", "ability_cache.json")
        )
        self._abilities = None
        self._by_id = None

    def _ensure_loaded(self):

        if self._abilities is not None:
            return

        cached = self._load_from_disk()

        if cached:
            self._abilities = cached
            self._by_id = {
                entry["id"]: entry["name"] for entry in cached
            }
            return

        try:
            result = self.bridge.ability_list()
            abilities = result.get("abilities", [])

        except Exception:
            abilities = []

        self._abilities = abilities
        self._by_id = {
            entry["id"]: entry["name"] for entry in abilities
        }

        if abilities:
            self._save_to_disk(abilities)

    def list_all(self):
        """
        Devuelve la lista [{'id', 'name'}, ...]. Vacía si el
        bridge no está disponible y tampoco hay caché en disco --
        nunca lanza. Un resultado vacío NO se cachea en memoria a
        propósito (mismo motivo que ItemCatalog: el bridge puede
        tardar unos segundos en arrancar la primera vez).
        """

        self._ensure_loaded()

        return self._abilities or []

    def get_name(self, ability_id):
        """
        Nombre en español de una habilidad puntual, o None si no
        se pudo resolver (bridge caído, id fuera de rango) -- nunca
        inventa un nombre de respaldo.
        """

        self._ensure_loaded()

        if not self._by_id:
            return None

        return self._by_id.get(ability_id)

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

    def _save_to_disk(self, abilities):

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
                    abilities,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write("\n")

        except Exception:
            pass

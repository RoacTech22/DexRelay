from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.core import paths


# Sets de sprites ya existentes en el proyecto (25/08 - 05/09/2026)
# que el editor del Team Overlay puede elegir -- ninguno es nuevo,
# los tres ya se sirven para otras páginas/paneles:
#   - "team": overlays/team/sprites/ (el de siempre, bordes
#     blancos/glow, el que ya usa este mismo overlay).
#   - "pokemon": assets/pokemon_full/, servido en
#     /sprites/pokemon/{id}.png (página Pokémon de la GUI).
#   - "shuffle": assets/pokemon_shuffle/, servido en
#     /sprites/pokemon_shuffle/{NNN}.png, 3 dígitos (tabla de
#     Encuentros por Ruta de la página Nuzlocke).
SPRITE_SETS = ("team", "pokemon", "shuffle")

DEFAULT_SETTINGS = {
    "show_hp": True,
    "show_level": True,
    "show_nickname": True,
    "sprite_set": "team",
}


class TeamOverlaySettings:
    """
    Preferencias de qué elementos muestra el Team Overlay (barra
    de HP, nivel, nickname) y qué set de sprites usa -- editor de
    la GUI v2, página Overlays (05/09/2026).

    Instancia ÚNICA compartida entre `Api` (la GUI las lee/escribe
    directo en memoria vía el puente pywebview, sin pasar por
    HTTP -- así el editor funciona aunque el HTTP server esté
    detenido) y `HTTPServer` (el overlay real, corriendo en un
    navegador/OBS aparte, solo puede leerlas vía
    GET /api/team-overlay-settings). Mismo patrón que
    `NuzlockeService` compartido entre `Runtime`/`HTTPServer`.

    Se persisten en disco (`data/team_overlay_settings.json`) para
    sobrevivir a un reinicio de DexRelay -- mismo criterio que
    `nuzlocke_storage.py`.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (
            paths.base_dir() / "data" / "team_overlay_settings.json"
        )
        self._lock = Lock()
        self._settings = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            # Archivo corrupto/inaccesible -- se sigue con los
            # valores por defecto en vez de tirar la app abajo al
            # arrancar.
            return

        if not isinstance(data, dict):
            return

        with self._lock:
            for key, default_value in DEFAULT_SETTINGS.items():
                if key not in data:
                    continue

                value = data[key]

                if key == "sprite_set":
                    if value in SPRITE_SETS:
                        self._settings[key] = value
                elif isinstance(default_value, bool):
                    self._settings[key] = bool(value)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._settings, fh, indent=2, ensure_ascii=False)

    def get(self) -> dict:
        with self._lock:
            return dict(self._settings)

    def update(self, patch: dict) -> dict:
        """
        Aplica solo las claves válidas presentes en `patch` (ignora
        el resto en silencio -- mismo criterio permisivo que
        `NuzlockeService.save_ruleset()`) y persiste. Devuelve el
        estado completo ya actualizado.
        """

        if not isinstance(patch, dict):
            return self.get()

        with self._lock:
            if "show_hp" in patch:
                self._settings["show_hp"] = bool(patch["show_hp"])

            if "show_level" in patch:
                self._settings["show_level"] = bool(patch["show_level"])

            if "show_nickname" in patch:
                self._settings["show_nickname"] = bool(
                    patch["show_nickname"]
                )

            if patch.get("sprite_set") in SPRITE_SETS:
                self._settings["sprite_set"] = patch["sprite_set"]

            snapshot = dict(self._settings)

        self._save()

        return snapshot

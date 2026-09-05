from __future__ import annotations

from app.services.pkhex.bridge import PKHeXBridge
from app.services.save_file_locator import find_save_file


class PlaytimeService:
    """
    Tiempo de juego real (GUI v2, página Nuzlocke, 04/09/2026) --
    a diferencia de todo lo demás que lee DexRelay, esto NO sale de
    la memoria RAM en vivo de Azahar (UDP, ciclo de 200ms): sale
    del archivo de guardado en disco, así que solo se actualiza
    cuando el juego GUARDA la partida, no en tiempo real. Decisión
    tomada con el usuario el 04/09/2026 -- alternativa a investigar
    una dirección de memoria nueva con Cheat Engine, que no hacía
    falta acá porque PKHeX ya sabe leer este campo de un SaveFile
    completo.

    Caché por `mtime` del archivo (no por tiempo): releer el
    archivo entero y volver a golpear el bridge en cada poll de la
    GUI (1-2s) sería trabajo desperdiciado la enorme mayoría de las
    veces -- el archivo solo cambia cuando el jugador guarda, que
    es mucho más esporádico. Comparar `mtime` contra la última
    lectura evita eso sin necesitar ningún timer propio.
    """

    def __init__(self, bridge=None) -> None:
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        # Por process_name -- Alpha Sapphire y Omega Ruby tienen
        # cada uno su propio archivo de guardado, no hay que
        # mezclar la caché de uno con la del otro (mismo criterio
        # que NuzlockeStorage.for_game()).
        self._cache: dict[str, dict] = {}

    def get_playtime(self, process_name: str | None) -> dict:
        """
        Devuelve siempre un dict con "available" (bool). Si es
        `True`, también trae "hours"/"minutes"/"seconds". Si es
        `False`, trae "reason" (texto corto para mostrar en la
        GUI, no un mensaje de error técnico) -- nunca lanza una
        excepción hacia el llamador, esto es una tarjeta
        informativa de la GUI, no algo que deba poder romper el
        resto de la página si falla.
        """

        if process_name is None:
            return {
                "available": False,
                "reason": "Sin juego detectado todavía.",
            }

        save_path = find_save_file(process_name)

        if save_path is None:
            return {
                "available": False,
                "reason": (
                    "No se encontró el archivo de guardado de "
                    "Azahar en disco."
                ),
            }

        try:
            mtime = save_path.stat().st_mtime
        except OSError:
            return {
                "available": False,
                "reason": (
                    "No se pudo leer el archivo de guardado."
                ),
            }

        cached = self._cache.get(process_name)

        if (
            cached is not None
            and cached.get("path") == str(save_path)
            and cached.get("mtime") == mtime
        ):
            return cached["result"]

        try:
            info = self.bridge.save_info(save_path)
        except RuntimeError as error:
            # El bridge puede fallar de forma transitoria (por
            # ejemplo, si todavía está arrancando) -- mismo
            # criterio de "no romper la página por esto" que el
            # resto de la GUI. No se cachea un fallo transitorio,
            # así el próximo poll reintenta solo.
            return {
                "available": False,
                "reason": f"Bridge PKHeX: {error}",
            }

        result = {
            "available": True,
            "hours": info.get("playedHours", 0),
            "minutes": info.get("playedMinutes", 0),
            "seconds": info.get("playedSeconds", 0),
        }

        self._cache[process_name] = {
            "path": str(save_path),
            "mtime": mtime,
            "result": result,
        }

        return result

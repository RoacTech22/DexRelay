"""
Ventana principal de la GUI v2 de DexRelay (pywebview).

Bloque 1: esqueleto -- Bienvenida, Espera, Conectado, y el shell
principal (sidebar + Dashboard placeholder, resto de las páginas
"Próximamente" hasta sus bloques respectivos). Reemplaza a
`app/gui/app_window.py` (Tkinter/ttkbootstrap) como punto de
entrada de `app/main.py` -- esa GUI vieja no se borra, queda en el
proyecto sin usarse (mismo criterio que con los probes: documenta
lo que ya se probó, no estorba).

A diferencia de la GUI Tkinter (que armaba pantallas como Frames
en Python), acá toda la navegación entre pantallas vive del lado
JS (`web/js/app.js`) -- esta clase solo crea la ventana nativa,
apunta a `web/index.html`, y conecta el bridge `Api`
(`app/gui_web/api.py`).

Modo desarrollo (31/08/2026): mientras la app NO esté empaquetada
con PyInstaller (`paths.is_frozen()` en `False`, o sea, corriendo
desde el código fuente), se activan dos cosas para poder iterar
sobre `web/` viendo el resultado sin reiniciar DexRelay entero
(y sin perder la conexión con Azahar cada vez, que sigue viva del
lado de Python -- solo se recarga la página):

1. `debug=True` en `webview.start()` -- habilita clic derecho >
   "Inspeccionar" en la ventana, las DevTools de siempre para
   tocar CSS en vivo y ver el resultado al toque antes de pasarlo
   al archivo real.
2. Un hilo liviano que vigila `web/` por cambios (comparando
   `mtime` de cada archivo cada medio segundo, sin dependencias
   nuevas) y llama `location.reload()` en la ventana apenas
   detecta que algo cambió -- guardás `style.css` (o cualquier
   archivo de `web/`) y la ventana se refresca sola.

En un build empaquetado, ninguna de las dos cosas se activa --
"congela" el criterio para no dejar DevTools accesibles ni un
hilo de polling de archivos corriendo en la versión que usa el
streamer en vivo.
"""

from __future__ import annotations

import threading
import time

import webview

from app.core import paths
from app.gui_web.api import Api

WINDOW_TITLE = "DexRelay"
DEFAULT_WIDTH = 1180
DEFAULT_HEIGHT = 800

# Mínimo de ventana (02/09/2026, a pedido del usuario): 844px. El
# máximo (1366px) ya NO se aplica acá -- pywebview no tiene un
# `max_size` nativo, y recortarlo a mano con el evento `resized`
# (ver versión anterior de este archivo) quedaba poco prolijo. En
# su lugar, el máximo vive en CSS (`.content { max-width: 1366px }`,
# ver style.css) -- la ventana nativa se puede redimensionar
# libre, y es el área de contenido la que deja de crecer pasado
# ese ancho, centrada con el espacio sobrante a los costados.
MIN_WIDTH = 844
MIN_HEIGHT = 480
BACKGROUND_COLOR = "#0a0e18"

DEV_MODE = not paths.is_frozen()
DEV_RELOAD_POLL_SECONDS = 0.5


class AppWindow:
    def __init__(self, application) -> None:
        self.app = application
        self._api = Api(application)

        # En modo desarrollo, paths.base_dir() es la raíz del
        # proyecto -- app/gui_web/web/index.html cuelga de ahí
        # directo. En un build de PyInstaller, esta carpeta tiene
        # que viajar empaquetada como recurso de datos
        # (--add-data), igual que overlays/ y panels/ -- pendiente
        # actualizar DexRelay.spec cuando se retome el empaquetado
        # de esta GUI nueva (Documento Maestro, plan del
        # 30/08/2026: primero cerrar los bloques de la GUI, después
        # empaquetar).
        self._web_dir = (
            paths.base_dir() / "app" / "gui_web" / "web"
        )
        self._index_path = self._web_dir / "index.html"

        self.window = webview.create_window(
            WINDOW_TITLE,
            url=str(self._index_path),
            js_api=self._api,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_size=(MIN_WIDTH, MIN_HEIGHT),
            background_color=BACKGROUND_COLOR,
        )

        self.window.events.closing += self._on_close

        self._reload_watch_running = False

    def _on_close(self) -> None:
        self._reload_watch_running = False

        if self.app.running:
            self.app.stop()

    def run(self) -> None:
        if DEV_MODE:
            self._start_dev_reload_watcher()
            print(
                "GUI en modo desarrollo: DevTools disponibles "
                "(clic derecho > Inspeccionar) y auto-recarga "
                f"activa sobre {self._web_dir}"
            )

        webview.start(debug=DEV_MODE)

    # -----------------------------------------------------------
    # Modo desarrollo -- auto-recarga al detectar cambios en web/
    # -----------------------------------------------------------

    def _start_dev_reload_watcher(self) -> None:
        self._reload_watch_running = True

        thread = threading.Thread(
            target=self._dev_reload_loop,
            name="DexRelayGuiDevReload",
            daemon=True,
        )
        thread.start()

    def _dev_reload_loop(self) -> None:
        last_snapshot = self._snapshot_web_dir()

        while self._reload_watch_running:
            time.sleep(DEV_RELOAD_POLL_SECONDS)

            snapshot = self._snapshot_web_dir()

            if snapshot != last_snapshot:
                last_snapshot = snapshot

                try:
                    self.window.evaluate_js("location.reload()")
                except Exception:
                    # La ventana pudo haberse cerrado justo entre
                    # el chequeo y el reload -- no es un error real
                    # que valga la pena reportar acá.
                    pass

    def _snapshot_web_dir(self) -> dict:
        snapshot = {}

        for file_path in self._web_dir.rglob("*"):
            if not file_path.is_file():
                continue

            try:
                snapshot[str(file_path)] = file_path.stat().st_mtime
            except OSError:
                continue

        return snapshot


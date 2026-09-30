"""
Orquestador de pantallas de DexRelay (FASE 4).

Un único `ttk.Window` real -- las "pantallas" (Bienvenida, Espera,
Principal) son Frames que se muestran/destruyen dentro de esa
misma ventana. Reemplaza el enfoque anterior donde `MainWindow`
era directamente la ventana raíz (ver Documento Maestro sección
15 para el historial de la GUI).
"""

from __future__ import annotations

import ttkbootstrap as ttk

from app.gui.main_window import MainWindow
from app.gui.waiting_screen import WaitingScreen
from app.gui.welcome_screen import WelcomeScreen

SMALL_GEOMETRY = "480x640"
MAIN_GEOMETRY = "480x900"


class AppWindow:
    def __init__(self, application) -> None:
        self.app = application
        self._main_window: MainWindow | None = None
        self._current_screen = None

        self.window = ttk.Window(
            title="DexRelay",
            themename="darkly",
            resizable=(True, True),
        )
        self.window.geometry(SMALL_GEOMETRY)
        self.window.minsize(420, 480)

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._show_welcome()

    # ---------------------------------------------------------------
    # Navegación entre pantallas
    # ---------------------------------------------------------------

    def _clear_screen(self) -> None:
        if self._current_screen is not None:
            self._current_screen.destroy()
            self._current_screen = None

    def _show_welcome(self) -> None:
        self._clear_screen()
        self.window.geometry(SMALL_GEOMETRY)
        self.window.minsize(420, 480)

        self._current_screen = WelcomeScreen(
            self.window,
            on_start=self._show_waiting,
        )
        self._current_screen.pack(fill="both", expand=True)

    def _show_waiting(self, process_name: str) -> None:
        # El proceso a buscar se elige acá, no en config.json --
        # se pisa en caliente sobre el reader ya construido (mutar
        # el atributo alcanza, find_game_process() lo relee en
        # cada intento de reconexión) y se persiste a disco para
        # que la próxima vez que se abra DexRelay recuerde la
        # elección. Ver Documento Maestro sección 14/17 sobre
        # PROCESS_NAME_ALPHA_SAPPHIRE/PROCESS_NAME_OMEGA_RUBY.
        self.app.reader.process_name = process_name
        self.app.config.set("azahar", "process_name", value=process_name)
        self.app.config.save()

        self._clear_screen()
        self.window.geometry(SMALL_GEOMETRY)

        self._current_screen = WaitingScreen(
            self.window,
            self.app,
            on_connected=self._show_main,
            on_cancel=self._show_welcome,
        )
        self._current_screen.pack(fill="both", expand=True)

    def _show_main(self) -> None:
        self._clear_screen()
        self.window.geometry(MAIN_GEOMETRY)
        self.window.minsize(420, 640)

        container = ttk.Frame(self.window)
        container.pack(fill="both", expand=True)

        self._main_window = MainWindow(
            self.app,
            window=self.window,
            container=container,
            on_back_to_welcome=self._back_to_welcome,
        )
        self._current_screen = container

    def _back_to_welcome(self) -> None:
        if self.app.running:
            self.app.stop()

        if self._main_window is not None:
            self._main_window.restore_log_redirect()
            self._main_window = None

        self._show_welcome()

    # ---------------------------------------------------------------
    # Cierre
    # ---------------------------------------------------------------

    def _on_close(self) -> None:
        if self.app.running:
            self.app.stop()

        if self._main_window is not None:
            self._main_window.restore_log_redirect()

        self.window.destroy()

    def run(self) -> None:
        self.window.mainloop()

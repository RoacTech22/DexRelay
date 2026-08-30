"""
Pantalla de espera de DexRelay (FASE 4).

Se muestra después de elegir la versión del juego en la
bienvenida. Arranca `Application` (Runtime + HTTPServer) y espera
a que `state.azahar_connected` se ponga en `True` -- el propio
Runtime ya hace la detección/reconexión con Azahar en su loop de
~200ms (Documento Maestro, sección 11), así que esta pantalla
solo consulta el estado, no reimplementa nada de esa lógica.
"""

from __future__ import annotations

import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY

POLL_INTERVAL_MS = 300


class WaitingScreen(ttk.Frame):
    def __init__(self, container, app, on_connected, on_cancel) -> None:
        super().__init__(container)
        self.app = app
        self.on_connected = on_connected
        self.on_cancel = on_cancel
        self._cancelled = False

        self._build()
        self._start_and_poll()

    def _build(self) -> None:
        wrapper = ttk.Frame(self, padding=32)
        wrapper.pack(fill="both", expand=True)

        ttk.Label(
            wrapper,
            text="Esperando a Azahar...",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(48, 12))

        ttk.Label(
            wrapper,
            text=(
                "Abrí el emulador Azahar con el juego cargado.\n"
                "Te vamos a conectar automáticamente apenas lo\n"
                "detectemos -- no hace falta hacer nada más acá."
            ),
            justify="center",
            bootstyle=SECONDARY,
        ).pack(pady=(0, 28))

        self.progress = ttk.Progressbar(
            wrapper,
            mode="indeterminate",
            length=240,
        )
        self.progress.pack(pady=(0, 28))
        self.progress.start(12)

        ttk.Button(
            wrapper,
            text="Cancelar",
            bootstyle=SECONDARY,
            command=self._cancel,
        ).pack()

    def _start_and_poll(self) -> None:
        if not self.app.running:
            self.app.start()

        self._poll()

    def _poll(self) -> None:
        if self._cancelled:
            return

        if self.app.state.azahar_connected:
            self.progress.stop()
            self.on_connected()
            return

        self.after(POLL_INTERVAL_MS, self._poll)

    def _cancel(self) -> None:
        self._cancelled = True
        self.progress.stop()

        if self.app.running:
            self.app.stop()

        self.on_cancel()

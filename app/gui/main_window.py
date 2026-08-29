"""
Ventana principal de DexRelay (FASE 4).

Ocupa el hilo principal con su propio mainloop (Tkinter/
ttkbootstrap) mientras el Runtime realtime y el HTTPServer siguen
corriendo en sus hilos de fondo -- esto ya estaba preparado desde
la decisión de concurrencia de la sección 18 del Documento
Maestro (Application.run() dejó libre el hilo principal
justamente para esto).

Simplificación deliberada de esta primera versión: "Lector"
(Runtime) y "Servidor HTTP" se inician/detienen juntos, porque
así ya funciona `Application.start()`/`stop()` -- separarlos en
controles independientes (como sugiere el mockup original de la
sección 15) es una extensión futura, no una necesidad para
reemplazar el uso actual de `main.py` a mano. No se tocó
`Application` para esta primera versión.

Arranque manual a propósito: al abrir la ventana NO se inicia el
lector/servidor solo -- el usuario lo hace con el botón "Iniciar
Lector", igual que el mockup de la sección 15 lo plantea como una
acción explícita.
"""

from __future__ import annotations

import webbrowser

import ttkbootstrap as ttk
from ttkbootstrap.constants import DANGER, SECONDARY, SUCCESS, WARNING

POLL_INTERVAL_MS = 500
BADGE_TOTAL = 8


class MainWindow:
    def __init__(self, application) -> None:
        self.app = application

        self.window = ttk.Window(
            title="DexRelay",
            themename="darkly",
            resizable=(False, False),
        )
        self.window.geometry("440x560")

        self._build_azahar_section()
        self._build_server_section()
        self._build_overlays_section()
        self._build_nuzlocke_section()

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self._on_close,
        )

        self._poll_state()

    # ---------------------------------------------------------------
    # Construcción de secciones
    # ---------------------------------------------------------------

    def _build_azahar_section(self) -> None:
        frame = ttk.Labelframe(
            self.window,
            text="AZAHAR",
            padding=12,
        )
        frame.pack(fill="x", padx=12, pady=(12, 6))

        self.azahar_status_label = ttk.Label(
            frame,
            text="● Detenido",
            bootstyle=SECONDARY,
        )
        self.azahar_status_label.pack(anchor="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))

        self.start_button = ttk.Button(
            buttons,
            text="Iniciar Lector",
            command=self._start_runtime,
            bootstyle=SUCCESS,
        )
        self.start_button.pack(
            side="left",
            expand=True,
            fill="x",
            padx=(0, 4),
        )

        self.stop_button = ttk.Button(
            buttons,
            text="Detener Lector",
            command=self._stop_runtime,
            bootstyle=DANGER,
        )
        self.stop_button.pack(
            side="left",
            expand=True,
            fill="x",
            padx=(4, 0),
        )

    def _build_server_section(self) -> None:
        frame = ttk.Labelframe(
            self.window,
            text="HTTP SERVER",
            padding=12,
        )
        frame.pack(fill="x", padx=12, pady=6)

        host, port = self._server_address()

        self.server_status_label = ttk.Label(
            frame,
            text=f"● Inactivo — {host}:{port}",
            bootstyle=SECONDARY,
        )
        self.server_status_label.pack(anchor="w")

    def _build_overlays_section(self) -> None:
        frame = ttk.Labelframe(
            self.window,
            text="OVERLAYS (OBS)",
            padding=12,
        )
        frame.pack(fill="x", padx=12, pady=6)

        base = self._server_base_url()

        overlays = [
            ("Team", f"{base}/overlay/team"),
            ("Badges", f"{base}/overlay/badges"),
            ("Nuzlocke", f"{base}/overlay/nuzlocke"),
        ]

        for name, url in overlays:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=3)

            ttk.Label(
                row,
                text=name,
                width=9,
            ).pack(side="left")

            entry = ttk.Entry(row)
            entry.insert(0, url)
            entry.configure(state="readonly")
            entry.pack(
                side="left",
                expand=True,
                fill="x",
                padx=4,
            )

            ttk.Button(
                row,
                text="Copiar",
                width=8,
                command=lambda u=url: self._copy_to_clipboard(u),
            ).pack(side="left")

    def _build_nuzlocke_section(self) -> None:
        frame = ttk.Labelframe(
            self.window,
            text="NUZLOCKE",
            padding=12,
        )
        frame.pack(fill="x", padx=12, pady=6)

        self.nuzlocke_stats_label = ttk.Label(
            frame,
            text="Capturados: 0   Muertos: 0   Medallas: 0/8",
        )
        self.nuzlocke_stats_label.pack(anchor="w")

        ttk.Button(
            frame,
            text="Abrir Tracker",
            command=self._open_tracker_panel,
        ).pack(fill="x", pady=(10, 0))

    # ---------------------------------------------------------------
    # Acciones
    # ---------------------------------------------------------------

    def _start_runtime(self) -> None:
        if not self.app.running:
            self.app.start()

    def _stop_runtime(self) -> None:
        if self.app.running:
            self.app.stop()

    def _open_tracker_panel(self) -> None:
        webbrowser.open(f"{self._server_base_url()}/panel/nuzlocke")

    def _copy_to_clipboard(self, text: str) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(text)

    # ---------------------------------------------------------------
    # Polling de estado (lee ApplicationState, no lo escribe --
    # mismo criterio de thread-safety ya documentado en la sección
    # 18: asignaciones simples son atómicas a nivel del GIL, peor
    # caso es un frame de estado ligeramente desactualizado)
    # ---------------------------------------------------------------

    def _poll_state(self) -> None:
        state = self.app.state

        if state.azahar_connected:
            self.azahar_status_label.configure(
                text="● Detectado / Conectado",
                bootstyle=SUCCESS,
            )
        elif self.app.running:
            self.azahar_status_label.configure(
                text="● Buscando Azahar...",
                bootstyle=WARNING,
            )
        else:
            self.azahar_status_label.configure(
                text="● Detenido",
                bootstyle=SECONDARY,
            )

        host, port = self._server_address()

        if self.app.running:
            self.server_status_label.configure(
                text=f"● Activo — {host}:{port}",
                bootstyle=SUCCESS,
            )
        else:
            self.server_status_label.configure(
                text=f"● Inactivo — {host}:{port}",
                bootstyle=SECONDARY,
            )

        nuzlocke = state.nuzlocke or {}
        roster = nuzlocke.get("roster", []) or []
        graveyard = nuzlocke.get("graveyard", []) or []

        badges = state.badges or {}
        badge_count = (
            badges.get("count", 0)
            if isinstance(badges, dict)
            else 0
        )

        self.nuzlocke_stats_label.configure(
            text=(
                f"Capturados: {len(roster) + len(graveyard)}   "
                f"Muertos: {len(graveyard)}   "
                f"Medallas: {badge_count}/{BADGE_TOTAL}"
            )
        )

        self.window.after(POLL_INTERVAL_MS, self._poll_state)

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def _server_address(self) -> tuple[str, int]:
        return self.app.http_server.host, self.app.http_server.port

    def _server_base_url(self) -> str:
        host, port = self._server_address()
        return f"http://{host}:{port}"

    def _on_close(self) -> None:
        if self.app.running:
            self.app.stop()
        self.window.destroy()

    def run(self) -> None:
        self.window.mainloop()

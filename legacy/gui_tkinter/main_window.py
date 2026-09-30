"""
Pantalla principal de DexRelay (FASE 4).

Ya no es dueña de la ventana raíz -- desde que existe el flujo de
bienvenida (`app/gui/app_window.py`), `MainWindow` recibe la
ventana (`window`, para `.after()`/clipboard/mainloop) y un
contenedor (`container`, un Frame donde empaquetar sus secciones)
por separado, para poder convivir con las otras pantallas
(Bienvenida, Espera) dentro del mismo `ttk.Window`. También recibe
un callback opcional `on_back_to_welcome` -- si se pasa, se
muestra un botón "◀ Volver a Bienvenida" arriba de todo; el
detener el lector y restaurar los logs antes de volver lo maneja
`AppWindow._back_to_welcome()`, no esta clase.

Decisión explícita del usuario (29/08/2026): "Lector" (Runtime) y
"Servidor HTTP" se mantienen en un solo control combinado, no se
separan -- así ya funciona `Application.start()`/`stop()` y no
hay necesidad real de más granularidad por ahora. No cambiar esto
sin instrucción nueva.

Secciones: AZAHAR, HTTP SERVER, OVERLAYS, NUZLOCKE, CONFIGURACIÓN
(edita config.json, cambios aplican al reiniciar DexRelay -- no
hay hot-reload, `Application` ya está construida con los valores
viejos) y LOGS (redirige stdout/stderr a un Text widget, ver
`_StreamToLogWidget` más abajo -- DexRelay no tiene módulo
`logging` todavía, solo `print()`).
"""

from __future__ import annotations

import sys
import tkinter as tk
import webbrowser

import ttkbootstrap as ttk
from ttkbootstrap.constants import DANGER, SECONDARY, SUCCESS, WARNING

POLL_INTERVAL_MS = 500
BADGE_TOTAL = 8
MAX_LOG_LINES = 500


class _StreamToLogWidget:
    """
    Redirige un stream (stdout/stderr) a un Text widget de la GUI,
    manteniendo también la salida original (la terminal, si la
    hay). DexRelay hoy solo usa `print()` para reportar estado
    (Application, HTTPServer) -- no hay módulo `logging` todavía,
    así que redirigir el stream entero es mucho más simple que
    tocar cada `print()` uno por uno.

    Las escrituras se marshalean al hilo principal con
    `window.after(0, ...)` porque pueden venir del hilo del
    Runtime o del hilo del HTTPServer, y Tkinter no es thread-safe
    (mismo criterio de la sección 18 del Documento Maestro).
    """

    def __init__(self, window, text_widget, original_stream=None):
        self.window = window
        self.text_widget = text_widget
        self.original_stream = original_stream

    def write(self, text: str) -> None:
        if self.original_stream is not None:
            self.original_stream.write(text)

        if text.strip():
            self.window.after(0, self._append, text)

    def flush(self) -> None:
        if self.original_stream is not None:
            self.original_stream.flush()

    def _append(self, text: str) -> None:
        widget = self.text_widget
        widget.configure(state="normal")
        widget.insert("end", text if text.endswith("\n") else text + "\n")

        line_count = int(widget.index("end-1c").split(".")[0])

        if line_count > MAX_LOG_LINES:
            widget.delete("1.0", f"{line_count - MAX_LOG_LINES}.0")

        widget.see("end")
        widget.configure(state="disabled")


class MainWindow:
    def __init__(
        self,
        application,
        window,
        container=None,
        on_back_to_welcome=None,
    ) -> None:
        self.app = application
        self.window = window
        self.container = container if container is not None else window
        self.on_back_to_welcome = on_back_to_welcome

        self._build_back_button()
        self._build_azahar_section()
        self._build_server_section()
        self._build_overlays_section()
        self._build_nuzlocke_section()
        self._build_config_section()
        self._build_logs_section()

        self._install_log_redirect()

        self._poll_state()

    # ---------------------------------------------------------------
    # Construcción de secciones
    # ---------------------------------------------------------------

    def _build_back_button(self) -> None:
        if self.on_back_to_welcome is None:
            return

        ttk.Button(
            self.container,
            text="◀ Volver a Bienvenida",
            bootstyle="link",
            command=self.on_back_to_welcome,
        ).pack(anchor="w", padx=12, pady=(12, 0))

    def _build_azahar_section(self) -> None:
        frame = ttk.Labelframe(
            self.container,
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
            self.container,
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
            self.container,
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
            self.container,
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

    def _build_config_section(self) -> None:
        frame = ttk.Labelframe(
            self.container,
            text="CONFIGURACIÓN",
            padding=12,
        )
        frame.pack(fill="x", padx=12, pady=6)

        config = self.app.config

        self._config_vars = {
            "process_name": ttk.StringVar(
                value=config.get(
                    "azahar", "process_name", default=""
                )
            ),
            "host": ttk.StringVar(
                value=config.get("server", "host", default="")
            ),
            "port": ttk.StringVar(
                value=str(config.get("server", "port", default=8080))
            ),
            "refresh_ms": ttk.StringVar(
                value=str(
                    config.get("realtime", "refresh_ms", default=200)
                )
            ),
        }

        fields = [
            ("Proceso Azahar", "process_name"),
            ("Host servidor", "host"),
            ("Puerto servidor", "port"),
            ("Refresco (ms)", "refresh_ms"),
        ]

        for label_text, key in fields:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)

            ttk.Label(
                row,
                text=label_text,
                width=14,
            ).pack(side="left")

            ttk.Entry(
                row,
                textvariable=self._config_vars[key],
            ).pack(side="left", expand=True, fill="x")

        self.config_status_label = ttk.Label(
            frame,
            text="Cambios de proceso/host/puerto/refresco requieren "
            "reiniciar DexRelay para aplicarse.",
            bootstyle=SECONDARY,
            wraplength=380,
        )
        self.config_status_label.pack(anchor="w", pady=(8, 0))

        ttk.Button(
            frame,
            text="Guardar configuración",
            command=self._save_config,
        ).pack(fill="x", pady=(6, 0))

    def _build_logs_section(self) -> None:
        frame = ttk.Labelframe(
            self.container,
            text="LOGS",
            padding=12,
        )
        frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(6, 12),
        )

        container = ttk.Frame(frame)
        container.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            container,
            height=10,
            wrap="word",
            state="disabled",
            background="#1e1e1e",
            foreground="#d0d0d0",
            insertbackground="#d0d0d0",
            relief="flat",
            borderwidth=0,
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=self.log_text.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _save_config(self) -> None:
        values = {
            key: var.get().strip()
            for key, var in self._config_vars.items()
        }

        try:
            port = int(values["port"])
            refresh_ms = int(values["refresh_ms"])
        except ValueError:
            self.config_status_label.configure(
                text="Puerto y refresco tienen que ser números "
                "enteros -- no se guardó nada.",
                bootstyle=DANGER,
            )
            return

        config = self.app.config
        config.set("azahar", "process_name", value=values["process_name"])
        config.set("server", "host", value=values["host"])
        config.set("server", "port", value=port)
        config.set("realtime", "refresh_ms", value=refresh_ms)
        config.save()

        self.config_status_label.configure(
            text="Guardado. Reiniciá DexRelay para que tome efecto.",
            bootstyle=SUCCESS,
        )

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

    def _install_log_redirect(self) -> None:
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        sys.stdout = _StreamToLogWidget(
            self.window, self.log_text, self._original_stdout
        )
        sys.stderr = _StreamToLogWidget(
            self.window, self.log_text, self._original_stderr
        )

    def restore_log_redirect(self) -> None:
        """
        Público a propósito -- lo llama `AppWindow` antes de cerrar
        la ventana raíz, ya que `MainWindow` ya no maneja el cierre
        de la ventana por su cuenta (ver `app/gui/app_window.py`).
        """

        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

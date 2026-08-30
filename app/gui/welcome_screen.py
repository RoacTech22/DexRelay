"""
Pantalla de bienvenida de DexRelay (FASE 4).

Primera pantalla que ve el usuario al abrir la app. Muestra el
logo real del proyecto (`assets/ui/dexrelay_logo.png`, provisto
por el usuario el 29/08/2026) y un selector de versión del juego.
"""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import PRIMARY, SECONDARY, SUCCESS

from app.core import paths
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)

LOGO_PATH = paths.path("assets", "ui", "dexrelay_logo.png")
LOGO_DISPLAY_WIDTH = 320

# (etiqueta visible, process_name, subtítulo opcional). Agregar un
# juego nuevo en el futuro es sumar una tupla acá -- no hace falta
# tocar nada más de esta pantalla.
GAME_VERSIONS = [
    ("Pokémon Alpha Sapphire", PROCESS_NAME_ALPHA_SAPPHIRE, None),
    (
        "Pokémon Omega Ruby",
        PROCESS_NAME_OMEGA_RUBY,
        "Soporte parcial -- todavía en pruebas",
    ),
]


class WelcomeScreen(ttk.Frame):
    def __init__(self, container, on_start) -> None:
        """
        `on_start(process_name)` se llama cuando el usuario elige
        una versión del juego y aprieta "Comenzar".
        """

        super().__init__(container)
        self.on_start = on_start
        self._selected_process_name = tk.StringVar(value="")
        self._logo_image = None  # referencia viva -- ver _build_logo()

        self._build()

    def _build(self) -> None:
        wrapper = ttk.Frame(self, padding=32)
        wrapper.pack(fill="both", expand=True)

        self._build_logo(wrapper)

        ttk.Label(
            wrapper,
            text=(
                "Lector en tiempo real para tus partidas de Pokémon\n"
                "en Azahar -- overlays para OBS, medallas y un\n"
                "Nuzlocke Tracker automático."
            ),
            justify="center",
            bootstyle=SECONDARY,
        ).pack(pady=(12, 28))

        ttk.Label(
            wrapper,
            text="Empezá a jugar",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            wrapper,
            text="Elegí la versión del juego:",
            bootstyle=SECONDARY,
        ).pack(anchor="w", pady=(0, 10))

        options_frame = ttk.Frame(wrapper)
        options_frame.pack(fill="x", pady=(0, 24))

        for label, process_name, subtitle in GAME_VERSIONS:
            self._build_option(
                options_frame, label, process_name, subtitle
            )

        self.start_button = ttk.Button(
            wrapper,
            text="Comenzar",
            bootstyle=SUCCESS,
            state="disabled",
            command=self._start,
        )
        self.start_button.pack(fill="x")

    def _build_option(
        self, parent, label: str, process_name: str, subtitle
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)

        ttk.Radiobutton(
            row,
            text=label,
            value=process_name,
            variable=self._selected_process_name,
            command=self._on_selection_changed,
            bootstyle=PRIMARY,
        ).pack(anchor="w")

        if subtitle:
            ttk.Label(
                row,
                text=subtitle,
                bootstyle=SECONDARY,
                font=("Segoe UI", 8),
            ).pack(anchor="w", padx=(24, 0))

    def _on_selection_changed(self) -> None:
        self.start_button.configure(state="normal")

    def _start(self) -> None:
        process_name = self._selected_process_name.get()

        if process_name:
            self.on_start(process_name)

    def _build_logo(self, parent) -> None:
        """
        Carga `assets/ui/dexrelay_logo.png` con Pillow (el `alpha`
        del PNG ya viene bien, sin halo blanco en los bordes --
        chequeado a mano antes de sumarlo al proyecto) y lo
        redimensiona manteniendo proporción. Si el archivo no
        está (por ejemplo, alguien corrió el código sin extraer
        el asset del zip), no revienta la pantalla entera -- cae
        a un título de texto simple.
        """

        try:
            image = Image.open(LOGO_PATH)
            ratio = LOGO_DISPLAY_WIDTH / image.width
            target_size = (
                LOGO_DISPLAY_WIDTH,
                round(image.height * ratio),
            )
            image = image.resize(target_size, Image.LANCZOS)

            self._logo_image = ImageTk.PhotoImage(image)

            ttk.Label(parent, image=self._logo_image).pack()
        except (FileNotFoundError, OSError):
            ttk.Label(
                parent,
                text="DexRelay",
                font=("Segoe UI", 28, "bold"),
            ).pack()

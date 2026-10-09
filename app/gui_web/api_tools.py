"""
Página Herramientas (única escritura de memoria de DexRelay: Caramelo Raro).

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations

from app.services.bag_service import (
    RARE_CANDY_ITEM_ID,
    BagService,
    BagWriteError,
)


class ToolsMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

    # -----------------------------------------------------------
    # Página Herramientas (07/09/2026) -- primera función de
    # ESCRITURA de memoria de DexRelay (todo lo demás en la app es
    # solo lectura). Ver Documento Maestro de esta sesión y
    # app/memory/pointers.py (sección "BOLSA DE ITEMS") para el
    # detalle completo de cómo se confirmó la dirección/estructura.
    # La lógica real vive en BagService, compartida con
    # tools/probes/memory/escribir_item_bolsa.py -- acá solo se
    # traduce el resultado a algo que el frontend pueda mostrar.
    # -----------------------------------------------------------

    def get_herramientas_page_data(self):
        """
        Estado inicial de la página: si Azahar está conectado (la
        página deshabilita el botón y muestra un aviso si no).
        Confirmada en vivo contra las dos versiones (Alpha Sapphire
        y Omega Ruby, 07/09/2026) -- no hace falta avisar sobre
        versión distinta como al principio.
        """

        state = self.app.state

        # Bloque 13: la escritura en la bolsa solo se ofrece si el
        # perfil del juego conectado la tiene confirmada. Sin juego
        # detectado todavía no se bloquea nada (la nota de "conecta
        # Azahar" ya cubre ese caso).
        profile = self.app.reader.profile
        bag_writing = (
            profile is None
            or (
                profile.capabilities.has_bag_writing
                and profile.memory_map.medicine_pocket_start_address
                is not None
            )
        )

        return {
            "connected": bool(state.azahar_connected),
            "bagWritingAvailable": bool(bag_writing),
        }

    def add_rare_candy(self, cantidad):
        """
        Agrega Caramelo Raro (item_id=50, confirmado contra la
        tabla oficial de índices de Bulbapedia para Generación VI)
        a la bolsa. Devuelve `{"ok": True, "new_quantity": N}` o
        `{"error": "mensaje"}` -- nunca lanza una excepción hacia
        el frontend, BagWriteError ya viene con un mensaje legible.
        """

        try:
            cantidad = int(cantidad)
        except (TypeError, ValueError):
            return {"error": "Cantidad inválida."}

        try:
            result = BagService(self.app.reader).add_medicine_item(
                RARE_CANDY_ITEM_ID, cantidad
            )
        except BagWriteError as error:
            return {"error": str(error)}

        return {"ok": True, "new_quantity": result["new_quantity"]}

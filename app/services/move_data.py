"""
Carga el dataset estático de movimientos (potencia/precisión/
categoría) curado por tools/data_curation/build_move_data.py.

Decisión de diseño (06/09/2026, roadmap sección 6 pregunta 1,
alcance ampliado): PKHeX.Core no trae potencia/precisión/categoría
(confirmado, ver Program.cs), así que ese pedazo de move_details()
NO sale del bridge -- sale de este archivo estático, curado offline
una sola vez. El bridge sigue siendo la fuente de nombre/tipo/PP
(lo que SÍ tiene).

Este servicio NO necesita internet -- lee un JSON ya generado y
commiteado (data/move_data.json). Si ese archivo no existe todavía
(porque el script de curación no se corrió), se degrada con
gracia: devuelve power/accuracy/categoryKey vacíos en vez de romper
toda la respuesta del modal de movimiento.
"""

import json

from app.core import paths


class MoveDataCatalog:
    """
    Instancia única, cacheada en memoria después de la primera
    lectura -- mismo patrón que SpeciesCatalog/LocationCatalog
    (el archivo no cambia mientras la app corre, no tiene sentido
    releerlo de disco en cada pedido del modal de movimiento).
    """

    def __init__(self):
        self._by_move_id = None

    def _ensure_loaded(self):

        if self._by_move_id is not None:
            return

        data_path = paths.path("data", "move_data.json")

        if not data_path.exists():
            # Degradación con gracia (ver docstring del módulo):
            # el resto del modal (nombre/tipo/PP, que sí vienen del
            # bridge) sigue funcionando igual sin este dataset.
            self._by_move_id = {}
            return

        with open(data_path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        # Las claves del JSON son strings (limitación de JSON, no
        # de Python) -- se normalizan a int acá para que el resto
        # del código no tenga que acordarse de este detalle en
        # cada lookup.
        self._by_move_id = {
            int(move_id): entry for move_id, entry in raw.items()
        }

    def get(self, move_id):
        """
        Devuelve {"power": int|None, "accuracy": int|None,
        "categoryKey": str} para el movimiento pedido, o valores
        vacíos si no está en el dataset (movimiento fuera de rango,
        o dataset todavía no generado).
        """

        self._ensure_loaded()

        return self._by_move_id.get(
            move_id,
            {"power": None, "accuracy": None, "categoryKey": ""},
        )


def merge_move_details(bridge_response, catalog):
    """
    Combina lo que YA devuelve el bridge PKHeX (id/name/typeKey/
    type/basePP -- ver HandleMoveDetails(), Program.cs) con lo que
    sale del dataset estático (power/accuracy/categoryKey). Punto
    único donde se unen las dos fuentes, para que quien llame a
    esto (el endpoint que use la GUI cuando se construya el modal
    de movimiento, Fase C del roadmap) reciba un solo objeto
    completo sin tener que conocer de dónde vino cada campo.
    """

    if "error" in bridge_response:
        return bridge_response

    static_data = catalog.get(bridge_response["id"])

    return {
        **bridge_response,
        "power": static_data["power"],
        "accuracy": static_data["accuracy"],
        "categoryKey": static_data["categoryKey"],
    }

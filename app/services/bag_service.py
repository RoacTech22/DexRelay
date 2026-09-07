"""
Servicio para agregar items a la bolsa escribiendo memoria real de
Azahar (Caramelo Raro y, en el futuro, otros items de Medicina).

Extraído de tools/probes/memory/escribir_item_bolsa.py (07/09/2026)
para que la página Herramientas de la GUI use exactamente la misma
lógica ya validada en vivo por el usuario, en vez de reimplementarla
aparte -- si en el futuro se corrige algo acá, los probes originales
quedan como referencia histórica de la investigación pero dejan de
ser la fuente de verdad del código real.

CORRECCIÓN IMPORTANTE (07/09/2026, mismo día): la primera versión de
este servicio buscaba CUALQUIER casillero vacío dentro de todo el
tramo de la bolsa (BAG_START/END_ADDRESS, ~740 casilleros que cubren
TODOS los bolsillos pegados sin relleno). Esto agregaba el Caramelo
Raro en un casillero que técnicamente pertenecía a otro bolsillo
(el juego lo mostraba en "Objetos"), y como el bolsillo real
importa para la lógica del juego (usar el item no descontaba la
cantidad), quedaba roto. La corrección: escribir SOLO dentro de la
ventana del bolsillo correcto -- ver
get_medicine_pocket_start_address() en app/memory/pointers.py.

Ver app/memory/pointers.py (sección "BOLSILLO DE MEDICINA") para el
detalle completo de cómo se confirmó la dirección y por qué Rare
Candy pertenece ahí (categoría oficial de Bulbapedia, no supuesto).
"""

from __future__ import annotations

import struct

from app.memory.pointers import (
    BAG_SLOT_SIZE,
    BAG_MAX_QUANTITY,
    MEDICINE_POCKET_SCAN_SLOTS,
    get_medicine_pocket_start_address,
)


class BagWriteError(Exception):
    """
    Cualquier problema que impida agregar el item de forma segura
    (sin conexión, lectura/escritura fallida, bolsillo lleno,
    cantidad fuera de rango, etc) -- el mensaje ya viene listo para
    mostrar tal cual en la GUI, no hace falta traducir códigos de
    error.
    """


class BagService:
    """
    Envoltorio fino sobre un AzaharReader ya conectado
    (`reader.citra`/`reader.memory`) para agregar items de Medicina
    a la bolsa. No guarda estado propio -- cada llamada a
    `add_medicine_item()` relee la ventana del bolsillo antes de
    decidir dónde escribir, para no operar sobre una copia vieja si
    el usuario tocó la bolsa mientras tanto.
    """

    def __init__(self, reader):
        self.reader = reader

    def _read_window(self, start, slot_count):
        size = slot_count * BAG_SLOT_SIZE
        data = self.reader.memory.read(start, size)

        if data is None or len(data) != size:
            raise BagWriteError(
                "No se pudo leer la memoria de la bolsa. "
                "¿Azahar sigue abierto y con el juego cargado?"
            )

        return data

    @staticmethod
    def _decode_slot(data, offset):
        return struct.unpack(
            "<HH", data[offset:offset + BAG_SLOT_SIZE]
        )

    @staticmethod
    def _encode_slot(item_id, quantity):
        return struct.pack("<HH", item_id, quantity)

    def _find_existing_slot(self, data, item_id):
        for offset in range(0, len(data), BAG_SLOT_SIZE):
            existing_id, _quantity = self._decode_slot(data, offset)
            if existing_id == item_id:
                return offset

        return None

    def _find_empty_slot(self, data):
        for offset in range(0, len(data), BAG_SLOT_SIZE):
            existing_id, existing_quantity = self._decode_slot(
                data, offset
            )
            if existing_id == 0 and existing_quantity == 0:
                return offset

        return None

    def add_medicine_item(self, item_id, quantity):
        """
        Agrega `quantity` unidades de `item_id` DENTRO del bolsillo
        de Medicina: si el item ya está, le suma a lo que tenía
        (tope BAG_MAX_QUANTITY); si no, usa el primer casillero
        vacío dentro de la ventana del bolsillo (ver
        MEDICINE_POCKET_SCAN_SLOTS -- acotado a propósito para no
        cruzar al bolsillo siguiente). Devuelve un dict con
        `address`, `item_id` y `new_quantity`. Lanza BagWriteError
        con un mensaje legible ante cualquier problema -- nunca
        falla en silencio.

        Solo pensado para items que pertenecen al bolsillo de
        Medicina (ver Category:Medicine_Pocket de Bulbapedia) -- no
        usar para items de otros bolsillos, terminarían en el lugar
        equivocado igual que le pasó al Caramelo Raro la primera
        vez.
        """

        if not (0 < item_id <= 999):
            raise BagWriteError("item_id fuera de rango (1-999).")

        if not (0 < quantity <= BAG_MAX_QUANTITY):
            raise BagWriteError(
                f"Cantidad fuera de rango (1-{BAG_MAX_QUANTITY})."
            )

        if (
            not self.reader.is_connected()
            or self.reader.process_name is None
        ):
            raise BagWriteError(
                "Azahar no está conectado. Conectate desde el "
                "Dashboard antes de usar esta herramienta."
            )

        pocket_start = get_medicine_pocket_start_address(
            self.reader.process_name
        )

        data = self._read_window(pocket_start, MEDICINE_POCKET_SCAN_SLOTS)

        existing_offset = self._find_existing_slot(data, item_id)

        if existing_offset is not None:
            existing_id, existing_quantity = self._decode_slot(
                data, existing_offset
            )
            target_offset = existing_offset
            new_quantity = min(
                existing_quantity + quantity, BAG_MAX_QUANTITY
            )
        else:
            empty_offset = self._find_empty_slot(data)

            if empty_offset is None:
                raise BagWriteError(
                    "No se encontró ningún casillero vacío dentro "
                    "del bolsillo de Medicina -- puede estar lleno, "
                    "o la ventana de búsqueda quedó corta."
                )

            target_offset = empty_offset
            new_quantity = quantity

        target_address = pocket_start + target_offset
        new_bytes = self._encode_slot(item_id, new_quantity)

        success = self.reader.citra.write_memory(
            target_address, new_bytes
        )

        if not success:
            raise BagWriteError("La escritura de memoria falló.")

        verify = self.reader.memory.read(
            target_address, BAG_SLOT_SIZE
        )

        if verify != new_bytes:
            raise BagWriteError(
                "La escritura no se pudo verificar (los bytes "
                "leídos no coinciden con lo escrito). Revisá la "
                "bolsa en el juego antes de seguir jugando."
            )

        return {
            "address": target_address,
            "item_id": item_id,
            "new_quantity": new_quantity,
        }

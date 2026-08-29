"""
Reproduce el bug real reportado (29/08/2026): al depositar un
Pokémon de la party en la Caja PC, el slot que quedaba libre en
el overlay se completaba con el sprite del último Pokémon del
equipo en vez de quedar en blanco.

Causa CONFIRMADA con Cheat Engine (dos hipótesis previas
descartadas en el camino -- ver historial de esta investigación
en el chat, o el Documento Maestro tras la próxima actualización):
`PARTY_ORDER_ADDRESS` son 6 casilleros fijos que el juego siempre
mantiene reservados en memoria, tengas 6 Pokémon o 1 -- al
depositar uno, su puntero NO se limpia (sigue apuntando a datos
viejos pero todavía válidos, por eso decodificaba bien). La
cantidad REAL de Pokémon vive aparte, en `PARTY_COUNT_ADDRESS`
(0x08CF7208 = PARTY_ORDER_ADDRESS + 0x18, el byte siguiente al
final de la tabla de 6 punteros) -- confirmada en vivo bajando de
6 a 2 exactamente en cada depósito.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.readers.azahar_reader import AzaharReader


class FakeMemoryReader:
    """
    Simula MemoryReader.read() devolviendo una tabla de punteros
    fija (24 bytes = 6 punteros de 4 bytes, little-endian) y un
    valor fijo de PARTY_COUNT_ADDRESS (1 byte), según la dirección
    pedida -- igual que la memoria real, ambas direcciones son
    independientes.
    """

    def __init__(self, pointers, party_count):
        assert len(pointers) == 6
        self.pointers = pointers
        self.party_count = party_count

    def read(self, address, size):

        from app.memory.pointers import (
            PARTY_ORDER_ADDRESS,
            PARTY_COUNT_ADDRESS,
        )

        if address == PARTY_ORDER_ADDRESS and size == 24:

            data = b""
            for pointer in self.pointers:
                data += pointer.to_bytes(
                    4, byteorder="little"
                )
            return data

        if address == PARTY_COUNT_ADDRESS and size == 1:
            return bytes([self.party_count])

        return b""


def _reader_with(pointers, party_count):
    reader = AzaharReader.__new__(AzaharReader)
    reader.memory = FakeMemoryReader(pointers, party_count)
    return reader


def test_party_completa_no_cambia_nada():

    reader = _reader_with(
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=6,
    )

    result = reader.read_party_order()

    assert result == [
        0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000
    ]

    print(
        "OK - con los 6 slots reales (party_count=6), la tabla "
        "se lee tal cual"
    )


def test_deposito_del_medio_vacia_el_slot_sobrante():
    """
    Reproduce el síntoma exacto reportado y confirmado con Cheat
    Engine: se deposita un Pokémon del medio (slot 3) -- los
    siguientes NO se mueven en la tabla de punteros (esto también
    se confirmó con el probe de observación: los punteros se
    reordenan de forma independiente a los depósitos, no hay
    ningún corrimiento automático), pero party_count baja a 5 --
    el sexto puntero (que sigue teniendo datos viejos válidos) se
    tiene que tratar como vacío igual, porque ya no es parte de la
    party real.
    """

    reader = _reader_with(
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=5,
    )

    result = reader.read_party_order()

    # Los primeros 5 punteros quedan tal cual (no sabemos de
    # antemano cuál posición exacta "sobra" según el motor del
    # juego, pero el punto clave es que TODO lo que esté en una
    # posición >= party_count se vacía, sea cual sea el valor).
    assert result == [
        0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0
    ]

    print(
        "OK - con party_count=5, el slot 6 (aunque su puntero "
        "siga teniendo datos viejos válidos) se fuerza a vacío"
    )


def test_varios_depositos_seguidos():

    reader = _reader_with(
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=2,
    )

    result = reader.read_party_order()

    assert result == [0x1000, 0x2000, 0, 0, 0, 0]

    print(
        "OK - con party_count=2 (varios depósitos seguidos), "
        "solo los primeros 2 slots quedan como reales"
    )


def test_lectura_de_party_count_fallida_no_vacia_nada():
    """
    Si por algún motivo transitorio la lectura de
    PARTY_COUNT_ADDRESS falla, no hay forma segura de saber
    cuántos slots son reales -- se prefiere el comportamiento
    anterior (los 6 punteros tal cual) a arriesgarse a vaciar de
    más por una lectura perdida.
    """

    class BrokenCountReader(FakeMemoryReader):
        def read(self, address, size):
            from app.memory.pointers import PARTY_COUNT_ADDRESS
            if address == PARTY_COUNT_ADDRESS:
                return b""  # lectura fallida
            return super().read(address, size)

    reader = AzaharReader.__new__(AzaharReader)
    reader.memory = BrokenCountReader(
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=3,
    )

    result = reader.read_party_order()

    assert result == [
        0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000
    ]

    print(
        "OK - si la lectura de party_count falla, se devuelven "
        "los 6 punteros tal cual (no se vacía nada por las dudas)"
    )


if __name__ == "__main__":
    test_party_completa_no_cambia_nada()
    test_deposito_del_medio_vacia_el_slot_sobrante()
    test_varios_depositos_seguidos()
    test_lectura_de_party_count_fallida_no_vacia_nada()

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
(PARTY_ORDER_ADDRESS + 0x18, el byte siguiente al final de la
tabla de 6 punteros) -- confirmada en vivo bajando de 6 a 2
exactamente en cada depósito.

Multi-versión (29/08/2026, mismo día): se confirmó que Alpha
Sapphire y Omega Ruby usan direcciones DISTINTAS para esto (la de
AS da 0x0 en Omega Ruby) -- `read_party_order()` ahora elige el
par correcto según `self.process_name`. Los tests de acá cubren
las dos versiones para asegurarse de que la selección funciona
bien y no se cruzan los valores.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
    get_party_order_address,
    get_party_count_address,
)


class FakeMemoryReader:
    """
    Simula MemoryReader.read() devolviendo una tabla de punteros
    fija (24 bytes = 6 punteros de 4 bytes, little-endian) y un
    valor fijo de party_count (1 byte), en las direcciones
    correctas SEGÚN LA VERSIÓN (`process_name`) -- para poder
    confirmar que read_party_order() no mezcla direcciones de
    Alpha Sapphire con las de Omega Ruby por error.
    """

    def __init__(self, process_name, pointers, party_count):
        assert len(pointers) == 6
        self.process_name = process_name
        self.pointers = pointers
        self.party_count = party_count

    def read(self, address, size):

        order_address = get_party_order_address(
            self.process_name
        )
        count_address = get_party_count_address(
            self.process_name
        )

        if address == order_address and size == 24:

            data = b""
            for pointer in self.pointers:
                data += pointer.to_bytes(
                    4, byteorder="little"
                )
            return data

        if address == count_address and size == 1:
            return bytes([self.party_count])

        return b""


def _reader_with(
    pointers,
    party_count,
    process_name=PROCESS_NAME_ALPHA_SAPPHIRE,
):
    reader = AzaharReader.__new__(AzaharReader)
    reader.process_name = process_name
    reader.memory = FakeMemoryReader(
        process_name, pointers, party_count
    )
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
            count_address = get_party_count_address(
                self.process_name
            )
            if address == count_address:
                return b""  # lectura fallida
            return super().read(address, size)

    reader = AzaharReader.__new__(AzaharReader)
    reader.process_name = PROCESS_NAME_ALPHA_SAPPHIRE
    reader.memory = BrokenCountReader(
        PROCESS_NAME_ALPHA_SAPPHIRE,
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


def test_omega_ruby_usa_sus_propias_direcciones():
    """
    29/08/2026: confirmado en el juego real que Omega Ruby usa
    PARTY_ORDER_ADDRESS/PARTY_COUNT_ADDRESS DISTINTAS de Alpha
    Sapphire. Mismo comportamiento (deposita del medio, el slot
    sobrante se vacía), pero pasando process_name="sango-1" --
    confirma que read_party_order() elige el par de direcciones
    correcto y no mezcla nada entre versiones.
    """

    reader = _reader_with(
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=5,
        process_name=PROCESS_NAME_OMEGA_RUBY,
    )

    result = reader.read_party_order()

    assert result == [
        0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0
    ]

    print(
        "OK - con process_name de Omega Ruby, read_party_order() "
        "usa sus propias direcciones y funciona igual que en "
        "Alpha Sapphire"
    )


def test_las_direcciones_de_las_dos_versiones_no_se_mezclan():
    """
    Control cruzado: un AzaharReader con process_name de Omega
    Ruby, pero una memoria falsa que SOLO tiene datos válidos en
    las direcciones de Alpha Sapphire (simulando el bug real que
    motivó todo esto: si el código mezclara mal las direcciones,
    leería mal). Tiene que devolver todo vacío -- confirma que
    jamás intenta leer las direcciones de la otra versión.
    """

    reader = AzaharReader.__new__(AzaharReader)
    reader.process_name = PROCESS_NAME_OMEGA_RUBY
    # Memoria que solo entiende las direcciones de AS -- si
    # read_party_order() se equivocara de versión, leería datos
    # de acá por error.
    reader.memory = FakeMemoryReader(
        PROCESS_NAME_ALPHA_SAPPHIRE,
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=6,
    )

    result = reader.read_party_order()

    # Ni un solo puntero real -- la memoria falsa no tiene nada
    # en las direcciones de Omega Ruby, así que debería devolver
    # una lectura fallida (lista vacía) en vez de leer por
    # accidente las direcciones de la otra versión.
    assert result == []

    print(
        "OK - las direcciones de las dos versiones no se mezclan "
        "nunca, aunque el process_name no coincida con la memoria"
    )


if __name__ == "__main__":
    test_party_completa_no_cambia_nada()
    test_deposito_del_medio_vacia_el_slot_sobrante()
    test_varios_depositos_seguidos()
    test_lectura_de_party_count_fallida_no_vacia_nada()
    test_omega_ruby_usa_sus_propias_direcciones()
    test_las_direcciones_de_las_dos_versiones_no_se_mezclan()

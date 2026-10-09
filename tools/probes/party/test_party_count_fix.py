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
Sapphire (todavía en la versión base, sin el parche) y Omega Ruby
usaban direcciones DISTINTAS para esto (la de AS daba 0x0 en Omega
Ruby) -- `read_party_order()` elige el par correcto según
`self.process_name`. Los tests de acá cubren
las dos versiones para asegurarse de que la selección funciona
bien y no se cruzan los valores.

ACTUALIZADO (09/09/2026, ver el comentario junto a
_PARTY_ORDER_ADDRESS_BY_PROCESS en pointers.py): tras migrar Alpha
Sapphire a la actualización 1.4, esta dirección CONVERGIÓ -- AS
1.4 y Omega Ruby ahora usan el mismo valor (0x08CFB1E0), confirmado
en vivo. `test_las_direcciones_de_las_dos_versiones_convergen_
desde_1_4` (antes `..._no_se_mezclan`, con la premisa opuesta e
inválida desde este cambio) prueba eso -- no que sigan siendo
distintas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.readers.azahar_reader import AzaharReader
from tools.probes.legacy_pointers import (
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
    29/08/2026: en ese momento, confirmado en el juego real que
    Omega Ruby usaba PARTY_ORDER_ADDRESS/PARTY_COUNT_ADDRESS
    DISTINTAS de Alpha Sapphire base. Desde que AS migró a la
    actualización 1.4 (09/09/2026), ambas direcciones convergieron
    al mismo valor -- ver test_las_direcciones_de_las_dos_
    versiones_convergen_desde_1_4 más abajo. Este test sigue
    siendo válido igual: confirma que pasando
    process_name="sango-1" explícito, read_party_order() resuelve
    bien sus propias direcciones (aunque hoy sean las mismas que
    las de AS) y el comportamiento (deposita del medio, el slot
    sobrante se vacía) funciona igual.
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


def test_las_direcciones_de_las_dos_versiones_convergen_desde_1_4():
    """
    Antes (`..._no_se_mezclan`, hasta el 09/09/2026): control
    cruzado que esperaba que mezclar el process_name de Omega Ruby
    con una memoria que solo entendía direcciones de Alpha
    Sapphire diera vacío -- válido mientras las dos versiones
    tenían PARTY_ORDER_ADDRESS/PARTY_COUNT_ADDRESS distintas.

    Ahora (ver pointers.py, comentario junto a
    _PARTY_ORDER_ADDRESS_BY_PROCESS, 09/09/2026): tras migrar
    Alpha Sapphire a la actualización 1.4, esa premisa dejó de ser
    cierta -- las dos versiones usan EXACTAMENTE la misma
    dirección (0x08CFB1E0/0x08CFB1F8), confirmado en vivo. Mezclar
    process_name="sango-1" con una memoria "de Alpha Sapphire" ya
    no puede dar vacío, porque para estas dos direcciones ya no
    hay nada que mezclar -- son la misma tabla.

    Este test prueba eso en cambio: que get_party_order_address()/
    get_party_count_address() devuelven el mismo valor para las
    dos versiones (protege contra reintroducir sin querer un par
    de direcciones separadas sin haber confirmado antes, con un
    probe real, que hizo falta -- regla 1/11 del Documento
    Maestro), y que el fallback ante un process_name desconocido
    sigue devolviendo el valor de Alpha Sapphire documentado.
    """

    assert get_party_order_address(
        PROCESS_NAME_OMEGA_RUBY
    ) == get_party_order_address(PROCESS_NAME_ALPHA_SAPPHIRE)

    assert get_party_count_address(
        PROCESS_NAME_OMEGA_RUBY
    ) == get_party_count_address(PROCESS_NAME_ALPHA_SAPPHIRE)

    assert get_party_order_address("proceso-desconocido") == (
        get_party_order_address(PROCESS_NAME_ALPHA_SAPPHIRE)
    )

    # Con las direcciones convergidas, una memoria que solo
    # entiende Alpha Sapphire responde igual sin importar qué
    # process_name traiga el reader -- ya no hay nada que
    # "mezclar" para estas dos direcciones en particular.
    reader = AzaharReader.__new__(AzaharReader)
    reader.process_name = PROCESS_NAME_OMEGA_RUBY
    reader.memory = FakeMemoryReader(
        PROCESS_NAME_ALPHA_SAPPHIRE,
        [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000],
        party_count=6,
    )

    result = reader.read_party_order()

    assert result == [
        0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000
    ]

    print(
        "OK - PARTY_ORDER_ADDRESS/PARTY_COUNT_ADDRESS convergieron "
        "entre las dos versiones desde Alpha Sapphire 1.4, y el "
        "fallback de process_name desconocido sigue apuntando a "
        "Alpha Sapphire"
    )


if __name__ == "__main__":
    test_party_completa_no_cambia_nada()
    test_deposito_del_medio_vacia_el_slot_sobrante()
    test_varios_depositos_seguidos()
    test_lectura_de_party_count_fallida_no_vacia_nada()
    test_omega_ruby_usa_sus_propias_direcciones()
    test_las_direcciones_de_las_dos_versiones_convergen_desde_1_4()
    print("OK - todos los tests de party_count_fix pasaron")

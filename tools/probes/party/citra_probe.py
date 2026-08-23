import struct

from app.readers.citra import Citra
from app.memory.memory_reader import MemoryReader
from app.memory.pointers import (
    PARTY_ORDER_ADDRESS,
    ORDER_ENTRY_SIZE,
    POKEMON_POINTER_OFFSET,
    SLOT_DATA_SIZE,
    STAT_DATA_OFFSET,
    STAT_DATA_SIZE,
)
from app.memory.structures import Pokemon6


def main():
    print("================================")
    print("       DEXRELAY PARTY PROBE")
    print("================================")
    print()

    # --------------------------------------------------------
    # CONEXIÓN CON AZAHAR
    # --------------------------------------------------------

    citra = Citra()
    memory = MemoryReader(citra)

    print("Consultando procesos de Azahar...")

    processes = citra.process_list()

    if not processes:
        print("No se encontraron procesos.")
        return

    # --------------------------------------------------------
    # BUSCAR sango-2
    # --------------------------------------------------------

    target_process_id = None

    for process_id, data in processes.items():
        title_id, process_name = data

        print(
            f"PID: {process_id} | "
            f"Nombre: {process_name} | "
            f"Title ID: {title_id}"
        )

        if process_name == "sango-2":
            target_process_id = process_id

    if target_process_id is None:
        print()
        print("No se encontró el proceso sango-2.")
        return

    # --------------------------------------------------------
    # SELECCIONAR PROCESO
    # --------------------------------------------------------

    print()
    print(
        f"Seleccionando proceso: "
        f"{target_process_id}"
    )

    citra.set_process(
        target_process_id
    )

    current_process = citra.get_process()

    print(
        f"Proceso activo según Azahar: "
        f"{current_process}"
    )

    # --------------------------------------------------------
    # LEER TABLA DE PARTY
    # --------------------------------------------------------

    print()
    print("Leyendo tabla de party...")

    party_order_size = (
        ORDER_ENTRY_SIZE * 6
    )

    party_order_data = memory.read(
        PARTY_ORDER_ADDRESS,
        party_order_size
    )

    if not party_order_data:
        print(
            "ERROR: No se pudo leer "
            "la tabla de party."
        )
        return

    if len(party_order_data) != party_order_size:
        print(
            f"ERROR: Se esperaban "
            f"{party_order_size} bytes, "
            f"se recibieron "
            f"{len(party_order_data)}."
        )
        return

    print(
        f"Tabla recibida: "
        f"{len(party_order_data)} bytes"
    )

    # --------------------------------------------------------
    # OBTENER PUNTEROS
    # --------------------------------------------------------

    pointers = []

    for slot in range(6):
        pointer = struct.unpack_from(
            "<I",
            party_order_data,
            slot * ORDER_ENTRY_SIZE
        )[0]

        pointers.append(pointer)

    # --------------------------------------------------------
    # MOSTRAR PARTY
    # --------------------------------------------------------

    print()
    print("================================")
    print("          PARTY")
    print("================================")

    for slot in range(6):

        pointer = pointers[slot]

        print()
        print(
            f"Slot {slot + 1}"
        )

        print(
            f"  Puntero: "
            f"0x{pointer:08X}"
        )

        # ----------------------------------------------------
        # SLOT VACÍO
        # ----------------------------------------------------

        if pointer == 0:
            print("  Vacío")
            continue

        # ----------------------------------------------------
        # PUNTERO → ESTRUCTURA PK6
        # ----------------------------------------------------

        pokemon_address = (
            pointer
            + POKEMON_POINTER_OFFSET
        )

        print(
            f"  Dirección PK6: "
            f"0x{pokemon_address:08X}"
        )

        # ----------------------------------------------------
        # LEER ESTRUCTURA PRINCIPAL
        # ----------------------------------------------------

        party_data = memory.read(
            pokemon_address,
            SLOT_DATA_SIZE
        )

        if not party_data:
            print(
                "  ERROR: No se pudo "
                "leer el Pokémon."
            )
            continue

        if len(party_data) != SLOT_DATA_SIZE:
            print(
                f"  ERROR: Se esperaban "
                f"{SLOT_DATA_SIZE} bytes, "
                f"se recibieron "
                f"{len(party_data)}."
            )
            continue

        # ----------------------------------------------------
        # LEER DATOS ADICIONALES
        #
        # El lector original utiliza:
        #
        # address
        # + SLOT_DATA_SIZE
        # + STAT_DATA_OFFSET
        #
        # y lee STAT_DATA_SIZE bytes.
        # ----------------------------------------------------

        stats_address = (
            pokemon_address
            + SLOT_DATA_SIZE
            + STAT_DATA_OFFSET
        )

        stats_data = memory.read(
            stats_address,
            STAT_DATA_SIZE
        )

        if not stats_data:
            print(
                "  ERROR: No se pudieron "
                "leer los datos adicionales."
            )
            continue

        if len(stats_data) != STAT_DATA_SIZE:
            print(
                f"  ERROR: Se esperaban "
                f"{STAT_DATA_SIZE} bytes "
                f"adicionales, "
                f"se recibieron "
                f"{len(stats_data)}."
            )
            continue

        # ----------------------------------------------------
        # COMBINAR DATOS
        # ----------------------------------------------------

        encrypted_data = (
            party_data
            + stats_data
        )

        print(
            f"  Datos PK6: "
            f"{len(party_data)} bytes"
        )

        print(
            f"  Datos adicionales: "
            f"{len(stats_data)} bytes"
        )

        print(
            f"  Datos totales: "
            f"{len(encrypted_data)} bytes"
        )

        # ----------------------------------------------------
        # DESCIFRAR / CREAR POKÉMON
        # ----------------------------------------------------

        try:
            pokemon = Pokemon6(
                encrypted_data
            )

        except Exception as error:
            print(
                f"  ERROR descifrando "
                f"slot {slot + 1}: "
                f"{error}"
            )
            continue

        if not pokemon.raw_data:
            print(
                "  Pokémon vacío o inválido."
            )
            continue

        # ----------------------------------------------------
        # LEER DATOS DEL POKÉMON
        # ----------------------------------------------------

        species_id = (
            pokemon.species_id()
        )

        nickname = (
            pokemon.nickname()
        )

        level = (
            pokemon.level()
        )

        hp = (
            pokemon.hp()
        )

        max_hp = (
            pokemon.max_hp()
        )

        # ----------------------------------------------------
        # MOSTRAR RESULTADO
        # ----------------------------------------------------

        print(
            f"  Species ID: {species_id}"
        )

        print(
            f"  Nickname:   {nickname}"
        )

        print(
            f"  Level:      {level}"
        )

        print(
            f"  HP:         {hp}/{max_hp}"
        )


if __name__ == "__main__":
    main()
"""
Diagnóstico SOLO LECTURA (18/09/2026, bug reportado: "no funciona el
registro de los Pokémon perdidos en el Nuzlocke").

La detección de "perdido" (Runtime._update_lost_encounter_tracking)
depende de CINCO lecturas de memoria encadenadas. Si cualquiera falla,
no se registra nada y no hay ningún error visible:

    1. Puntero de combate (COMBAT_POINTER_ADDRESS, combat_service.py)
    2. Flag salvaje       (WILD_BATTLE_FLAG_OFFSET, relativo al anterior)
    3. Zona actual        (CURRENT_ZONE_ID_ADDRESS, por proceso)
    4. Contador de capturas (TOTAL_CAUGHT_ADDRESS, por proceso)
    5. Especie del rival  (LAST_CAUGHT_ADDRESS, dirección fija)

Este probe imprime cada eslabón SOLO cuando cambia, así se ve en qué
punto exacto de un combate real se rompe la cadena.

CÓMO USARLO (Azahar corriendo, DexRelay CERRADO para no competir por
el socket UDP):

    python -m tools.probes.combat.diagnostico_perdido

Con el juego en una ruta SIN encuentro registrado en el Nuzlocke:
    - Entrá a un combate salvaje y HUÍ (o derrotalo) sin capturar.
    - Ctrl+C cuando estés de vuelta en el mapa y pasame TODA la salida.

Lo esperado en un combate salvaje sin captura:
    combate: sin combate -> SALVAJE   (flag=SALVAJE)
    zona: <nombre real de la ruta>
    especie rival: <especie>          (no None)
    total_caught: se mantiene igual antes/durante/después
"""

import struct
import time

from app.core.config import Config
from app.memory.pointers import (
    LAST_CAUGHT_ADDRESS,
    get_current_zone_id_address,
    get_total_caught_address,
)
from app.readers.azahar_reader import AzaharReader
from app.services.combat_service import (
    COMBAT_INACTIVE_POINTER,
    COMBAT_POINTER_ADDRESS,
    LECTURA_DESCARTADA,
    CombatService,
)
from app.services.zone_names import resolve_zone_name


def read_u32(reader, address):

    data = reader.memory.read(address, 4)

    if data is None or len(data) != 4:
        return None

    return struct.unpack("<I", data)[0]


def describe_pointer(value):

    if value is None:
        return "LECTURA FALLIDA"

    if value == 0:
        return "0x00000000 (sin combate)"

    if value == COMBAT_INACTIVE_POINTER:
        return f"{hex(value)} (valor inactivo conocido)"

    return f"{hex(value)} (combate ACTIVO)"


def main():

    process_name = Config().get(
        "azahar", "process_name", default=None
    )

    reader = AzaharReader(process_name=process_name)

    print("Conectando con Azahar...")

    if not reader.connect():
        print("No se pudo conectar.")
        return

    print(f"Conectado -- proceso: {reader.process_name}")
    print()
    print("Direcciones en uso:")
    print(f"  puntero de combate : {hex(COMBAT_POINTER_ADDRESS)}")
    print(
        "  zona actual        : "
        f"{hex(get_current_zone_id_address(reader.process_name))}"
    )
    print(
        "  contador capturas  : "
        f"{hex(get_total_caught_address(reader.process_name))}"
    )
    print(f"  último rival       : {hex(LAST_CAUGHT_ADDRESS)}")
    print()
    print("Estado inicial (fuera de combate):")
    print(f"  puntero: {describe_pointer(read_u32(reader, COMBAT_POINTER_ADDRESS))}")
    print(f"  zona   : {resolve_zone_name(reader.read_current_zone_id())}")
    print(f"  total  : {reader.read_total_caught_count()}")
    last = reader.read_last_caught()
    print(f"  rival  : {last.get('species') if last else None}")
    print()
    print("Hacé el combate salvaje ahora. Ctrl+C para cortar.")
    print()

    combat_service = CombatService(reader.memory)

    previous = {}

    try:
        while True:

            pointer = read_u32(reader, COMBAT_POINTER_ADDRESS)
            wild = combat_service.read_wild_flag()

            if wild is LECTURA_DESCARTADA:
                wild_text = "DESCARTADA"
            elif wild is None:
                wild_text = "sin combate"
            elif wild is True:
                wild_text = "SALVAJE"
            else:
                wild_text = "entrenador"

            zone_id = reader.read_current_zone_id()
            last = reader.read_last_caught()

            current = {
                "puntero": describe_pointer(pointer),
                "flag": wild_text,
                "zona": f"{zone_id} -> {resolve_zone_name(zone_id)}",
                "total_caught": reader.read_total_caught_count(),
                "especie rival": last.get("species") if last else None,
            }

            for key, value in current.items():

                if previous.get(key) != value:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] "
                        f"{key:14s}: {value}"
                    )

            previous = current

            time.sleep(0.2)

    except KeyboardInterrupt:
        print()
        print("Cortado. Pasame toda la salida de arriba.")


if __name__ == "__main__":
    main()

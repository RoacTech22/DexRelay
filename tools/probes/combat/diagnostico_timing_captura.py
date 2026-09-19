"""
Diagnóstico SOLO LECTURA (10/09/2026, bug real: "el Nuzlocke marca
perdido aunque atrapé, y después se duplica al asignar ruta" --
sigue pasando después de dos rondas de arreglos en runtime.py,
hace falta ver el timing real en vivo en vez de seguir adivinando
desde el código solo).

Imprime, cada ciclo de 200ms, el estado de combate/flag salvaje/
contador de capturas -- así vemos EXACTAMENTE en qué momento el
puntero de combate se limpia en relación a cuándo sube
TOTAL_CAUGHT_ADDRESS durante una captura real.

CÓMO USARLO:

    python -m tools.probes.combat.diagnostico_timing_captura

Dejalo corriendo, hacé UN combate salvaje y capturá el Pokémon
(ponele nombre si el juego te lo pide), y después pasame TODA la
salida de la consola desde un poco antes de entrar al combate
hasta un par de segundos después de que termine.
"""

import time

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.services.combat_service import CombatService, LECTURA_DESCARTADA


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
    print("Dejalo corriendo y hacé la prueba de captura ahora.")
    print("Ctrl+C para cortar cuando termines.")
    print()

    combat_service = CombatService(reader.memory)

    last_wild = "N/A"
    last_combat_active = None

    try:
        while True:

            wild_result = combat_service.read_wild_flag()
            total_caught = reader.read_total_caught_count()

            if wild_result is LECTURA_DESCARTADA:
                wild_display = "DESCARTADA"
                combat_active_now = last_combat_active
            elif wild_result is None:
                wild_display = "sin combate"
                combat_active_now = False
            elif wild_result is True:
                wild_display = "SALVAJE"
                combat_active_now = True
            else:
                wild_display = "entrenador"
                combat_active_now = True

            changed = (
                wild_display != last_wild
                or combat_active_now != last_combat_active
            )

            marker = " <-- CAMBIO" if changed else ""

            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"combate={wild_display:12s} "
                f"total_caught={total_caught}"
                f"{marker}"
            )

            last_wild = wild_display
            last_combat_active = combat_active_now

            time.sleep(0.2)

    except KeyboardInterrupt:
        print()
        print("Cortado. Pasame toda la salida de arriba.")


if __name__ == "__main__":
    main()

"""
Diagnóstico paso a paso de AzaharReader.connect(), sin tragarse
ninguna excepción -- a diferencia de connect() (que envuelve TODO
en un try/except Exception y devuelve False para cualquier falla,
sea cual sea), este script hace cada paso por separado y muestra el
error real si algo falla.

Contexto: listar_procesos_azahar.py (que solo llama
Citra().process_list()) encuentra bien el proceso, pero
observar_cajas_pc_contiguas.py (que usa AzaharReader().connect(),
un paso más: además de listar procesos, llama citra.set_process())
falla con el mismo mensaje genérico. Este script separa esos dos
pasos para ver cuál de los dos es el que realmente falla.

USO:
    python -m tools.probes.party.diagnosticar_connect
"""

from app.readers.citra import Citra
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


KNOWN_PROCESS_NAMES = (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


def main():
    print("================================")
    print("   DIAGNOSTICAR connect()")
    print("================================")
    print()

    citra = Citra()

    print("Paso 1: process_list()...")

    try:
        processes = citra.process_list()
    except Exception as error:
        print(f"  FALLO en process_list(): {error!r}")
        return

    print(f"  OK -- {len(processes)} proceso(s) encontrado(s).")

    process_id = None
    process_name_found = None

    for pid, data in processes.items():
        title_id, process_name = data
        print(
            f"    process_id={pid}  title_id={title_id}  "
            f"process_name={process_name!r}"
        )

        if process_name in KNOWN_PROCESS_NAMES:
            process_id = pid
            process_name_found = process_name

    print()

    if process_id is None:
        print(
            "  Ninguno de los procesos listados coincide con "
            f"{KNOWN_PROCESS_NAMES} -- acá terminaría "
            "find_game_process() devolviendo None."
        )
        return

    print(
        f"Paso 2: set_process({process_id}) "
        f"(juego detectado: {process_name_found!r})..."
    )

    try:
        citra.set_process(process_id)
    except Exception as error:
        print(f"  FALLO en set_process(): {error!r}")
        print(
            "  Este es probablemente el paso que está fallando en "
            "observar_cajas_pc_contiguas.py -- connect() lo trata "
            "igual que si nunca hubiera encontrado el proceso."
        )
        return

    print("  OK -- set_process() no lanzó excepción.")
    print()

    print("Paso 3: get_process() (confirmar que quedó seleccionado)...")

    try:
        selected = citra.get_process()
    except Exception as error:
        print(f"  FALLO en get_process(): {error!r}")
        return

    print(f"  OK -- proceso seleccionado ahora: {selected}")
    print()
    print("Todo el camino de connect() funcionó paso a paso.")
    print(
        "Si observar_cajas_pc_contiguas.py sigue fallando con esto "
        "en verde, avisar -- sería un tercer problema distinto."
    )


if __name__ == "__main__":
    main()

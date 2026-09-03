"""
Imprime el Title ID real del proceso de juego detectado por
Azahar -- para el campo "Región" del panel "Conectado" de la GUI
v2 (31/08/2026).

El Title ID es un identificador de 8 bytes que Nintendo asigna por
versión + región del cartucho (no es un dato de la partida en
RAM -- es metadata del ROM, así que una vez confirmado no hace
falta volver a validarlo, a diferencia de una dirección de
memoria). `citra.py` ya lo recibe en cada respuesta de
`process_list()` (mismo protocolo UDP que usa
`find_game_process()`), simplemente no se guardaba en ningún
lado hasta ahora.

USO:
    Con el juego cargado en Azahar (Alpha Sapphire u Omega Ruby,
    cualquiera de los dos sirve para esta prueba), corré:

    python -m tools.probes.memory.imprimir_title_id_juego

    Copiá el valor de TITLE ID (HEX) que imprime y pasáselo a
    Claude junto con qué versión y qué región es tu copia (por
    ejemplo "Alpha Sapphire, versión física en español de
    España" o "Omega Ruby, eShop"). Con eso alcanza para armar la
    tabla de Title ID -> región sin adivinar nada.

No hace falta correr esto por separado para Alpha Sapphire Y
Omega Ruby en la misma sesión -- cada vez que cambiás de versión
en la pantalla de Bienvenida y volvés a conectar, podés correr
este probe de nuevo para esa versión.
"""

from app.core.config import Config
from app.readers.citra import Citra


def main():
    print("=========================================")
    print("   TITLE ID DEL JUEGO DETECTADO EN AZAHAR")
    print("=========================================")
    print()

    config = Config()
    process_name = config.get(
        "azahar", "process_name", default="sango-2"
    )

    print(f"Buscando proceso configurado en config.json: {process_name!r}")
    print()

    citra = Citra()

    try:
        processes = citra.process_list()
    except Exception as error:
        print(f"No se pudo conectar con Azahar: {error}")
        print(
            "Confirmá que Azahar está abierto, con el juego "
            "cargado, y que la interfaz UDP de depuración está "
            "habilitada (puerto 45987)."
        )
        return

    match = None

    for process_id, data in processes.items():
        title_id, found_name = data

        if found_name == process_name:
            match = (process_id, title_id, found_name)
            break

    if match is None:
        print(
            f"No se encontró ningún proceso llamado {process_name!r} "
            "entre los procesos que reporta Azahar. ¿Está el juego "
            "realmente cargado (no solo el menú de Azahar)?"
        )
        print()
        print("Procesos encontrados:")
        for process_id, data in processes.items():
            title_id, found_name = data
            print(
                f"  process_id={process_id}   "
                f"title_id=0x{title_id:016X}   "
                f"process_name={found_name!r}"
            )
        return

    process_id, title_id, found_name = match

    print("Encontrado:")
    print(f"  process_name : {found_name!r}")
    print(f"  process_id   : {process_id}")
    print(f"  TITLE ID (HEX): 0x{title_id:016X}")
    print(f"  title_id (dec): {title_id}")
    print()
    print(
        "Pasale ese TITLE ID (HEX) a Claude junto con qué versión "
        "y qué región/idioma es tu copia del juego."
    )


if __name__ == "__main__":
    main()

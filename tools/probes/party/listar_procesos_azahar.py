"""
Lista TODOS los procesos que ve Azahar por UDP, sin filtrar por
ningún nombre en particular -- para encontrar bajo qué nombre
interno corre Omega Ruby (el proyecto asume "sango-2" por defecto,
que es el nombre confirmado para Alpha Sapphire; no hay garantía
de que Omega Ruby use el mismo).

USO:
    python -m tools.probes.party.listar_procesos_azahar

    Con Omega Ruby ya abierto en Azahar, corré esto y buscá en la
    lista cuál proceso corresponde al juego (probablemente el
    único con un título reconocible, o el que tenga un
    process_name distinto a "sango-2"). Copiá ese process_name
    exacto.

Una vez que tengas el nombre real, actualizalo en `config.json`:

    {
      "azahar": {
        "process_name": "EL_NOMBRE_QUE_ENCONTRASTE_ACA"
      }
    }

No hace falta tocar ningún código -- `Application` ya lee ese
valor de config.json (sección 4/17 del Documento Maestro).
"""

from app.readers.citra import Citra


def main():
    print("================================")
    print("   LISTAR PROCESOS EN AZAHAR")
    print("================================")
    print()

    citra = Citra()

    try:
        processes = citra.process_list()
    except Exception as error:
        print(f"No se pudo conectar con Azahar: {error}")
        print(
            "Confirmá que Azahar está abierto, con Omega Ruby "
            "corriendo, y que la interfaz UDP de depuración está "
            "habilitada (puerto 45987)."
        )
        return

    if not processes:
        print(
            "Azahar respondió, pero no devolvió ningún proceso. "
            "¿Está el juego realmente cargado (no solo el menú "
            "de Azahar)?"
        )
        return

    print(f"Procesos encontrados: {len(processes)}")
    print()

    for process_id, data in processes.items():
        title_id, process_name = data
        print(
            f"  process_id={process_id}   "
            f"title_id={title_id}   "
            f"process_name={process_name!r}"
        )

    print()
    print(
        "Buscá arriba el que corresponda al juego (probablemente "
        "el único con nombre reconocible, o el que sea distinto "
        "de 'sango-2') y usá ese texto exacto como process_name "
        "en config.json."
    )


if __name__ == "__main__":
    main()

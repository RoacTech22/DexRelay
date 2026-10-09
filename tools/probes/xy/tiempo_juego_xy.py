"""
P7 (paridad X/Y, 09/10/2026): comprobar que DexRelay encuentra el
archivo de guardado de Pokémon X/Y en la carpeta de Azahar y que PKHeX
lo lee (tiempo de juego).

Hasta hoy esto solo se probó con ORAS. El código es genérico (el
Title ID sale del perfil y PKHeX reconoce el guardado por su tamaño),
pero "nada se da por bueno sin medirlo": este probe lo comprueba para
los cuatro juegos soportados.

Solo lectura: no escribe nada ni necesita Azahar abierto (lee el
archivo de guardado en disco; el bridge de PKHeX debe estar publicado).

Para cada juego informa:
  * si `find_save_file` encontró el archivo y cuál es (ruta, tamaño,
    fecha de modificación);
  * si no lo encontró, qué carpetas de juegos 3DS hay realmente bajo
    `title/00040000/` en las raíces conocidas (para ver el Title ID real);
  * el tiempo de juego que devuelve `PlaytimeService` (y, por tanto,
    PKHeX).

El tiempo es el del ÚLTIMO GUARDADO: para comparar, guarda la partida
en el juego y mira el tiempo que muestra el menú de Guardar/Continuar.

Uso (desde la raíz del proyecto):

    python tools/probes/xy/tiempo_juego_xy.py

Pega en el chat el texto que imprime.
"""

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

JUEGOS = (
    ("sango-1", "Alpha Sapphire"),
    ("sango-2", "Omega Ruby"),
    ("kujira-1", "Pokémon X"),
    ("kujira-2", "Pokémon Y"),
)


def formatear_tiempo(playtime):
    """Texto legible del dict que devuelve PlaytimeService.get_playtime."""
    if not playtime or not playtime.get("available"):
        razon = (playtime or {}).get("reason", "sin motivo")
        return f"NO disponible ({razon})"

    return (
        f"{playtime.get('hours', 0)} h "
        f"{playtime.get('minutes', 0):02d} min "
        f"{playtime.get('seconds', 0):02d} s"
    )


def describir_archivo(ruta):
    """Ruta, tamaño y fecha de un archivo de guardado (función pura de E/S mínima)."""
    ruta = Path(ruta)
    estado = ruta.stat()

    return {
        "ruta": str(ruta),
        "bytes": estado.st_size,
        "modificado": datetime.fromtimestamp(estado.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }


def titulos_presentes(raices, alto="00040000"):
    """
    {raiz: [Title ID bajo, ...]} de lo que hay bajo
    `<raiz>/Nintendo 3DS/*/*/title/<alto>/`. Sirve de diagnóstico cuando
    no se encuentra el guardado de un juego.
    """
    resultado = {}

    for raiz in raices:
        raiz = Path(raiz)

        if not raiz.exists():
            continue

        bajos = set()

        for carpeta in raiz.glob(f"Nintendo 3DS/*/*/title/{alto}/*"):
            if carpeta.is_dir():
                bajos.add(carpeta.name.lower())

        resultado[str(raiz)] = sorted(bajos)

    return resultado


def analizar_juego(clave, nombre, buscar, servicio):
    """
    Informe de un juego. `buscar(clave)` -> Path|None y
    `servicio.get_playtime(clave)` -> dict, inyectados para poder probar
    esta lógica sin disco ni bridge.
    """
    ruta = buscar(clave)

    informe = {
        "clave": clave,
        "juego": nombre,
        "encontrado": ruta is not None,
        "archivo": None,
        "tiempo": None,
    }

    if ruta is not None:
        try:
            informe["archivo"] = describir_archivo(ruta)
        except OSError as error:
            informe["archivo"] = {"ruta": str(ruta), "error": repr(error)}

    informe["tiempo"] = servicio.get_playtime(clave)

    return informe


def formatear(informes, titulos):
    lineas = []

    for informe in informes:
        lineas.append(f"=== {informe['juego']} ({informe['clave']}) ===")

        if informe["encontrado"]:
            archivo = informe["archivo"] or {}
            lineas.append(f"  archivo: {archivo.get('ruta')}")
            lineas.append(
                f"  tamaño: {archivo.get('bytes')} bytes  "
                f"modificado: {archivo.get('modificado')}"
            )
        else:
            lineas.append("  archivo de guardado: NO encontrado")

        lineas.append(f"  tiempo de juego: {formatear_tiempo(informe['tiempo'])}")
        lineas.append("")

    if any(not i["encontrado"] for i in informes):
        lineas.append("Carpetas de juegos 3DS presentes (Title ID bajo):")

        if not titulos:
            lineas.append("  (ninguna raíz de Azahar/Citra encontrada)")

        for raiz, bajos in titulos.items():
            lineas.append(f"  {raiz}")
            lineas.append(f"    {', '.join(bajos) if bajos else '(vacío)'}")

    return "\n".join(lineas).rstrip()


def main() -> int:
    from app.services import save_file_locator
    from app.services.playtime_service import PlaytimeService

    servicio = PlaytimeService()

    informes = [
        analizar_juego(
            clave, nombre, save_file_locator.find_save_file, servicio
        )
        for clave, nombre in JUEGOS
    ]

    raices = (
        save_file_locator._candidate_appdata_roots()
        + save_file_locator._candidate_linux_roots()
    )

    print(formatear(informes, titulos_presentes(raices)))

    return 0


if __name__ == "__main__":
    sys.exit(main())

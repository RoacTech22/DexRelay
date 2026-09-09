"""
Confirma (o descarta) si el fix de idioma del bridge PKHeX
(`GameInfo.Strings = GameInfo.GetStrings("es")`, Program.cs,
03/09/2026) resolvió DEL TODO los nombres de movimiento en
español -- pendiente heredado desde el Documento Maestro del
04/09/2026, nunca confirmado en vivo hasta ahora.

IMPORTANTE -- esto es DISTINTO del caso ya resuelto de los
movimientos de líderes de gimnasio (data/gym_leaders.json +
MOVE_NAME_ES en app.js/leader_team_window.js): ese es un dataset
estático curado a mano con exactamente los 64 movimientos que usan
los 8 líderes, ya completo, no hace falta tocarlo. Esto de acá
prueba la fuente real que usa el EQUIPO/CAJA del jugador (bridge
PKHeX vía GameInfo.Strings.Move), que nunca se probó a fondo --
son ~700+ movimientos posibles, no 64.

NO necesita el emulador corriendo ni ningún save cargado -- el
bridge resuelve esto directo desde PKHeX.Core, sin tocar memoria de
Azahar. Sí necesita el bridge publicado (o `dotnet run` en modo
desarrollo) andando en Windows -- por eso lo corre el usuario, no
Claude (el sandbox donde se escribió esto no tiene .NET ni puede
correr un .exe de Windows).

Método: para cada movimiento real (id 1 en adelante, tope
descubierto pidiendo un id fuera de rango), compara el nombre que
devuelve el bridge contra una CONJETURA del nombre en inglés
reconstruida desde el identifier de PokéAPI ya curado en
data/move_descriptions.json (ej. "karate-chop" -> "Karate Chop").
Si el nombre del bridge coincide con la conjetura en inglés, es una
señal fuerte (no 100% infalible -- unos pocos movimientos podrían
compartir grafía en los dos idiomas por casualidad) de que ESE
movimiento puntual quedó sin traducir.

CÓMO USARLO:

    python -m tools.probes.verificar_nombres_movimiento_es

Reporta:
    - Cuántos movimientos se revisaron en total.
    - Lista de los que coinciden con la conjetura en inglés
      (sospechosos de no estar traducidos).
    - Si la lista sale vacía -> el fix ya resolvió todo, se puede
      cerrar este pendiente sin tocar nada más.
    - Si aparecen varios -> confirma que quedan huecos reales en el
      diccionario "es" embebido de PKHeX.Core, y ahí sí hace falta
      pensar una tabla acotada (ver la idea original del Documento
      Maestro 04/09: acotada a lo que el equipo real del usuario
      use, no las ~700 completas).

HALLAZGO REAL (09/09/2026, primera corrida): data/move_descriptions.json
trae 18 ids >= 10000 (extensiones propias de PokéAPI, variantes que
no tienen Move ID real en PKHeX.Core para esta generación) -- el
bridge no los conoce y tira error. Se descartan antes de preguntarle
al bridge por ellos (no forman parte de los ~937 movimientos reales
de todos modos).
"""

import json

from app.core import paths
from app.services.pkhex.bridge import PKHeXBridge


def guess_english_display_name(identifier):
    """
    Reconstruye una conjetura de cómo se vería el nombre en inglés
    a partir del identifier de PokéAPI (ej. "karate-chop" ->
    "Karate Chop", "u-turn" -> "U Turn"). No es exacta al 100% para
    casos con guión real en el nombre visible (ej. "U-turn"), pero
    alcanza como heurística de comparación -- un falso negativo acá
    (la conjetura no matchea aunque el movimiento siga en inglés)
    se notaría igual mirando la lista completa impresa.
    """

    words = identifier.split("-")
    return " ".join(word.capitalize() for word in words)


def load_identifiers():
    """
    Carga data/move_descriptions.json (ya curado, 937 movimientos)
    solo para sacar el identifier en inglés de cada id -- no se
    toca ni se depende de sus descripciones.
    """

    data_path = paths.path("data", "move_descriptions.json")

    with open(data_path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    return {int(move_id): entry["name"] for move_id, entry in raw.items()}


def main():

    identifiers = load_identifiers()

    # Los ids >= 10000 son extensiones propias de PokéAPI (variantes
    # Z-move/GMax/etc, ver hallazgo real: move_descriptions.json trae
    # 18 de estos) -- no existen como Move ID real en PKHeX.Core para
    # esta generación, así que ni vale la pena preguntarle al bridge
    # por ellos.
    identifiers = {
        move_id: name
        for move_id, name in identifiers.items()
        if move_id < 10000
    }

    max_id = max(identifiers)

    print(
        f"Revisando {max_id} movimientos contra el bridge PKHeX "
        f"(esto puede tardar unos segundos, es 1 ida y vuelta por "
        f"movimiento)...\n"
    )

    bridge = PKHeXBridge()
    bridge.start()

    suspicious = []
    checked = 0
    errors = []

    try:
        for move_id in range(1, max_id + 1):

            identifier = identifiers.get(move_id)

            if not identifier:
                continue

            result = None

            try:
                result = bridge.move_details(move_id)
            except RuntimeError as error:
                errors.append((move_id, identifier, str(error)))
                continue

            if not result or "error" in result:
                errors.append((move_id, identifier, result))
                continue

            checked += 1

            spanish_name = result.get("name", "")
            english_guess = guess_english_display_name(identifier)

            if spanish_name.strip().lower() == english_guess.strip().lower():
                suspicious.append(
                    (move_id, identifier, spanish_name)
                )
    finally:
        bridge.stop()

    print(f"Revisados: {checked} / {max_id}")

    if errors:
        print(f"\nCon error de bridge ({len(errors)}):")
        for move_id, identifier, result in errors[:20]:
            print(f"  id={move_id} ({identifier}): {result}")
        if len(errors) > 20:
            print(f"  ... y {len(errors) - 20} más.")

    if not suspicious:
        print(
            "\nOK -- ningún movimiento coincidió con su conjetura "
            "en inglés. El fix de idioma del bridge parece estar "
            "resolviendo todos los nombres reales en español."
        )
        return

    print(
        f"\nSOSPECHOSOS de seguir en inglés ({len(suspicious)}):"
    )
    for move_id, identifier, spanish_name in suspicious:
        print(f"  id={move_id} ({identifier}): {spanish_name!r}")

    print(
        "\nSi esta lista tiene contenido real (y no son solo "
        "coincidencias de grafía entre idiomas), confirma que "
        "GameInfo.Strings.Move en \"es\" tiene huecos reales -- "
        "avisar para armar la tabla acotada."
    )


if __name__ == "__main__":
    main()

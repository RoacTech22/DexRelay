"""
Verifica en vivo las dos acciones nuevas del bridge agregadas en
Fase A (06/09/2026, roadmap secciones 4.1/4.2): `species_details` y
`move_details`. Se escribieron y compilaron esa sesión (ver
Documento Maestro Fase A, sección 4: "compiló limpio... Confirmado,
no pendiente de verificación"), pero esa confirmación fue solo de
COMPILACIÓN -- nunca se corrió una petición real y se miró la
respuesta completa. Antes de construir el modal de la GUI encima
(Fase C) conviene confirmar que la forma real del JSON es la
esperada, mismo criterio de siempre ("nunca un dato sin confirmar").

A diferencia de la mayoría de los probes de este proyecto, este NO
necesita Azahar corriendo -- species_details/move_details no leen
memoria de ningún juego, resuelven todo desde las tablas internas de
PKHeX.Core (PersonalTable/EvolutionTree/MoveInfo). Solo hace falta
que el bridge .NET pueda arrancar (dotnet run, o el .exe publicado
si ya existe en releases/pkhex-bridge/).

Especies elegidas a propósito para estresar casos raros:
    - Bulbasaur (1): caso simple, un tipo, evolución por nivel.
    - Eevee (133): DOBLE tipo NO (mono-tipo Normal, pero con 3
      habilidades reales -- Adaptabilidad/Cuerpo Puro/Anticipación
      en algunas gens -- y sobre todo MUCHAS evoluciones con
      métodos distintos entre sí: nivel+objeto (piedras) y
      felicidad -- el caso más rico para revisar que `methodKey`/
      `level`/`argument` salgan coherentes para cada rama).
    - Charizard (6): doble tipo real (Fuego/Volador), para
      confirmar que type2Key no sale vacío cuando corresponde.

Movimientos elegidos:
    - Placaje/Tackle (33): movimiento físico simple, PP bajo.
    - Rayo/Thunderbolt (85): especial, para cruzar con
      move_data.json vía merge_move_details() y confirmar que
      power/accuracy/categoryKey salen pobladas.
    - Gruñido/Growl (45): movimiento de estado (category="Status"),
      para confirmar que categoryKey distingue esto de físico/
      especial.

CÓMO USARLO:

    python -m tools.probes.pkhex_species_move_details_probe

Mirar la salida completa de cada bloque y confirmar a ojo que:
    - Los tipos/habilidades/stats base coinciden con lo que
      cualquier Pokédex real muestra para esa especie.
    - Las evoluciones de Eevee salen con methodKey/level/argument
      coherentes (ej. una rama por nivel de felicidad no debería
      tener el mismo methodKey que una rama por piedra).
    - power/accuracy/categoryKey de move_data.json coinciden con
      los valores reales de Generación 6 (no los actuales -- ver
      Documento Maestro Fase A, sección 5, el caso de Recover que
      motivó fijar los valores a Gen 6 en vez de traer lo último de
      PokéAPI).

Si algo sale vacío/raro, es la señal de que hay que ajustar
Program.cs antes de construir el modal encima (más barato arreglarlo
acá que después de haber cableado media GUI sobre un dato mal
resuelto).
"""

from app.services.pkhex.bridge import PKHeXBridge
from app.services.move_data import MoveDataCatalog, merge_move_details


SPECIES_TO_CHECK = [
    (1, "Bulbasaur"),
    (133, "Eevee"),
    (6, "Charizard"),
]

MOVES_TO_CHECK = [
    (33, "Placaje/Tackle"),
    (85, "Rayo/Thunderbolt"),
    (45, "Gruñido/Growl"),
]


def print_species(bridge, species_id, label):

    print(f"--- species_details({species_id}) [{label}] ---")

    result = bridge.species_details(species_id)

    print(result)
    print()


def print_move(bridge, catalog, move_id, label):

    print(f"--- move_details({move_id}) [{label}] ---")

    bridge_result = bridge.move_details(move_id)

    print("Bridge (nombre/tipo/PP):", bridge_result)

    merged = merge_move_details(bridge_result, catalog)

    print(
        "Combinado con move_data.json "
        "(potencia/precisión/categoría):",
        merged,
    )
    print()


def main():
    print("=================================================")
    print("   VERIFICAR species_details / move_details")
    print("=================================================")
    print()

    bridge = PKHeXBridge()
    catalog = MoveDataCatalog()

    for species_id, label in SPECIES_TO_CHECK:
        print_species(bridge, species_id, label)

    for move_id, label in MOVES_TO_CHECK:
        print_move(bridge, catalog, move_id, label)

    bridge.stop()

    print("Prueba finalizada.")


if __name__ == "__main__":
    main()

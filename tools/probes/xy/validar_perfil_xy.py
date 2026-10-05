"""
Bloque 15 (ruta multijuego, 04/10/2026): validar EN VIVO las direcciones
del perfil de Pokémon X/Y con el código REAL de la app (AzaharReader,
BadgesService, CombatService), no con un escaneo aparte. Lo que se vea
aquí es exactamente lo que verá DexRelay.

Solo lectura. USO (X o Y cargado en una partida, Azahar abierto):

    python tools/probes/xy/validar_perfil_xy.py --watch

--watch repite cada segundo e imprime SOLO cuando algo cambia. Hazlo por
partes y anota el resultado de cada una:

  1. Sin hacer nada: entrenador, equipo y cantidad deben coincidir con
     tu partida; "medallas" debe dar el valor de tu partida (X=3, Y=8 en
     las partidas de prueba) y la zona debe ser un número estable.
  2. Cambia de zona (entra a otra ruta/ciudad): "zona" debe cambiar (y
     "zona_espejo", si existe, igual).
  3. Captura un Pokémon: "capturas" debe subir exactamente +1 y
     "ultimo_capturado" debe ser el que atrapaste. Luego haz un combate
     salvaje SIN capturar (derrota/huye/falla una bola): "capturas" NO
     debe subir. Si sube, el favorito 0x08C82AC0 no sirve; prueba con
     --capturas 0x08C82B24 o --capturas 0x08C82CAC.
  4. Entra a un combate salvaje: "combate" pasa a salvaje y "hp" debe
     coincidir con el HP actual de tu Pokémon activo; "rival" debe ser la
     especie salvaje. En uno de entrenador: "combate" = entrenador. Al
     terminar vuelve a "sin combate". Prueba encuentros raros: horda,
     doble, Safari de Amigos, legendario.
  5. Bolsa: "pokeballs" True si tienes alguna Poké Ball.

Opciones: --process kujira-1|kujira-2 (por defecto se detecta solo),
--capturas 0xDIRECCION (leer otro candidato del contador u32).
Pega la salida completa en el chat.
"""

import argparse
import struct
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.games.registry import get_profile  # noqa: E402
from app.readers.azahar_reader import AzaharReader  # noqa: E402
from app.services.badges_service import BadgesService  # noqa: E402
from app.services.combat_service import (  # noqa: E402
    LECTURA_DESCARTADA,
    CombatService,
)


def parse_int(value):
    return int(value, 0)


def describe_combat(wild):
    if wild is LECTURA_DESCARTADA:
        return "lectura descartada"
    if wild is None:
        return "sin combate"
    return "SALVAJE" if wild else "ENTRENADOR"


def read_u16(reader, address):
    if address is None:
        return None

    data = reader.memory.read(address, 2)

    if data is None or len(data) != 2:
        return None

    return struct.unpack("<H", data)[0]


def snapshot(reader, badges, combat, captures_address):
    profile = reader.profile
    memory_map = profile.memory_map

    try:
        badge_state = badges.read_badges()
    except Exception as error:  # noqa: BLE001
        badge_state = f"error: {error}"

    party = reader.read_party()
    species = [
        slot.get("species") or slot.get("nickname")
        for slot in party
        if not slot.get("empty")
    ]

    captures = None

    if captures_address is not None:
        data = reader.memory.read(captures_address, 4)

        if data is not None and len(data) == 4:
            captures = struct.unpack("<I", data)[0]

    last = reader.read_last_caught()

    return {
        "entrenador": reader.read_trainer_identity(),
        "equipo": species,
        "medallas": (
            badge_state
            if isinstance(badge_state, str)
            else f"{badge_state['count']} (valor 0b{badge_state['value']:08b})"
        ),
        "zona": reader.read_current_zone_id(),
        "zona_espejo": read_u16(
            reader, memory_map.current_zone_id_mirror_address
        ),
        "capturas": captures,
        "ultimo_capturado": None if last is None else last.get("species"),
        "combate": describe_combat(combat.read_wild_flag()),
        "hp": combat.read(),
        "rival": reader.read_wild_rival_species(),
        "pokeballs": reader.read_has_pokeballs(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--capturas", type=parse_int, default=None)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()

    reader = AzaharReader(process_name=args.process)

    if not reader.connect():
        print("No se pudo conectar con Azahar / no se encontró X o Y.")
        return 1

    profile = reader.profile

    if profile is None or get_profile(reader.process_name) is None:
        print(f"El juego {reader.process_name!r} no tiene perfil.")
        return 1

    print(f"Juego: {profile.display_name}  (proceso {reader.process_name})")

    captures_address = (
        args.capturas
        if args.capturas is not None
        else profile.memory_map.total_caught_address
    )
    print(f"Contador de capturas leído en 0x{captures_address:08X}\n")

    badges = BadgesService(reader)
    combat = CombatService(
        reader.memory, profile_provider=lambda: reader.profile
    )

    previous = None

    while True:
        current = snapshot(reader, badges, combat, captures_address)

        if current != previous:
            print(time.strftime("[%H:%M:%S]"))

            for key, value in current.items():
                changed = (
                    previous is not None and previous.get(key) != value
                )
                print(f"  {'*' if changed else ' '} {key}: {value}")

            print(flush=True)
            previous = current

        if not args.watch:
            return 0

        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())

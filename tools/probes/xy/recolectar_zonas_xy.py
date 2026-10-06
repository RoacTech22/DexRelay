"""
P2 (paridad X/Y, 05/10/2026), paso B: recolectar la tabla ID de zona ->
lugar del catálogo de Kalos.

Por qué: la corrida de zonas_vs_lugares_xy.py (4 capturas, Pokémon Y) dio
un mapeo CONSISTENTE pero SIN offset fijo entre el ID de zona que se lee
de memoria y el lugar de encuentro de PKHeX (zona - lugar = 206, 215, 218
y 249), y el rival salvaje no trae lugar (0/52). La tabla hay que
recolectarla, como se hizo en ORAS. Pero para detectar "perdido" solo
importan las zonas donde EMPIEZA UN COMBATE SALVAJE, así que este
recolector NO te interrumpe en pueblos, edificios ni pasillos: solo
pregunta por zonas donde tuviste un combate salvaje y todavía no tienen
nombre.

Cómo se llena la tabla:
  - AUTOMÁTICO: cada captura da un par (zona, lugar) verificado con el
    campo Met_Location del Pokémon (igual que en zonas_vs_lugares_xy.py).
    Si una zona ya tenía otro lugar, avisa del CONFLICTO y no la pisa.
  - MANUAL: al terminar un combate salvaje en una zona sin nombre, te
    pregunta qué lugar es. Respuestas válidas:
        10          -> Ruta 10 (un número solo es SIEMPRE número de ruta)
        ruta 10     -> Ruta 10
        reflejos    -> Cueva Reflejos (si hay una sola coincidencia)
        id:56       -> el ID de lugar del catálogo (p. ej. 56)
        Enter       -> saltar por ahora (volverá a preguntar otro día)
        no          -> NO es un lugar de Nuzlocke (no volver a preguntar)
        salir       -> terminar y guardar

Solo lectura de memoria. USO (X o Y en el mapa; sirve cualquiera de los
dos, comparten la tabla):

    python tools/probes/xy/recolectar_zonas_xy.py

Juega normal: ve a cada ruta, cueva y zona de pesca/surf de la historia
y empieza un combate salvaje en cada una (puedes huir). En cuevas con
varios pisos/salas, un combate en CADA sala. Se guarda tras cada zona
nombrada en tools/probes/xy/zonas_recolectadas_xy.json y se retoma donde
quedó en la próxima corrida. Ctrl+C también guarda.
"""

import argparse
import json
import re
import struct
import sys
import time
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zonas_vs_lugares_xy import (  # noqa: E402
    DEFAULT_BOXES,
    POLL_SECONDS,
    SCAN_SECONDS,
    Observador,
    scan_party_and_boxes,
)

TABLE_PATH = Path(__file__).resolve().parent / "zonas_recolectadas_xy.json"


def normalize(text):
    """Minúsculas, sin tildes y con espacios simples."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    return re.sub(r"\s+", " ", text.lower()).strip()


def buscar_lugar(texto, catalogo):
    """
    Interpreta lo que escribe Ronald. `catalogo` = {id: nombre}.

    Devuelve (estado, ids):
      ("ok", [id])        una sola coincidencia
      ("varios", [ids])   ambiguo: hay que precisar
      ("nada", [])        sin coincidencias
    """
    raw = normalize(texto)

    if not raw:
        return ("nada", [])

    match = re.fullmatch(r"id\s*:\s*(\d+)", raw)

    if match:
        location_id = int(match.group(1))

        return ("ok", [location_id]) if location_id in catalogo else ("nada", [])

    # Un número solo = número de ruta (los IDs internos no los conoce
    # nadie; "10" no puede significar el lugar con ID 10).
    match = re.fullmatch(r"(?:ruta\s*)?(\d+)", raw)

    if match:
        raw = f"ruta {int(match.group(1))}"

    names = {i: normalize(n) for i, n in catalogo.items()}

    exact = [i for i, n in names.items() if n == raw]

    if len(exact) == 1:
        return ("ok", exact)

    partial = sorted(i for i, n in names.items() if raw in n)

    if len(partial) == 1:
        return ("ok", partial)

    if partial:
        return ("varios", partial)

    return ("nada", [])


class Tabla:
    """Tabla zona -> lugar con su fuente; se guarda en JSON."""

    def __init__(self):
        self.zonas = {}      # int zona -> {"lugar", "fuente"}
        self.descartadas = set()

    def registrar(self, zona, lugar, fuente):
        """'nuevo' | 'igual' | 'conflicto' (no pisa lo existente)."""
        actual = self.zonas.get(zona)

        if actual is None:
            self.zonas[zona] = {"lugar": lugar, "fuente": fuente}
            self.descartadas.discard(zona)
            return "nuevo"

        return "igual" if actual["lugar"] == lugar else "conflicto"

    def descartar(self, zona):
        self.descartadas.add(zona)

    def conocida(self, zona):
        return zona in self.zonas or zona in self.descartadas

    def to_json(self, catalogo):
        return {
            "nota": (
                "ID de zona (u16 de memoria) -> ID de lugar del catálogo "
                "de Kalos (app/games/xy/locations.py). Recolectado en vivo "
                "con recolectar_zonas_xy.py; fuente 'captura' = verificado "
                "con el Met_Location de un Pokémon capturado en esa zona."
            ),
            "zonas": {
                str(z): {
                    "lugar": d["lugar"],
                    "nombre": catalogo.get(d["lugar"], "?"),
                    "fuente": d["fuente"],
                }
                for z, d in sorted(self.zonas.items())
            },
            "no_aplica": sorted(self.descartadas),
        }

    @classmethod
    def from_json(cls, data):
        tabla = cls()

        for zona, d in (data.get("zonas") or {}).items():
            tabla.zonas[int(zona)] = {
                "lugar": int(d["lugar"]),
                "fuente": d.get("fuente", "manual"),
            }

        tabla.descartadas = {int(z) for z in data.get("no_aplica") or []}

        return tabla


def cargar(path=TABLE_PATH):
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            return Tabla.from_json(json.load(file))
    except (OSError, ValueError, KeyError, TypeError):
        return Tabla()


def guardar(tabla, catalogo, path=TABLE_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(tabla.to_json(catalogo), file, indent=2, ensure_ascii=False)
        file.write("\n")

    tmp.replace(path)


def preguntar(zona, catalogo, rival, input_fn=input):
    """
    Pregunta por una zona. Devuelve ("lugar", id) | ("no", None) |
    ("saltar", None) | ("salir", None). `input_fn` se inyecta en tests.
    """
    rival_txt = f" (rival: especie {rival})" if rival else ""

    while True:
        texto = input_fn(
            f"\nZona {zona} (0x{zona:X}){rival_txt}. ¿Qué lugar es? "
            "[10 / ruta 10 / nombre / id:NN / Enter=saltar / no / salir] > "
        )
        limpio = normalize(texto)

        if limpio == "":
            return ("saltar", None)
        if limpio == "salir":
            return ("salir", None)
        if limpio == "no":
            return ("no", None)

        estado, ids = buscar_lugar(texto, catalogo)

        if estado == "ok":
            print(f"  -> {ids[0]} {catalogo[ids[0]]}")
            return ("lugar", ids[0])

        if estado == "varios":
            print("  Varias coincidencias, precisa:")
            for i in ids[:12]:
                print(f"    {catalogo[i]}  (id:{i})")
        else:
            print("  No encontré ese lugar en el catálogo de Kalos.")


# ---------------------------------------------------------------------
# E/S (no se prueba sin Azahar)
# ---------------------------------------------------------------------

def main():
    from app.games.registry import get_profile
    from app.readers.azahar_reader import AzaharReader
    from app.services.combat_service import LECTURA_DESCARTADA, CombatService
    from app.services.kalos_locations_es import KALOS_LOCATION_NAMES_ES
    from app.services.pkhex.bridge import PKHeXBridge

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--cajas", type=int, default=DEFAULT_BOXES)
    args = parser.parse_args()

    catalogo = KALOS_LOCATION_NAMES_ES
    reader = AzaharReader(process_name=args.process)

    if not reader.connect():
        print("No se pudo conectar con Azahar / no se encontró X o Y.")
        return 1

    if get_profile(reader.process_name) is None:
        print(f"El juego {reader.process_name!r} no tiene perfil.")
        return 1

    try:
        bridge = PKHeXBridge.shared()
    except Exception as error:  # noqa: BLE001
        print(f"Sin bridge ({error!r}): no habrá pares automáticos por captura.")
        bridge = None

    tabla = cargar()
    print(
        f"Juego: {reader.profile.display_name}. Tabla cargada: "
        f"{len(tabla.zonas)} zonas, {len(tabla.descartadas)} marcadas 'no'."
    )

    combat = CombatService(reader.memory, profile_provider=lambda: reader.profile)
    observer = Observador()
    observer.baseline_pids = {
        pid: d["species"]
        for pid, d in scan_party_and_boxes(reader, None, boxes=args.cajas).items()
    }
    print(
        f"Línea base: {len(observer.baseline_pids)} Pokémon propios. "
        "Juega normal; solo te preguntaré tras combates salvajes en zonas "
        "sin nombre. Ctrl+C para terminar.\n",
        flush=True,
    )

    pairs_done = 0
    combat_zone = None
    last_rival = None
    por_preguntar = []
    last_scan = 0.0
    salir = False

    try:
        while not salir:
            now = time.time()

            observer.feed_zone(reader.read_current_zone_id())

            text = observer.feed_counter(reader.read_total_caught_count(), now)

            if text:
                print(time.strftime("[%H:%M:%S]"), text, flush=True)
                last_scan = 0.0

            wild = combat.read_wild_flag()

            if wild is True and combat_zone is None:
                combat_zone = observer.stable_zone
            elif wild is None and combat_zone is not None:
                if (
                    combat_zone is not None
                    and not tabla.conocida(combat_zone)
                    and combat_zone not in por_preguntar
                ):
                    por_preguntar.append(combat_zone)

                combat_zone = None

            if wild is True:
                species = reader.read_wild_rival_species()
                last_rival = species or last_rival

            if observer.pending is not None and now - last_scan >= SCAN_SECONDS:
                last_scan = now
                scan = scan_party_and_boxes(
                    reader,
                    bridge,
                    known_pids=observer.baseline_pids,
                    boxes=args.cajas,
                )
                observer.feed_scan(scan, time.time())

            # Pares nuevos de capturas -> tabla automática.
            while pairs_done < len(observer.pairs):
                pair = observer.pairs[pairs_done]
                pairs_done += 1

                if pair["fuente"] != "captura" or pair["zona"] is None:
                    continue

                result = tabla.registrar(pair["zona"], pair["lugar"], "captura")
                name = catalogo.get(pair["lugar"], "¿?")

                if result == "nuevo":
                    print(
                        f"[auto] zona {pair['zona']} (0x{pair['zona']:X}) -> "
                        f"{pair['lugar']} {name} (captura)",
                        flush=True,
                    )
                    guardar(tabla, catalogo)
                elif result == "conflicto":
                    print(
                        f"[CONFLICTO] zona {pair['zona']} ya era "
                        f"{tabla.zonas[pair['zona']]['lugar']} y la captura "
                        f"dice {pair['lugar']} {name}. No se pisa; "
                        "pégalo en el chat.",
                        flush=True,
                    )

            # Preguntas pendientes: solo fuera de combate y sin captura
            # esperando (así la captura nombra la zona sola).
            if (
                por_preguntar
                and combat_zone is None
                and wild is None
                and observer.pending is None
            ):
                zona = por_preguntar.pop(0)

                if tabla.conocida(zona):
                    continue

                kind, location_id = preguntar(zona, catalogo, last_rival)

                if kind == "lugar":
                    tabla.registrar(zona, location_id, "manual")
                    guardar(tabla, catalogo)
                elif kind == "no":
                    tabla.descartar(zona)
                    guardar(tabla, catalogo)
                elif kind == "salir":
                    salir = True

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        pass

    guardar(tabla, catalogo)
    print(
        f"\nGuardado en {TABLE_PATH}: {len(tabla.zonas)} zonas con lugar, "
        f"{len(tabla.descartadas)} 'no aplica'."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
P3 (paridad X/Y, 06/10/2026): ¿con qué SEÑALES llega a la memoria cada
origen especial de un Pokémon en Kalos? (inicial, fósil revivido, huevo,
regalo de historia, intercambio con NPC) y ¿se distinguen de una captura
salvaje normal?

Por qué existe: en ORAS el fósil se reconoce porque el lugar de
encuentro es Devon Corp, donde no hay pasto (ver
`SpecialRules.fossil_location_ids`). En Kalos ese truco no se puede dar
por bueno: el Laboratorio de Fósiles está en Pueblo Petroglifo, que tiene
costa con pesca. Nada se fija sin ver los datos reales (regla 2 de la
guía de paridad), así que este probe NO decide nada: registra, para cada
Pokémon que aparece o cambia en tu equipo o cajas, los campos del PK6
que podrían servir de señal, te pregunta cómo lo obtuviste y al final
dice qué valores se solapan con una captura salvaje.

Campos que registra (offsets del formato PK6, contrastados con el bridge
de PKHeX en cada Pokémon nuevo): especie, apodo crudo (incluye los
placeholders "Egg"/"Huevo" de un huevo o fósil recién creado), bit de
huevo, Egg_Location (0xD8), Met_Location (0xDA), nivel de encuentro
(0xDD), Poké Ball (0xDC), juego de origen (0xDF), nombre del OT (0xB0) y
la zona actual de memoria.

Solo lectura (no escribe memoria). USO, con X o Y cargado en el mapa:

    python tools/probes/xy/origenes_xy.py

Juega normal. Para cada origen que quieras comprobar, consíguelo y, cuando
el probe te pregunte ("¿Cómo lo obtuviste?"), responde con la etiqueta:

    inicial | salvaje | fosil | huevo | regalo | intercambio | otro | Enter=saltar

Lo más útil, en este orden: 1) un Pokémon SALVAJE capturado en Pueblo
Petroglifo pescando (para ver si se parece al fósil); 2) un FÓSIL
revivido en el Laboratorio de Fósiles de Pueblo Petroglifo; 3) un HUEVO
(recibido y, si puedes, ya nacido); 4) cada REGALO de historia que
tengas a mano; 5) un INTERCAMBIO con un NPC; 6) un salvaje cualquiera.
No hace falta todo en una sesión: el JSON se acumula si lo vuelves a
correr con --continuar. Ctrl+C termina, imprime el resumen y guarda
tools/probes/xy/salida/origenes_xy.json. Pega el resumen en el chat y
adjunta el JSON.

MODO INVENTARIO (sin jugar, sobre lo que YA tienes en equipo y cajas):

    python tools/probes/xy/origenes_xy.py --inventario

Lista los Pokémon propios de las familias de regalo y fósil de Kalos
(iniciales de Kanto, Riolu/Lucario, Lapras, Tyrunt/Amaura y sus
evoluciones) con los mismos campos, para medir la señal de cada regalo
sin tener que volver a conseguirlos. Con otras especies:
`--inventario 131,448` (números de la Pokédex nacional). Guarda
tools/probes/xy/salida/inventario_xy.json.
"""

import argparse
import json
import struct
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = Path(__file__).resolve().parent / "salida" / "origenes_xy.json"

PK6_SIZE = 232

# Offsets del PK6 descifrado (formato PKHeX).
NICKNAME_OFFSET = 0x40
NICKNAME_BYTES = 24
IV32_OFFSET = 0x74            # bit 30 = es huevo, bit 31 = tiene apodo
OT_NAME_OFFSET = 0xB0
OT_NAME_BYTES = 24
EGG_LOCATION_OFFSET = 0xD8
MET_LOCATION_OFFSET = 0xDA
BALL_OFFSET = 0xDC
MET_LEVEL_OFFSET = 0xDD       # bits 0-6 = nivel, bit 7 = género del OT
ORIGIN_GAME_OFFSET = 0xDF

POLL_SECONDS = 0.3
BOX_SCAN_SECONDS = 2.0
# Segundos sin cambios tras un Pokémon nuevo antes de preguntar.
ASK_AFTER_SECONDS = 4.0
# Segundos ausente del equipo y de las cajas para dar un Pokémon por ido.
VANISH_SECONDS = 6.0

ETIQUETAS = (
    "inicial", "salvaje", "fosil", "huevo", "regalo", "intercambio", "otro",
)


def _text(raw, offset, size):
    try:
        text = raw[offset:offset + size].decode("utf-16le", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""

    return text.split("\x00", 1)[0]


def pid_of(raw):
    if raw is None or len(raw) < 4:
        return None

    return struct.unpack_from("<I", raw, 0)[0]


def decodificar_origen(raw):
    """Campos de origen de un PK6 descifrado (232 bytes), o None."""
    if raw is None or len(raw) < PK6_SIZE:
        return None

    iv32 = struct.unpack_from("<I", raw, IV32_OFFSET)[0]

    return {
        "pid": pid_of(raw),
        "especie": struct.unpack_from("<H", raw, 0x08)[0],
        "apodo": _text(raw, NICKNAME_OFFSET, NICKNAME_BYTES),
        "es_huevo": bool((iv32 >> 30) & 1),
        "egg_location": struct.unpack_from("<H", raw, EGG_LOCATION_OFFSET)[0],
        "met_location": struct.unpack_from("<H", raw, MET_LOCATION_OFFSET)[0],
        "bola": raw[BALL_OFFSET],
        "nivel_encuentro": raw[MET_LEVEL_OFFSET] & 0x7F,
        "juego_origen": raw[ORIGIN_GAME_OFFSET],
        "ot": _text(raw, OT_NAME_OFFSET, OT_NAME_BYTES),
    }


# Campos cuyo cambio vale la pena registrar en un Pokémon ya conocido
# (así se ve el paso "Egg"/"Huevo" -> nombre real, o huevo -> nacido).
CAMPOS_VIGILADOS = (
    "especie", "apodo", "es_huevo", "egg_location", "met_location",
    "nivel_encuentro", "bola", "juego_origen",
)


class Seguimiento:
    """
    Lógica pura (sin Azahar ni bridge): recibe escaneos
    {pid: {"raw": bytes, "origen": "equipo 1" | "caja 3.7"}} y devuelve
    eventos. El bucle de E/S está en main().
    """

    def __init__(self):
        self.conocidos = {}   # pid -> campos decodificados
        self.visto = {}       # pid -> último instante en que se vio
        self.eventos = []
        self.ya_ido = set()

    def linea_base(self, escaneo, now):
        for pid, entry in escaneo.items():
            campos = decodificar_origen(entry["raw"])

            if campos is not None:
                self.conocidos[pid] = campos
                self.visto[pid] = now

    def alimentar(self, escaneo, now, zona=None):
        """Devuelve los eventos nuevos de este escaneo."""
        nuevos = []

        for pid, entry in escaneo.items():
            campos = decodificar_origen(entry["raw"])

            if campos is None:
                continue

            self.visto[pid] = now
            self.ya_ido.discard(pid)
            previo = self.conocidos.get(pid)

            if previo is None:
                evento = {
                    "t": now, "tipo": "nuevo", "pid": pid,
                    "origen": entry.get("origen"), "zona": zona,
                    "campos": campos,
                    "raw_hex": bytes(entry["raw"][:PK6_SIZE]).hex(),
                }
            else:
                cambios = {
                    campo: [previo[campo], campos[campo]]
                    for campo in CAMPOS_VIGILADOS
                    if previo[campo] != campos[campo]
                }

                if not cambios:
                    continue

                evento = {
                    "t": now, "tipo": "cambio", "pid": pid,
                    "origen": entry.get("origen"), "zona": zona,
                    "campos": campos, "cambios": cambios,
                }

            self.conocidos[pid] = campos
            self.eventos.append(evento)
            nuevos.append(evento)

        for pid, ultimo in list(self.visto.items()):
            if (
                pid not in escaneo
                and pid not in self.ya_ido
                and now - ultimo >= VANISH_SECONDS
            ):
                self.ya_ido.add(pid)
                evento = {
                    "t": now, "tipo": "ido", "pid": pid, "zona": zona,
                    "campos": self.conocidos.get(pid),
                }
                self.eventos.append(evento)
                nuevos.append(evento)

        return nuevos

    def etiquetar(self, pid, etiqueta):
        """Marca el evento 'nuevo' de ese Pokémon con cómo se obtuvo."""
        for evento in self.eventos:
            if evento["tipo"] == "nuevo" and evento["pid"] == pid:
                evento["etiqueta"] = etiqueta
                return True

        return False


def estados_previos(eventos, pid):
    """Apodos/bit de huevo por los que pasó un Pokémon (tras nacer o revivir)."""
    estados = []

    for evento in eventos:
        if evento["pid"] != pid or evento["tipo"] != "cambio":
            continue

        if "apodo" in evento["cambios"] or "es_huevo" in evento["cambios"]:
            estados.append(evento["cambios"])

    return estados


def resumen(eventos):
    """
    Texto del resumen: una línea por Pokémon nuevo etiquetado, agrupado por
    etiqueta, y los solapes de cada origen con las capturas salvajes.
    """
    nuevos = [
        e for e in eventos
        if e["tipo"] == "nuevo" and e.get("etiqueta") in ETIQUETAS
    ]
    lines = []

    for etiqueta in ETIQUETAS:
        grupo = [e for e in nuevos if e["etiqueta"] == etiqueta]

        if not grupo:
            continue

        lines.append(f"\n== {etiqueta} ({len(grupo)}) ==")

        for e in grupo:
            c = e["campos"]
            bridge = e.get("bridge") or {}
            transitorio = estados_previos(eventos, e["pid"])
            extra = f" previo={transitorio}" if transitorio else ""
            lines.append(
                f"  esp {c['especie']:>3} apodo={c['apodo']!r} "
                f"huevo={c['es_huevo']} met={c['met_location']}"
                f"({bridge.get('metLocationName', '?')}) "
                f"egg={c['egg_location']}({bridge.get('eggLocationName', '?')}) "
                f"nv={c['nivel_encuentro']} bola={c['bola']} "
                f"juego={c['juego_origen']} zona={e.get('zona')}{extra}"
            )

    salvajes = [e for e in nuevos if e["etiqueta"] == "salvaje"]
    lugares_salvajes = {e["campos"]["met_location"] for e in salvajes}
    veredicto = []

    for etiqueta in ("fosil", "regalo", "inicial", "huevo", "intercambio"):
        grupo = [e for e in nuevos if e["etiqueta"] == etiqueta]

        if not grupo:
            continue

        lugares = {e["campos"]["met_location"] for e in grupo}
        solapa = sorted(lugares & lugares_salvajes)
        veredicto.append(
            f"  {etiqueta}: lugares {sorted(lugares)}; "
            + (
                f"SOLAPAN con salvajes en {solapa} -> el lugar solo NO basta"
                if solapa
                else "sin solape con los salvajes registrados"
            )
        )

    if veredicto:
        lines.append("\n== Distinción frente a capturas salvajes ==")
        lines.extend(veredicto)

        if not salvajes:
            lines.append(
                "  (no hay salvajes etiquetados: el veredicto no es concluyente)"
            )

    return "\n".join(lines).lstrip("\n")


# Familias de los regalos de historia y fósiles de Kalos que se quieren
# medir: Bulbasaur/Charmander/Squirtle y sus evoluciones, Riolu/Lucario,
# Lapras, Tyrunt/Tyrantrum y Amaura/Aurorus.
INVENTARIO_ESPECIES = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 447, 448, 131, 696, 697, 698, 699,
)
INVENTARIO_PATH = Path(__file__).resolve().parent / "salida" / "inventario_xy.json"


def inventario(escaneo, especies):
    """Campos de origen de los Pokémon propios cuya especie está en `especies`."""
    filas = []

    for pid, entry in escaneo.items():
        campos = decodificar_origen(entry["raw"])

        if campos is None or campos["especie"] not in especies:
            continue

        filas.append({
            "origen": entry.get("origen"),
            "campos": campos,
            "raw_hex": bytes(entry["raw"][:PK6_SIZE]).hex(),
        })

    return sorted(
        filas, key=lambda f: (f["campos"]["especie"], f["campos"]["met_location"])
    )


def texto_inventario(filas):
    lines = []

    for fila in filas:
        c = fila["campos"]
        bridge = fila.get("bridge") or {}
        lines.append(
            f"esp {c['especie']:>3} apodo={c['apodo']!r} "
            f"met={c['met_location']}({bridge.get('metLocationName', '?')}) "
            f"egg={c['egg_location']}({bridge.get('eggLocationName', '?')}) "
            f"nv={c['nivel_encuentro']} bola={c['bola']} "
            f"juego={c['juego_origen']} ot={c['ot']!r} [{fila['origen']}]"
        )

    return "\n".join(lines) if lines else "(ninguno de esas especies)"


def guardar(eventos, path=OUTPUT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8", newline="\n") as file:
        json.dump({"eventos": eventos}, file, indent=1, ensure_ascii=False)
        file.write("\n")

    tmp.replace(path)


def cargar(path=OUTPUT_PATH):
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            return list(json.load(file).get("eventos") or [])
    except (OSError, ValueError, TypeError, AttributeError):
        return []


# ---------------------------------------------------------------------
# E/S (no se prueba sin Azahar)
# ---------------------------------------------------------------------

def escanear_equipo(reader):
    found = {}

    for slot in range(1, 7):
        pokemon = reader.read_pokemon_raw_for_slot(slot)

        if pokemon is not None and pokemon.raw_data:
            pid = pid_of(pokemon.raw_data)

            if pid:
                found[pid] = {"raw": pokemon.raw_data, "origen": f"equipo {slot}"}

    return found


def preguntar(evento, input_fn=input):
    c = evento["campos"]
    texto = input_fn(
        f"\nNuevo: especie {c['especie']} apodo={c['apodo']!r} "
        f"met={c['met_location']} egg={c['egg_location']} "
        f"nv={c['nivel_encuentro']} ({evento.get('origen')}). "
        f"¿Cómo lo obtuviste? [{'/'.join(ETIQUETAS)}/Enter=saltar/salir] > "
    ).strip().lower()

    if texto == "salir":
        return "salir"

    return texto if texto in ETIQUETAS else None


def main():
    from app.games.registry import get_profile
    from app.readers.azahar_reader import AzaharReader
    from app.services.pkhex.bridge import PKHeXBridge
    from zonas_vs_lugares_xy import scan_party_and_boxes

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument("--cajas", type=int, default=31)
    parser.add_argument(
        "--inventario", nargs="?", const="", default=None,
        help="lista los Pokémon propios de esas especies (sin jugar)",
    )
    parser.add_argument(
        "--continuar", action="store_true",
        help="suma a salida/origenes_xy.json en vez de empezar de cero",
    )
    args = parser.parse_args()

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
        print(f"Sin bridge ({error!r}): no habrá nombres de lugar de PKHeX.")
        bridge = None

    if args.inventario is not None:
        especies = (
            {int(x) for x in args.inventario.split(",") if x.strip()}
            if args.inventario.strip()
            else set(INVENTARIO_ESPECIES)
        )
        todos = {
            **scan_party_and_boxes(
                reader, None, boxes=args.cajas, include_last=False
            ),
            **escanear_equipo(reader),
        }
        filas = inventario(todos, especies)

        if bridge is not None:
            for fila in filas:
                try:
                    fila["bridge"] = bridge.met_location(
                        bytes.fromhex(fila["raw_hex"])
                    )
                except Exception:  # noqa: BLE001
                    fila["bridge"] = None

        print(texto_inventario(filas))
        guardar(filas, INVENTARIO_PATH)
        print(f"\nGuardado en {INVENTARIO_PATH} ({len(filas)} Pokémon).")

        return 0

    seg = Seguimiento()
    previos = cargar() if args.continuar else []
    now = time.time()
    cajas = scan_party_and_boxes(
        reader, None, boxes=args.cajas, include_last=False
    )
    seg.linea_base({**cajas, **escanear_equipo(reader)}, now)
    print(
        f"Juego: {reader.profile.display_name}. Línea base: "
        f"{len(seg.conocidos)} Pokémon propios. Juega normal; Ctrl+C para "
        "terminar.\n",
        flush=True,
    )

    por_preguntar = []
    ultimo_cambio = 0.0
    ultimo_cajas = now
    salir = False

    try:
        while not salir:
            now = time.time()

            if now - ultimo_cajas >= BOX_SCAN_SECONDS:
                ultimo_cajas = now
                cajas = scan_party_and_boxes(
                    reader, None, boxes=args.cajas, include_last=False
                )

            escaneo = {**cajas, **escanear_equipo(reader)}
            nuevos = seg.alimentar(
                escaneo, now, zona=reader.read_current_zone_id()
            )

            for evento in nuevos:
                ultimo_cambio = now
                c = evento["campos"] or {}

                if evento["tipo"] == "nuevo" and bridge is not None:
                    try:
                        evento["bridge"] = bridge.met_location(
                            bytes.fromhex(evento["raw_hex"])
                        )
                    except Exception:  # noqa: BLE001
                        evento["bridge"] = None

                    b = evento["bridge"] or {}

                    if b and (
                        b.get("metLocationId") != c.get("met_location")
                        or b.get("eggLocationId") != c.get("egg_location")
                    ):
                        print(
                            "[AVISO] el bridge no coincide con los offsets "
                            f"del PK6: bridge met={b.get('metLocationId')} "
                            f"egg={b.get('eggLocationId')}",
                            flush=True,
                        )

                print(
                    time.strftime("[%H:%M:%S]"), evento["tipo"].upper(),
                    f"esp {c.get('especie')} apodo={c.get('apodo')!r} "
                    f"huevo={c.get('es_huevo')} met={c.get('met_location')} "
                    f"egg={c.get('egg_location')} nv={c.get('nivel_encuentro')} "
                    f"zona={evento.get('zona')} {evento.get('cambios', '')}",
                    flush=True,
                )

                if evento["tipo"] == "nuevo":
                    por_preguntar.append(evento)

            if por_preguntar and now - ultimo_cambio >= ASK_AFTER_SECONDS:
                evento = por_preguntar.pop(0)
                etiqueta = preguntar(evento)

                if etiqueta == "salir":
                    salir = True
                elif etiqueta:
                    seg.etiquetar(evento["pid"], etiqueta)
                    guardar(previos + seg.eventos)

                ultimo_cambio = time.time()

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        pass

    eventos = previos + seg.eventos
    guardar(eventos)
    print(f"\nGuardado en {OUTPUT_PATH} ({len(eventos)} eventos).\n")
    print(resumen(eventos))

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
P2 (paridad X/Y, 05/10/2026), paso A: ¿cómo se relaciona el ID de ZONA
que se lee de memoria (u16 en 0x08C670AE) con el LUGAR DE ENCUENTRO
(Met_Location) que PKHeX/el juego escriben en un Pokémon?

Por qué existe: la detección automática de "perdido" necesita el nombre
de la ruta donde empieza un combate salvaje, y ese nombre tiene que
coincidir con la fila del catálogo de P1 (que usa los IDs de lugar de
PKHeX: Ruta 1 = 8, Pueblo Acuarela = 10...). Los IDs de zona observados
(Ruta 1 = 0x102, Pueblo Acuarela = 0x08...) no se parecen a primera
vista. Este probe NO asume nada: junta pares (zona, lugar) de dos
fuentes y al final dice qué relación hay.

  A. CAPTURA: cuando el contador de capturas sube +1, espera a que el
     Pokémon nuevo aparezca en el equipo o en las cajas y toma su
     Met_Location (campo u16 en 0xDA del PK6 descifrado; se contrasta
     con el ID que devuelve el bridge de PKHeX).
  B. RIVAL SALVAJE: al empezar un combate salvaje lee el PK6 del rival
     (primera dirección de `wild_rival_addresses`) y mira si YA trae
     Met_Location. Si lo trae, cada encuentro (aunque huyas o lo
     derrotes) da un par sin necesidad de capturar, y hasta podría
     sustituir a la tabla de zonas.

Solo lectura (no escribe memoria). USO, con X o Y cargado en el mapa:

    python tools/probes/xy/zonas_vs_lugares_xy.py

Juega normal por rutas y cuevas DISTINTAS:
  - entra en 6–10 lugares con hierba/cueva/agua distintos y empieza un
    combate salvaje en cada uno (puedes huir);
  - captura al menos un Pokémon en 3–4 de esos lugares (lugares
    distintos; en la misma ruta, una captura en hierba y otra pescando
    o surfeando, si puedes);
  - pasa por algún pueblo/ciudad y por una zona de cueva de varias salas.
Ctrl+C para terminar: imprime el resumen y guarda
tools/probes/xy/salida/zonas_vs_lugares_xy.json. Pega el resumen en el chat
y adjunta el JSON.
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

OUTPUT_PATH = (
    Path(__file__).resolve().parent / "salida" / "zonas_vs_lugares_xy.json"
)

# Offset del lugar de encuentro (u16) en el PK6 descifrado. Es lo que
# dice el formato PK6; el probe lo CONTRASTA con el bridge de PKHeX en
# cada captura y avisa si no coinciden (no se da por bueno a ciegas).
MET_LOCATION_OFFSET = 0xDA
PK6_SIZE = 232

POLL_SECONDS = 0.4
# Cajas que se escanean (X/Y traen 31; solo se leen las que tienen
# Pokémon válidos).
DEFAULT_BOXES = 31
# Lecturas seguidas iguales para dar una zona por asentada.
CONFIRM_POLLS = 3
# Cada cuánto se escanea equipo + cajas mientras se espera una captura.
SCAN_SECONDS = 2.0
# Cuánto se espera a que aparezca el Pokémon capturado.
CAPTURE_TIMEOUT = 45.0
# Cuánto después de empezar el combate se mira el rival (el juego
# escribe los datos de forma progresiva): una vez pronto y otra tarde.
RIVAL_SAMPLE_DELAYS = (0.6, 4.0)


def met_location_raw(raw):
    """Met_Location (u16 en 0xDA) de un PK6 descifrado, o None."""
    if raw is None or len(raw) < MET_LOCATION_OFFSET + 2:
        return None

    return struct.unpack_from("<H", raw, MET_LOCATION_OFFSET)[0]


def pid_of(raw):
    if raw is None or len(raw) < 4:
        return None

    return struct.unpack_from("<I", raw, 0)[0]


class Observador:
    """
    Lógica pura del probe (sin Azahar): recibe lecturas, devuelve
    eventos de texto. El bucle de E/S está en main().
    """

    def __init__(self):
        self.stable_zone = None
        self._candidate = None
        self._candidate_polls = 0
        self.zones_seen = []          # IDs de zona asentados, en orden
        self.pairs = []               # pares (zona, lugar) con su fuente
        self.baseline_pids = None     # pid -> especie (equipo + cajas)
        self.last_counter = None
        self.pending = None           # captura esperando al Pokémon nuevo
        self._last_diag = None

    # -- zona ---------------------------------------------------------
    def feed_zone(self, zone_id):
        """Zona asentada nueva -> texto; si no hay cambio, None."""
        if zone_id is None:
            return None

        if zone_id != self._candidate:
            self._candidate = zone_id
            self._candidate_polls = 1
        else:
            self._candidate_polls += 1

        if (
            self._candidate_polls >= CONFIRM_POLLS
            and zone_id != self.stable_zone
        ):
            self.stable_zone = zone_id
            self.zones_seen.append(zone_id)
            return f"zona -> {zone_id} (0x{zone_id:X})"

        return None

    # -- captura ------------------------------------------------------
    def feed_counter(self, value, now):
        if value is None:
            return None

        previous = self.last_counter
        self.last_counter = value

        if previous is not None and value == previous + 1:
            self.pending = {"zone": self.stable_zone, "t0": now}
            return (
                f"captura detectada (contador {previous}->{value}) en "
                f"zona {self.stable_zone}; esperando al Pokémon nuevo..."
            )

        return None

    def feed_scan(self, scan, now):
        """
        `scan`: {pid: {"species": int, "met_raw": int|None,
        "met_bridge": int|None}} con equipo + cajas. Devuelve la lista
        de textos de eventos (puede estar vacía).
        """
        events = []

        if self.baseline_pids is None:
            self.baseline_pids = {pid: d["species"] for pid, d in scan.items()}
            return events

        if self.pending is None:
            return events

        new_pids = [p for p in scan if p not in self.baseline_pids]
        resolved = [
            p for p in new_pids
            if (scan[p]["met_bridge"] or scan[p]["met_raw"])
        ]

        diag = (
            f"escaneo: {len(scan)} Pokémon propios, {len(new_pids)} nuevo(s)"
            + "".join(
                f" [pid {p:08X} esp {scan[p]['species']} "
                f"campo0xDA={scan[p]['met_raw']} "
                f"en {scan[p].get('origen', '?')}]"
                for p in new_pids
            )
        )

        if diag != self._last_diag and not resolved:
            self._last_diag = diag
            events.append(diag)

        for pid in resolved:
            data = scan[pid]
            met = (
                data["met_bridge"]
                if data["met_bridge"] is not None
                else data["met_raw"]
            )
            self.pairs.append({
                "fuente": "captura",
                "zona": self.pending["zone"],
                "lugar": met,
                "lugar_campo_0xDA": data["met_raw"],
                "lugar_bridge": data["met_bridge"],
                "especie": data["species"],
                "pid": f"{pid:08X}",
            })
            events.append(
                f"PAR captura: zona {self.pending['zone']} -> lugar {met} "
                f"(campo 0xDA={data['met_raw']}, bridge={data['met_bridge']}, "
                f"especie {data['species']})"
            )

        if resolved:
            self.baseline_pids = {pid: d["species"] for pid, d in scan.items()}
            self.pending = None
        elif now - self.pending["t0"] > CAPTURE_TIMEOUT:
            events.append(
                "captura SIN par: no apareció un Pokémon nuevo con lugar "
                f"en {CAPTURE_TIMEOUT:.0f} s (¿lo liberaste o sigue el "
                "diálogo de apodo?)."
            )
            self.baseline_pids = {pid: d["species"] for pid, d in scan.items()}
            self.pending = None

        return events

    # -- rival --------------------------------------------------------
    def feed_rival(self, species, met_raw, delay):
        """Par de la fuente B (rival al empezar el combate)."""
        self.pairs.append({
            "fuente": "rival",
            "zona": self.stable_zone,
            "lugar": met_raw,
            "lugar_campo_0xDA": met_raw,
            "lugar_bridge": None,
            "especie": species,
            "pid": None,
            "t_desde_inicio_combate": delay,
        })

        return (
            f"rival a +{delay:.1f}s: zona {self.stable_zone}, especie "
            f"{species}, Met_Location del rival = {met_raw}"
        )


def agrupar_por_lugar(scan):
    """{campo 0xDA: [pid, ...]} de un escaneo (para --dump)."""
    grupos = {}

    for pid, data in scan.items():
        grupos.setdefault(data["met_raw"], []).append(pid)

    return {k: sorted(v) for k, v in sorted(
        grupos.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)
    )}


def analizar(pairs, zones_seen=()):
    """
    Resume qué relación hay entre zona y lugar. Función pura.

    Veredictos:
      - "SIN_DATOS": no hay pares con zona y lugar.
      - "OFFSET_FIJO": zona - lugar es constante en todos los pares
        (la tabla de zonas sale del catálogo sumando ese offset).
      - "MAPEO_CONSISTENTE": cada zona apunta a un único lugar pero no
        hay offset fijo (tabla zona->lugar derivable solo de lo visto).
      - "CONFLICTOS": una misma zona dio lugares distintos.
    """
    validos = [
        p for p in pairs
        if p.get("zona") is not None and p.get("lugar") not in (None, 0)
    ]

    por_zona = {}
    for p in validos:
        por_zona.setdefault(p["zona"], set()).add(p["lugar"])

    por_lugar = {}
    for p in validos:
        por_lugar.setdefault(p["lugar"], set()).add(p["zona"])

    deltas = sorted({p["zona"] - p["lugar"] for p in validos})

    conflictos = {z: sorted(ls) for z, ls in por_zona.items() if len(ls) > 1}

    if not validos:
        veredicto = "SIN_DATOS"
    elif conflictos:
        veredicto = "CONFLICTOS"
    elif len(deltas) == 1:
        veredicto = "OFFSET_FIJO"
    else:
        veredicto = "MAPEO_CONSISTENTE"

    desacuerdos_bridge = [
        p for p in validos
        if p.get("lugar_bridge") is not None
        and p.get("lugar_campo_0xDA") is not None
        and p["lugar_bridge"] != p["lugar_campo_0xDA"]
    ]

    fuentes = {}
    for p in validos:
        fuentes[p["fuente"]] = fuentes.get(p["fuente"], 0) + 1

    rival_con_lugar = sum(
        1 for p in pairs if p["fuente"] == "rival" and p.get("lugar") not in (None, 0)
    )
    rival_total = sum(1 for p in pairs if p["fuente"] == "rival")

    return {
        "pares_validos": len(validos),
        "pares_por_fuente": fuentes,
        "zona_a_lugares": {z: sorted(ls) for z, ls in sorted(por_zona.items())},
        "lugar_a_zonas": {l: sorted(zs) for l, zs in sorted(por_lugar.items())},
        "deltas_zona_menos_lugar": deltas,
        "conflictos": conflictos,
        "campo_0xDA_distinto_del_bridge": len(desacuerdos_bridge),
        "rival_con_lugar": f"{rival_con_lugar}/{rival_total}",
        "zonas_vistas": sorted(set(zones_seen)),
        "zonas_vistas_sin_par": sorted(set(zones_seen) - set(por_zona)),
        "veredicto": veredicto,
    }


def format_summary(resumen):
    from app.services.kalos_locations_es import KALOS_LOCATION_NAMES_ES

    lines = [
        f"Veredicto: {resumen['veredicto']}",
        f"Pares válidos: {resumen['pares_validos']} "
        f"{resumen['pares_por_fuente']}",
        f"Rival con Met_Location al empezar el combate: "
        f"{resumen['rival_con_lugar']}",
        f"Campo 0xDA distinto del bridge: "
        f"{resumen['campo_0xDA_distinto_del_bridge']} (debe ser 0)",
        f"zona - lugar: {resumen['deltas_zona_menos_lugar']}",
        "",
        "zona (dec / hex) -> lugar (id, nombre del catálogo):",
    ]

    for zona, lugares in resumen["zona_a_lugares"].items():
        nombres = ", ".join(
            f"{l} {KALOS_LOCATION_NAMES_ES.get(l, '¿?')}" for l in lugares
        )
        lines.append(f"  {zona:>5} / 0x{zona:03X} -> {nombres}")

    if resumen["conflictos"]:
        lines.append(f"CONFLICTOS (misma zona, lugares distintos): {resumen['conflictos']}")

    lines.append(f"Zonas vistas sin par: {resumen['zonas_vistas_sin_par']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# E/S (no se prueba sin Azahar)
# ---------------------------------------------------------------------

def scan_party_and_boxes(
    reader, bridge, known_pids=None, boxes=DEFAULT_BOXES, include_last=True
):
    """
    pid -> {species, met_raw, met_bridge, raw, origen} del equipo, las
    cajas 1..`boxes` y (si `include_last`) la copia del último capturado.

    La corrida del 05/10/2026 tenía 215 Pokémon propios (equipo + 7
    cajas casi llenas): las capturas nuevas iban a cajas 8+ y el probe no
    las veía. Por eso ahora se escanean más cajas (en bloques de 7; solo
    cuentan los slots con checksum PK6 válido, así que si el bloque no
    fuera contiguo no se inventa nada) y se mira también la copia del
    último capturado.

    `known_pids`: Pokémon ya conocidos; solo para los demás se consulta
    al bridge (antes se le preguntaba por los 215 en cada escaneo y era
    lento). Con None no se consulta a nadie (línea base).
    """
    from app.memory.structures import Pokemon6

    found = {}

    def add(raw, origen):
        pid = pid_of(raw)

        if pid is None or pid == 0:
            return

        if pid in found:
            # Ya visto en equipo/caja: esa ubicación manda sobre la copia.
            return

        species = struct.unpack_from("<H", raw, 0x08)[0]
        met_raw = met_location_raw(raw)
        met_bridge = None

        if (
            bridge is not None
            and known_pids is not None
            and pid not in known_pids
            and (met_raw or 0) != 0
        ):
            try:
                met_bridge = bridge.met_location(raw[:PK6_SIZE]).get(
                    "metLocationId"
                )
            except Exception:  # noqa: BLE001
                met_bridge = None

        found[pid] = {
            "species": species,
            "met_raw": met_raw,
            "met_bridge": met_bridge,
            "raw": raw,
            "origen": origen,
        }

    for slot in range(1, 7):
        pokemon = reader.read_pokemon_raw_for_slot(slot)

        if pokemon is not None and pokemon.raw_data:
            add(pokemon.raw_data, f"equipo {slot}")

    geometry = reader._box_geometry()

    if geometry is not None:
        _b, stride, count = geometry
        group = 7

        for first in range(1, boxes + 1, group):
            n_boxes = min(group, boxes - first + 1)
            base = reader._box_address(first)
            window = n_boxes * count * stride

            try:
                data = reader.memory.read(base, window)
            except OSError:
                continue

            if data is None or len(data) != window:
                continue

            for index in range(n_boxes * count):
                chunk = data[index * stride:index * stride + PK6_SIZE]
                pokemon = Pokemon6(chunk)

                if pokemon.raw_data:
                    box = first + index // count
                    slot = index % count + 1
                    add(pokemon.raw_data, f"caja {box}.{slot}")

    if include_last:
        address = reader._field("last_caught_address")

        if address is not None:
            try:
                data = reader.memory.read(address, PK6_SIZE)
            except OSError:
                data = None

            if data is not None and len(data) == PK6_SIZE:
                pokemon = Pokemon6(data)

                if pokemon.raw_data:
                    add(pokemon.raw_data, "ultimo_capturado")

    return found


def read_rival_raw(reader):
    from app.memory.structures import Pokemon6

    addresses = reader._field("wild_rival_addresses") or ()

    if not addresses:
        return None

    try:
        data = reader.memory.read(addresses[0], PK6_SIZE)
    except OSError:
        return None

    if data is None or len(data) != PK6_SIZE:
        return None

    pokemon = Pokemon6(data)

    return pokemon.raw_data or None


def save(observer, resumen):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            {
                "resumen": resumen,
                "pares": observer.pairs,
                "zonas_vistas_en_orden": observer.zones_seen,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")


def run_dump(reader, bridge, boxes=DEFAULT_BOXES):
    """Distribución de Met_Location de los Pokémon propios (una pasada)."""
    from app.services.kalos_locations_es import KALOS_LOCATION_NAMES_ES

    scan = scan_party_and_boxes(reader, None, boxes=boxes)
    grupos = agrupar_por_lugar(scan)
    desacuerdos = 0

    print(f"{len(scan)} Pokémon propios leídos.\n")
    print("campo 0xDA -> cantidad | bridge (PKHeX) | catálogo")

    for met_raw, pids in grupos.items():
        bridge_id = None
        bridge_name = "-"

        if bridge is not None and met_raw:
            try:
                answer = bridge.met_location(scan[pids[0]]["raw"][:PK6_SIZE])
                bridge_id = answer.get("metLocationId")
                bridge_name = answer.get("metLocationName") or "-"
            except Exception as error:  # noqa: BLE001
                bridge_name = f"error {error!r}"

        if bridge_id is not None and bridge_id != met_raw:
            desacuerdos += 1

        print(
            f"  {met_raw!s:>6} -> {len(pids):>3} | "
            f"{bridge_id!s:>6} {bridge_name} | "
            f"{KALOS_LOCATION_NAMES_ES.get(met_raw, '-')}"
        )

    print(f"\nCampo 0xDA distinto del bridge: {desacuerdos} (debe ser 0)")

    return 0


def main():
    from app.games.registry import get_profile
    from app.readers.azahar_reader import AzaharReader
    from app.services.combat_service import LECTURA_DESCARTADA, CombatService
    from app.services.pkhex.bridge import PKHeXBridge

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--process", default=None)
    parser.add_argument(
        "--cajas",
        type=int,
        default=DEFAULT_BOXES,
        help=f"cuántas cajas escanear (por defecto {DEFAULT_BOXES})",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="una sola pasada: distribución del Met_Location de tus "
        "Pokémon (valida el campo 0xDA contra el bridge) y sale",
    )
    args = parser.parse_args()

    reader = AzaharReader(process_name=args.process)

    if not reader.connect():
        print("No se pudo conectar con Azahar / no se encontró X o Y.")
        return 1

    if get_profile(reader.process_name) is None:
        print(f"El juego {reader.process_name!r} no tiene perfil.")
        return 1

    print(f"Juego: {reader.profile.display_name} ({reader.process_name})")

    try:
        bridge = PKHeXBridge.shared()
    except Exception as error:  # noqa: BLE001
        print(f"Sin bridge de PKHeX ({error!r}): solo se usará el campo 0xDA.")
        bridge = None

    if args.dump:
        return run_dump(reader, bridge, args.cajas)

    combat = CombatService(reader.memory, profile_provider=lambda: reader.profile)
    observer = Observador()
    observer.baseline_pids = {
        pid: d["species"]
        for pid, d in scan_party_and_boxes(
            reader, None, boxes=args.cajas
        ).items()
    }
    print(
        f"Línea base: {len(observer.baseline_pids)} Pokémon propios "
        f"(equipo + {args.cajas} cajas). "
        "Juega normal; Ctrl+C para terminar.\n",
        flush=True,
    )

    combat_started = None
    samples_done = set()
    last_scan = 0.0

    try:
        while True:
            now = time.time()

            text = observer.feed_zone(reader.read_current_zone_id())
            if text:
                print(time.strftime("[%H:%M:%S]"), text, flush=True)

            text = observer.feed_counter(reader.read_total_caught_count(), now)
            if text:
                print(time.strftime("[%H:%M:%S]"), text, flush=True)
                last_scan = 0.0

            wild = combat.read_wild_flag()

            if wild is True and combat_started is None:
                combat_started = now
                samples_done = set()
                print(
                    time.strftime("[%H:%M:%S]"),
                    f"combate SALVAJE en zona {observer.stable_zone}",
                    flush=True,
                )
            elif wild is None:
                combat_started = None

            if combat_started is not None and wild is not LECTURA_DESCARTADA:
                for delay in RIVAL_SAMPLE_DELAYS:
                    if delay in samples_done or now - combat_started < delay:
                        continue

                    samples_done.add(delay)
                    raw = read_rival_raw(reader)

                    if raw is None:
                        print(f"  rival a +{delay:.1f}s: sin PK6 válido")
                        continue

                    species = struct.unpack_from("<H", raw, 0x08)[0]
                    print(
                        " ",
                        observer.feed_rival(
                            species, met_location_raw(raw), delay
                        ),
                        flush=True,
                    )

            if observer.pending is not None and now - last_scan >= SCAN_SECONDS:
                last_scan = now

                scan = scan_party_and_boxes(
                    reader,
                    bridge,
                    known_pids=observer.baseline_pids,
                    boxes=args.cajas,
                )

                for event in observer.feed_scan(scan, time.time()):
                    print(time.strftime("[%H:%M:%S]"), event, flush=True)

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        pass

    resumen = analizar(observer.pairs, observer.zones_seen)
    print("\n" + format_summary(resumen))
    save(observer, resumen)
    print(f"\nGuardado en: {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Paso 5 del Bloque 14 (ruta multijuego, 04/10/2026): encontrar en RAM de
Pokémon X/Y las medallas, la zona actual y el contador de capturas
comparando "fotos" de la memoria tomadas en momentos distintos de la
partida. Solo lectura: nunca escribe en el juego.

Una foto guarda una ventana de RAM (por defecto 0x08C60000 .. 0x08D00000,
640 KB: ahí viven la tarjeta de entrenador, las cajas y el equipo; en
ORAS también estaban medallas, zona, bolsa y contador). Sacar una foto
tarda segundos.

SACAR UNA FOTO (con X o Y abierto, parado, fuera de combate y de menús):

    python tools/probes/xy/snapshots_xy.py capturar --out logs/xy_antes.bin

COMPARAR (cada --snap es archivo=dato; el dato depende del modo):

  medallas  dato = cuántas medallas tienes en ESA foto.
      Regla: un byte con tantos bits encendidos como medallas, y cada
      foto con más medallas contiene los bits de la anterior. Sirve
      comparar partidas distintas (X y Y) o antes/después de ganar una
      medalla. Una foto de control (mismo número, tomada más tarde) elimina
      los bytes que cambian solos.

      python tools/probes/xy/snapshots_xy.py medallas \\
          --snap logs/xy_x.bin=8 --snap logs/xy_y.bin=5

  zona      dato = nombre del lugar donde estabas (texto sin espacios).
      Regla: mismo lugar -> mismo valor; lugares distintos -> valores
      distintos. Hacen falta al menos 3 fotos con un lugar repetido
      (por ejemplo Ruta5, CiudadLumiose, Ruta5, Ruta6).

      python tools/probes/xy/snapshots_xy.py zona \\
          --snap logs/z1.bin=Ruta5 --snap logs/z2.bin=Lumiose \\
          --snap logs/z3.bin=Ruta5 --snap logs/z4.bin=Ruta6

  contador  dato = cuántas capturas HAS HECHO en esa foto (relativo: 0, 1,
      2... o el número real). Regla: un entero de 32 bits que sube
      exactamente lo mismo que el dato. Haz una foto, captura UN Pokémon,
      haz otra, espera un poco y haz una tercera de control con el mismo
      dato que la segunda.

      python tools/probes/xy/snapshots_xy.py contador \\
          --snap logs/c0.bin=0 --snap logs/c1.bin=1 --snap logs/c2.bin=1

  bolsa     (una sola foto) dato = --item ID:CANTIDAD, repetible. Busca el
      bolsillo de Objetos: casilleros de 4 bytes (id u16, cantidad u16)
      que contengan a la vez TODOS los objetos que indiques, cercanos
      entre sí. IDs de Poké Balls (iguales en ORAS): 1 Master, 2 Ultra,
      3 Super, 4 Poké Ball, 5 Safari... Mira en tu bolsa cuántas tienes
      de cada una y saca la foto SIN gastar nada entre medias:

      python tools/probes/xy/snapshots_xy.py bolsa --snap logs/b0.bin \
          --item 4:25 --item 3:12 --item 2:3

  combate   (fotos de una ventana distinta: --start 0x081F0000 --size 0x40000)
      dato = estado[:HP] de cada foto: "fuera" (en el mapa, sin menús),
      "entrenador" o "salvaje" (dentro de un combate, con el menú de
      comandos en pantalla) y, si es de combate, el HP ACTUAL de tu
      Pokémon activo. Busca: (1) posiciones fijas que valen tu HP en todos
      los combates, (2) celdas que apuntan a RAM durante el combate y valen
      0 fuera de él (¿hay combate?), (3) bytes que valen 0 en combates de
      entrenador y !=0 en salvajes (¿es salvaje?).

      python tools/probes/xy/snapshots_xy.py capturar --start 0x081F0000 \
          --size 0x40000 --out logs/k_fuera1.bin
      python tools/probes/xy/snapshots_xy.py combate \
          --snap logs/k_fuera1.bin=fuera --snap logs/k_fuera2.bin=fuera \
          --snap logs/k_ent1.bin=entrenador:187 \
          --snap logs/k_ent2.bin=entrenador:233 \
          --snap logs/k_sal1.bin=salvaje:204 --snap logs/k_sal2.bin=salvaje:210

Los resultados son CANDIDATOS: no se fijan en el perfil hasta confirmarlos
con otra partida o en vivo (reglas 1, 11 y 12 del Documento Maestro).
"""

import argparse
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.memory.memory_reader import MemoryReader  # noqa: E402
from app.readers.citra import Citra  # noqa: E402
from tools.probes.memory.investigar_trainer_id import read_window  # noqa: E402
from investigar_trainer_xy import select_process  # noqa: E402

DEFAULT_START = 0x08C60000
DEFAULT_SIZE = 0x000A0000
TRAINER_CARD_ADDRESS = 0x08C79C3C  # confirmada en X e Y (paso 4)
MAGIC = b"XYSN"
MAX_PRINT = 40


def parse_int(value):
    return int(value, 0)


def save_snapshot(path, start, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MAGIC + struct.pack("<II", start, len(data)) + data)


def load_snapshot(path):
    raw = Path(path).read_bytes()

    if raw[:4] != MAGIC:
        raise ValueError(f"{path}: no es una foto de este probe")

    start, size = struct.unpack_from("<II", raw, 4)
    data = raw[12:12 + size]

    if len(data) != size:
        raise ValueError(f"{path}: archivo truncado")

    return start, data


def check_same_window(snapshots):
    """snapshots: [(start, data, dato)]. Devuelve (start, size)."""
    start, data, _ = snapshots[0]

    for other_start, other_data, _ in snapshots[1:]:
        if other_start != start or len(other_data) != len(data):
            raise ValueError("Las fotos no cubren la misma ventana de RAM.")

    return start, len(data)


def sort_by_distance(addresses):
    return sorted(addresses, key=lambda a: (abs(a - TRAINER_CARD_ADDRESS), a))


def badge_candidates(snapshots):
    """Bytes que se comportan como un campo de bits de medallas.

    snapshots: [(start, data, medallas)]. Devuelve [(dirección, [valores])].
    """
    start, size = check_same_window(snapshots)
    counts = [badges for _, _, badges in snapshots]

    if len(set(counts)) < 2 and counts[0] == 0:
        raise ValueError("Con todas las fotos en 0 medallas no hay señal.")

    ordered = sorted(range(len(snapshots)), key=lambda i: counts[i])
    found = []

    for offset in range(size):
        values = [snapshots[i][1][offset] for i in range(len(snapshots))]

        if any(bin(v).count("1") != n for v, n in zip(values, counts)):
            continue

        ok = True

        for earlier, later in zip(ordered, ordered[1:]):
            a, b = values[earlier], values[later]

            if counts[earlier] == counts[later]:
                ok = ok and a == b
            else:
                ok = ok and (a & ~b) == 0 and a != b

        if ok:
            found.append(start + offset)

    return [
        (address, [snap[1][address - start] for snap in snapshots])
        for address in sort_by_distance(found)
    ]


def zone_candidates(snapshots, width):
    """Valores alineados de `width` bytes que identifican el lugar.

    snapshots: [(start, data, lugar)]. Devuelve [(dirección, [valores])].
    """
    start, size = check_same_window(snapshots)
    places = [place for _, _, place in snapshots]

    if len(set(places)) < 2 or len(set(places)) == len(places):
        raise ValueError(
            "Hacen falta al menos 2 lugares distintos y un lugar repetido."
        )

    first_index = {}

    for index, place in enumerate(places):
        first_index.setdefault(place, index)

    found = []

    for offset in range(0, size - width + 1, width):
        values = [
            int.from_bytes(snap[1][offset:offset + width], "little")
            for snap in snapshots
        ]
        by_place = {}
        ok = True

        for place, value in zip(places, values):
            if by_place.setdefault(place, value) != value:
                ok = False
                break

        if ok and len(set(by_place.values())) == len(by_place):
            found.append(start + offset)

    return [
        (
            address,
            [
                int.from_bytes(
                    snap[1][address - start:address - start + width], "little"
                )
                for snap in snapshots
            ],
        )
        for address in sort_by_distance(found)
    ]


def counter_candidates(snapshots):
    """Enteros de 32 bits (alineados) que suben igual que el dato.

    snapshots: [(start, data, capturas)]. Devuelve [(dirección, [valores])].
    """
    start, size = check_same_window(snapshots)
    counts = [count for _, _, count in snapshots]

    if len(set(counts)) < 2:
        raise ValueError("Hacen falta fotos con capturas distintas.")

    found = []

    for offset in range(0, size - 3, 4):
        values = [
            struct.unpack_from("<I", snap[1], offset)[0]
            for snap in snapshots
        ]
        base_value, base_count = values[0], counts[0]

        if all(v - base_value == c - base_count for v, c in zip(values, counts)):
            found.append(start + offset)

    return [
        (address, [struct.unpack_from("<I", s[1], address - start)[0]
                   for s in snapshots])
        for address in sort_by_distance(found)
    ]


BAG_MAX_ITEM_ID = 0x400
BAG_MAX_QUANTITY = 1000
BAG_CLUSTER_SPAN = 0x1000


def _slot(data, offset):
    return struct.unpack_from("<HH", data, offset)


def _slot_is_valid(item_id, quantity):
    return item_id <= BAG_MAX_ITEM_ID and quantity <= BAG_MAX_QUANTITY


def bag_candidates(start, data, items):
    """Busca casilleros (id u16, cantidad u16) con todos los `items` juntos.

    items: [(id, cantidad)]. Devuelve [{"hits": {id: dirección},
    "inicio": dirección}], donde `inicio` es el primer casillero tras el
    último casillero inválido hacia atrás desde el primer hallazgo (las
    zonas de ceros cuentan como válidas: es solo una pista para mirar).
    """
    if not items:
        raise ValueError("Indica al menos un --item ID:CANTIDAD.")

    positions = {}

    for item_id, quantity in items:
        needle = struct.pack("<HH", item_id, quantity)
        found = []
        offset = data.find(needle)

        while offset >= 0:
            if offset % 4 == 0:
                found.append(offset)

            offset = data.find(needle, offset + 1)

        positions[item_id] = found

    first_id = items[0][0]
    results = []

    for anchor in positions[first_id]:
        hits = {first_id: start + anchor}
        ok = True

        for item_id, _ in items[1:]:
            near = [
                o for o in positions[item_id]
                if abs(o - anchor) <= BAG_CLUSTER_SPAN
            ]

            if not near:
                ok = False
                break

            hits[item_id] = start + min(near, key=lambda o: abs(o - anchor))

        if not ok:
            continue

        lowest = min(hits.values()) - start
        cursor = lowest

        while cursor - 4 >= 0 and _slot_is_valid(*_slot(data, cursor - 4)):
            cursor -= 4

        results.append({"hits": hits, "inicio": start + cursor})

    return results


FCRAM_LOW = 0x08000000
FCRAM_HIGH = 0x0A000000
COMBAT_STATES = ("entrenador", "salvaje")


def parse_combat_label(label):
    """'salvaje:204' -> ('salvaje', 204); 'fuera' -> ('fuera', None)."""
    state, _, hp_text = label.partition(":")

    if state not in ("fuera", *COMBAT_STATES):
        raise ValueError(f"Estado desconocido {state!r}: fuera/entrenador/salvaje")

    if state == "fuera":
        if hp_text:
            raise ValueError("Una foto 'fuera' no lleva HP.")

        return state, None

    if hp_text and not hp_text.isdigit():
        raise ValueError(f"HP inválido en {label!r}")

    return state, int(hp_text) if hp_text else None


def combat_analysis(snapshots):
    """snapshots: [(start, data, (estado, hp))].

    Devuelve {"hp": [dirección], "activo": [(dirección, [valores])],
    "salvaje": [(dirección, constante)]}.
    """
    start, size = check_same_window(snapshots)
    states = [label[0] for _, _, label in snapshots]
    outside = [i for i, st in enumerate(states) if st == "fuera"]
    trainer = [i for i, st in enumerate(states) if st == "entrenador"]
    wild = [i for i, st in enumerate(states) if st == "salvaje"]

    if not outside or not (trainer or wild):
        raise ValueError("Hacen falta fotos 'fuera' y al menos una de combate.")

    battle = trainer + wild

    # (1) posiciones que valen tu HP en TODAS las fotos de combate con HP
    hp_snaps = [i for i in battle if snapshots[i][2][1] is not None]
    hp_positions = None

    for index in hp_snaps:
        needle = snapshots[index][2][1].to_bytes(2, "little")
        data = snapshots[index][1]
        found = set()
        offset = data.find(needle)

        while offset >= 0:
            if offset % 2 == 0:
                found.add(start + offset)

            offset = data.find(needle, offset + 1)

        hp_positions = found if hp_positions is None else hp_positions & found

    # (2) celdas puntero en combate y 0 fuera
    usable = size - size % 4
    cells = {
        i: memoryview(snapshots[i][1][:usable]).cast("I") for i in outside + battle
    }
    active = []

    for index in range(usable // 4):
        if any(cells[i][index] != 0 for i in outside):
            continue

        values = [cells[i][index] for i in battle]

        if all(FCRAM_LOW <= v < FCRAM_HIGH for v in values):
            active.append((start + index * 4, values))

    # (3) byte 0 en entrenador y !=0 en salvaje
    flag = []

    if trainer and wild:
        for offset in range(size):
            if any(snapshots[i][1][offset] for i in trainer):
                continue

            values = {snapshots[i][1][offset] for i in wild}

            if 0 not in values:
                flag.append(
                    (start + offset, values.pop() if len(values) == 1 else None)
                )

    # (4) por cada celda activa: desplazamientos desde su valor (la base)
    # donde está TU HP en todos los combates, y donde está la bandera
    # (0 en entrenador, !=0 en salvaje). Es el diseño de ORAS (puntero fijo
    # + desplazamiento) y no depende de que la base sea la misma siempre.
    based = []
    hp_needed = [i for i in battle if snapshots[i][2][1] is not None]

    def _byte_at(index, address):
        offset = address - start

        if 0 <= offset < size:
            return snapshots[index][1][offset]

        return None

    def _u16_at(index, address):
        offset = address - start

        if 0 <= offset <= size - 2:
            return int.from_bytes(snapshots[index][1][offset:offset + 2], "little")

        return None

    for address, values in active:
        by_snapshot = dict(zip(battle, values))
        hp_offsets = []

        if len(hp_needed) >= 2:
            for off in range(0, 0x800 + 1, 2):
                if all(
                    _u16_at(i, by_snapshot[i] + off) == snapshots[i][2][1]
                    for i in hp_needed
                ):
                    hp_offsets.append(off)

        if not hp_offsets:
            continue

        flag_offsets = []

        if trainer and wild:
            for off in range(0, 0x1000):
                if all(_byte_at(i, by_snapshot[i] + off) == 0 for i in trainer):
                    seen = [_byte_at(i, by_snapshot[i] + off) for i in wild]

                    if all(v for v in seen):
                        flag_offsets.append((off, seen))

        based.append((address, values, hp_offsets, flag_offsets))

    anchor = min(hp_positions) if hp_positions else start

    def near(item):
        address = item if isinstance(item, int) else item[0]
        return (abs(address - anchor), address)

    return {
        "hp": sorted(hp_positions or [], key=near),
        "activo": sorted(active, key=near),
        "salvaje": sorted(flag, key=near),
        "base": based,
    }


def parse_snap_arg(text, numeric):
    path, _, label = text.rpartition("=")

    if not path or not label:
        raise ValueError(f"--snap debe ser archivo=dato (recibí {text!r})")

    return path, int(label) if numeric else label


def connect(process_name):
    citra = Citra()
    selected = select_process(citra, process_name)

    if selected is None:
        print("No se encontró el proceso de X/Y. Corre listar_procesos_xy.py.")
        return None

    pid, name = selected
    citra.set_process(pid)
    print(f"Proceso: {name}  (PID {pid})")
    return citra


def command_capturar(args):
    try:
        citra = connect(args.process)
    except OSError as error:
        print(f"No se pudo hablar con Azahar: {error!r}")
        return 1

    if citra is None:
        return 1

    data, failed = read_window(MemoryReader(citra), args.start, args.size)

    if failed:
        print(f"(bloques que no se pudieron leer: {failed}; la foto no sirve)")
        return 1

    save_snapshot(args.out, args.start, data)
    print(f"Foto guardada: {args.out}  (0x{args.start:08X}, {len(data)} bytes)")
    return 0


def print_candidates(title, rows, snaps, formatter):
    print(f"\n{title}: {len(rows)} candidatos "
          f"(ordenados por cercanía a la tarjeta de entrenador)")

    if not rows:
        print("  Ninguno. Revisa que los datos de cada foto sean correctos.")
        return

    print("  fotos: " + ", ".join(Path(path).name for path, _ in snaps))

    for address, values in rows[:MAX_PRINT]:
        distance = address - TRAINER_CARD_ADDRESS
        print(f"  0x{address:08X} ({distance:+#07x})  "
              + "  ".join(formatter(v) for v in values))

    if len(rows) > MAX_PRINT:
        print(f"  ... y {len(rows) - MAX_PRINT} más")


def command_compare(args):
    numeric = args.command in ("medallas", "contador")

    try:
        parsed = [parse_snap_arg(text, numeric) for text in args.snap]
        loaded = [(*load_snapshot(path), label) for path, label in parsed]

        if len(loaded) < 2:
            raise ValueError("Hacen falta al menos 2 fotos.")

        if args.command == "medallas":
            rows = badge_candidates(loaded)
            formatter = lambda v: f"{v:08b}"  # noqa: E731
        elif args.command == "zona":
            rows = zone_candidates(loaded, args.ancho)
            formatter = lambda v: f"{v:#x}"  # noqa: E731
        else:
            rows = counter_candidates(loaded)
            formatter = str
    except (ValueError, OSError) as error:
        print(f"Error: {error}")
        return 1

    print_candidates(args.command.upper(), rows, parsed, formatter)
    print("\nSon candidatos: no se fija nada en el perfil hasta confirmarlos.")
    return 0


def parse_item_arg(text):
    item_id, _, quantity = text.partition(":")

    if not item_id or not quantity:
        raise ValueError(f"--item debe ser ID:CANTIDAD (recibí {text!r})")

    return int(item_id, 0), int(quantity)


def command_bolsa(args):
    try:
        items = [parse_item_arg(text) for text in args.item]
        start, data = load_snapshot(args.snap)
        rows = bag_candidates(start, data, items)
    except (ValueError, OSError) as error:
        print(f"Error: {error}")
        return 1

    print(f"\nBOLSA: {len(rows)} grupos con todos los objetos juntos")

    for row in rows[:MAX_PRINT]:
        hits = ", ".join(
            f"id {item_id} en 0x{address:08X}"
            for item_id, address in row["hits"].items()
        )
        print(f"  {hits}")
        print(f"    inicio probable (hacia atrás hasta un casillero inválido): "
              f"0x{row['inicio']:08X}")
        first = []

        for index in range(8):
            offset = row["inicio"] - start + index * 4
            first.append("%d x%d" % _slot(data, offset))

        print("    primeros casilleros desde ahí: " + ", ".join(first))

    print("\nSon candidatos: no se fija nada en el perfil hasta confirmarlos.")
    return 0


def command_combate(args):
    try:
        loaded = []
        parsed = []

        for text in args.snap:
            path, _, label = text.rpartition("=")

            if not path or not label:
                raise ValueError(f"--snap debe ser archivo=estado[:HP] ({text!r})")

            loaded.append((*load_snapshot(path), parse_combat_label(label)))
            parsed.append((path, label))

        result = combat_analysis(loaded)
    except (ValueError, OSError) as error:
        print(f"Error: {error}")
        return 1

    print("\nCOMBATE")
    print(f"(1) Posiciones que valen tu HP en todos los combates: "
          f"{len(result['hp'])}")

    for address in result["hp"][:MAX_PRINT]:
        print(f"    0x{address:08X}")

    print(f"(2) Celdas que apuntan a RAM en combate y valen 0 fuera: "
          f"{len(result['activo'])}")

    for address, values in result["activo"][:MAX_PRINT]:
        print(f"    0x{address:08X}  " + ", ".join(f"0x{v:08X}" for v in values))

    print(f"(3) Bytes 0 en entrenador y !=0 en salvaje: "
          f"{len(result['salvaje'])}")

    for address, constant in result["salvaje"][:MAX_PRINT]:
        detail = f"constante {constant}" if constant is not None else "varía"
        print(f"    0x{address:08X}  ({detail})")

    print(f"(4) Celdas con tu HP y la bandera a un desplazamiento fijo de su "
          f"valor: {len(result['base'])}")

    for address, values, hp_offsets, flag_offsets in result["base"][:MAX_PRINT]:
        print(f"    celda 0x{address:08X}  valores: "
              + ", ".join(f"0x{v:08X}" for v in values))
        print("      HP en base + " + ", ".join(f"0x{o:X}" for o in hp_offsets[:8]))
        print(f"      bandera ({len(flag_offsets)}), con los valores vistos en "
              f"los combates salvajes:")

        for off, seen in flag_offsets[:12]:
            print(f"        base + 0x{off:X}: {sorted(set(seen))}")

        if not flag_offsets:
            print("        ninguna")

    print("\nSon candidatos: no se fija nada en el perfil hasta confirmarlos.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capturar")
    capture.add_argument("--out", required=True)
    capture.add_argument("--process", default=None)
    capture.add_argument("--start", type=parse_int, default=DEFAULT_START)
    capture.add_argument("--size", type=parse_int, default=DEFAULT_SIZE)

    combat = sub.add_parser("combate")
    combat.add_argument("--snap", action="append", required=True)

    bag = sub.add_parser("bolsa")
    bag.add_argument("--snap", required=True)
    bag.add_argument("--item", action="append", required=True)

    for name in ("medallas", "zona", "contador"):
        compare = sub.add_parser(name)
        compare.add_argument("--snap", action="append", required=True)

        if name == "zona":
            compare.add_argument("--ancho", type=int, choices=(1, 2), default=2)

    return parser


def main():
    args = build_parser().parse_args()

    if args.command == "capturar":
        return command_capturar(args)

    if args.command == "bolsa":
        return command_bolsa(args)

    if args.command == "combate":
        return command_combate(args)

    return command_compare(args)


if __name__ == "__main__":
    sys.exit(main())

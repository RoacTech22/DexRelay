"""
Busca la direccion de memoria de la bolsa de items, como primer paso
para poder escribir items (Caramelo Raro y otros) desde DexRelay --
ver Documento Maestro de cierre de Fase B, seccion 0.

Mismo enfoque que ya funciono para badges/contador de capturas: en
vez de adivinar un offset, se compara memoria ANTES/DESPUES de un
cambio real y conocido (la cantidad de un item en la bolsa), y se
reporta que direcciones cambiaron.

A diferencia de rastrear_zona_actual.py (que necesita la regla
"mismo lugar = mismo valor" porque no controla el momento del
cambio), aca SI controlamos el cambio nosotros (vos cambias la
cantidad de un item cuando el script lo pide), asi que alcanza con
un antes/despues -- pero se agrega tambien un CONTROL A/B (sin tocar
nada) para descartar ruido de fondo (timers, animaciones, RNG) que
NO tiene que ver con la bolsa, mismo patron ya usado en
azahar_badges_probe.py.

Rango escaneado: alrededor de BADGES_ADDRESS (confirmada compartida
entre Alpha Sapphire y Omega Ruby) hasta la PARTY_ORDER_ADDRESS de
la version que este corriendo, con margen de 0x8000 a cada lado.
Se eligio este rango porque ya sabemos que ahi adentro vive TODO lo
demas de la partida ya confirmado hasta ahora (badges, contador de
capturas, Caja PC, orden de la party) -- es la apuesta mas logica de
donde tambien va a estar la bolsa, antes de probar en otro lado.

COMO USARLO:

    1. Abri Azahar con el juego cargado, PARADO en el mapa (fuera de
       combate/menus) para el primer control.
    2. Corre:

           python -m tools.probes.memory.buscar_bolsa_items

    3. Vas a pasar por 3 capturas:
       - CONTROL A: no toques nada todavia.
       - CONTROL B: esperas unos segundos sin tocar nada (para
         descartar ruido de fondo). Esta captura se reusa despues
         como el "antes" del cambio real.
       - DESPUES: abrite la bolsa y cambia la cantidad de UN item
         conocido en 1 (por ejemplo, usa una Pocion, o tira/junta
         una Baya) -- cuanto mas simple el cambio, mas facil de
         identificar despues. Anota bien QUE item cambiaste y de
         cuanto a cuanto, el script no lo sabe.
    4. Al final imprime los offsets candidatos que cambiaron entre
       "antes" y "despues" pero NO cambiaron entre CONTROL A/B, con
       el valor viejo/nuevo y el contexto de bytes alrededor (para
       ayudar a reconocer la estructura real: en los juegos de esta
       generacion cada casillero de la bolsa suele ser un par de 2
       bytes -- item_id, cantidad -- pero no esta confirmado todavia
       para ORAS, por eso se imprimen ambas interpretaciones).
    5. Guarda los 3 snapshots en tools/probes/memory/ para poder
       reanalizarlos despues sin tener que repetir la captura en
       vivo (mismo criterio que azahar_badges_probe.py).

IMPORTANTE: esto es SOLO LECTURA, no escribe nada en el juego --
no hay riesgo de corromper el save corriendo este script.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import get_party_order_address
from app.services.badges_service import BADGES_ADDRESS


MARGIN_BEFORE = 0x8000
MARGIN_AFTER = 0x8000

SNAPSHOT_CONTROL_A = "tools/probes/memory/bolsa_control_a.bin"
SNAPSHOT_CONTROL_B = "tools/probes/memory/bolsa_control_b.bin"
SNAPSHOT_DESPUES = "tools/probes/memory/bolsa_despues.bin"

# Cuantos bytes de contexto mostrar alrededor de cada candidato,
# para poder reconocer a ojo la estructura real (por ejemplo, un
# item_id de 2 bytes justo antes de la cantidad).
CONTEXT_RADIUS = 8


def capture(memory, start, size):
    data = memory.read(start, size)

    if data is None or len(data) != size:
        raise RuntimeError(
            f"Lectura incompleta desde 0x{start:08X} "
            f"(pedidos {size} bytes)."
        )

    return data


def save_snapshot(filename, data):
    with open(filename, "wb") as file:
        file.write(data)

    print(f"Snapshot guardado: {filename} ({len(data)} bytes)")


def find_changed_offsets(before, after):
    if len(before) != len(after):
        raise ValueError("Los snapshots tienen distinto tamano.")

    return {
        offset
        for offset in range(len(before))
        if before[offset] != after[offset]
    }


def describe_candidate(scan_start, offset, before, after):
    address = scan_start + offset

    context_start = max(0, offset - CONTEXT_RADIUS)
    context_end = min(len(before), offset + CONTEXT_RADIUS + 1)

    context_before = before[context_start:context_end]
    context_after = after[context_start:context_end]

    print(f"0x{address:08X} : {before[offset]:02X} -> {after[offset]:02X}")

    print(
        f"    contexto antes:  "
        f"{context_before.hex(' ')}"
    )
    print(
        f"    contexto despues: "
        f"{context_after.hex(' ')}"
    )

    # Interpretacion tentativa como par (item_id, cantidad) de 2
    # bytes cada uno, probando que el offset cambiado sea la
    # cantidad (empieza en el offset) o el item_id (offset - 2),
    # little-endian -- formato tipico de esta generacion, pero SIN
    # confirmar todavia para ORAS.
    for label, pair_start in (
        ("este offset = cantidad, offset-2 = item_id", offset - 2),
        ("este offset = item_id, offset+2 = cantidad", offset),
    ):
        if 0 <= pair_start and pair_start + 4 <= len(before):
            id_before, qty_before = struct.unpack(
                "<HH", before[pair_start:pair_start + 4]
            )
            id_after, qty_after = struct.unpack(
                "<HH", after[pair_start:pair_start + 4]
            )
            print(
                f"    si {label}: "
                f"item_id={id_before}->{id_after} "
                f"cantidad={qty_before}->{qty_after}"
            )

    print()


def main():
    print("================================")
    print("   DEXRELAY BOLSA DE ITEMS PROBE")
    print("================================")
    print()

    # process_name=None fuerza el modo automatico de
    # find_game_process() (busca cualquiera de KNOWN_PROCESS_NAMES).
    # AzaharReader() sin argumentos NO es automatico -- su default
    # es process_name="sango-2" fijo (para no romper probes viejos
    # que la instancian sin pasar nada), asi que solo encontraba
    # Alpha Sapphire y fallaba en silencio con Omega Ruby corriendo.
    # Mismo bug ya visto antes en otro probe, mismo arreglo.
    reader = AzaharReader(process_name=None)

    print("Buscando proceso (sango-1 / sango-2)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    process_name = reader.process_name

    print(f"Azahar conectado correctamente. Proceso: {process_name}")
    print()

    memory = reader.memory

    party_order_address = get_party_order_address(process_name)

    scan_start = BADGES_ADDRESS - MARGIN_BEFORE
    scan_end = party_order_address + MARGIN_AFTER
    scan_size = scan_end - scan_start

    print(
        f"Ancla badges: 0x{BADGES_ADDRESS:08X} "
        f"(confirmada compartida entre versiones)"
    )
    print(
        f"Ancla party (segun version detectada): "
        f"0x{party_order_address:08X}"
    )
    print(
        f"Rango de escaneo: 0x{scan_start:08X} - 0x{scan_end:08X} "
        f"({scan_size} bytes)"
    )
    print()

    input(
        "Parate en el mapa, fuera de combate/menus, y NO toques "
        "nada. Presiona Enter para CONTROL A..."
    )

    print("Capturando CONTROL A...")
    snapshot_a = capture(memory, scan_start, scan_size)
    save_snapshot(SNAPSHOT_CONTROL_A, snapshot_a)

    print()
    input(
        "Segui sin tocar nada unos segundos (ni bolsa, ni "
        "caminar). Presiona Enter para CONTROL B..."
    )

    print("Capturando CONTROL B...")
    snapshot_b = capture(memory, scan_start, scan_size)
    save_snapshot(SNAPSHOT_CONTROL_B, snapshot_b)

    control_changes = find_changed_offsets(snapshot_a, snapshot_b)

    print()
    print(
        f"Ruido de fondo detectado (CONTROL A -> B): "
        f"{len(control_changes)} bytes distintos "
        f"(se van a ignorar en el resultado final)."
    )
    print()

    print(
        "AHORA: abri la bolsa y cambia la cantidad de UN item "
        "conocido en 1 (usar una Pocion, tirar/juntar una Baya, "
        "etc). Anota bien que item y de cuanto a cuanto cambiaste."
    )
    input("Cuando ya hayas hecho el cambio, presiona Enter...")

    print("Capturando DESPUES...")
    snapshot_despues = capture(memory, scan_start, scan_size)
    save_snapshot(SNAPSHOT_DESPUES, snapshot_despues)

    real_changes = find_changed_offsets(snapshot_b, snapshot_despues)
    candidates = sorted(real_changes - control_changes)

    print()
    print("================================")
    print("   RESULTADO")
    print("================================")
    print()

    if not candidates:
        print(
            "Ningun offset cambio (fuera del ruido de fondo). "
            "Puede ser que el rango escaneado no incluya la bolsa "
            "-- probar ampliando MARGIN_BEFORE/MARGIN_AFTER, o que "
            "el cambio no se haya guardado a tiempo antes de la "
            "captura DESPUES."
        )
        return

    print(f"Offsets candidatos: {len(candidates)}")
    print()

    for offset in candidates:
        describe_candidate(
            scan_start, offset, snapshot_b, snapshot_despues
        )

    print(
        "Si aparecen MUCHOS candidatos dispersos, probablemente el "
        "cambio de item no fue lo unico que paso entre las dos "
        "capturas (por ejemplo, el personaje se movio o abrio/cerro "
        "un menu) -- repetir con mas cuidado. Si aparecen 2-4 "
        "candidatos juntos y cercanos entre si, esa agrupacion es "
        "la mejor pista de donde vive el casillero del item en la "
        "bolsa."
    )


if __name__ == "__main__":
    main()

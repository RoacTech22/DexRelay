"""
Busca la direccion real del bolsillo de MEDICINA dentro de la
bolsa, despues de descubrir un problema con escribir_item_bolsa.py:
al agregar Caramelo Raro en CUALQUIER casillero vacio del tramo
grande confirmado (BAG_START_ADDRESS-BAG_END_ADDRESS), el juego lo
mostraba en el bolsillo "Objetos" en vez de "Medicina" -- y por
estar en el bolsillo equivocado, usarlo no descontaba la cantidad
(el menu de Objetos no tiene la logica de "usar sobre un Pokemon"
que si tiene Medicina).

Esto revisa la hipotesis anterior (buscar_bolsa_items.py /
confirmar_bolsa_items.py, sesion previa): NO es una sola lista
unificada de items sin separacion real -- son VARIOS arrays de
capacidad fija, uno por bolsillo, pegados uno atras del otro SIN
relleno (mismo patron de contiguidad ya visto en otras estructuras
del proyecto: Cajas PC, orden de la party, etc). Por eso al escanear
se ve como un solo bloque grande sin cortes, pero la POSICION real
dentro de ese bloque importa: cada bolsillo tiene su propia zona.

El bolsillo de Poke Balls ya esta confirmado (Ultra Ball/Poke Ball,
sesion anterior) pero el de Medicina (donde va el Caramelo Raro:
Bulbapedia lo agrupa en el bolsillo de Objetos en juegos MAS
recientes, pero en Generacion VI el Caramelo Raro va en el bolsillo
"Objetos" tambien segun el juego real -- de ahi la duda; hay que
confirmarlo en vivo, no asumirlo) todavia no.

MISMO METODO que ya funciono para Poke Ball/Ultra Ball: comparar
memoria ANTES/DESPUES de un cambio real y conocido -- pero esta vez
el rango a escanear es mucho mas chico (solo BAG_START_ADDRESS a
BAG_END_ADDRESS, ~2960 bytes, ya confirmado que ahi vive TODA la
bolsa) asi que la corrida es rapida.

COMO USARLO:

    1. Necesitas un item de MEDICINA en la bolsa para poder
       cambiarle la cantidad (Pocion, Antidoto, cualquiera). Si no
       tenes ninguno, compra uno barato en un Poke Mart antes de
       empezar (el cambio de 0 a 1 al comprarlo tambien sirve como
       "cambio conocido").
    2. Corre:

           python -m tools.probes.memory.buscar_pocket_medicina

    3. CONTROL A, CONTROL B (sin tocar nada, para descartar ruido),
       y despues usa/compra el item de medicina para que su cantidad
       cambie en 1. Anota bien QUE item y de cuanto a cuanto.
    4. Al final imprime los candidatos (mismo formato que
       buscar_bolsa_items.py) -- el que muestre item_id estable y
       cantidad cambiada en exactamente lo esperado es el confirmado.

IMPORTANTE: esto es SOLO LECTURA, no escribe nada en el juego.
"""

import struct

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    get_bag_start_address,
    get_bag_end_address,
)


SNAPSHOT_CONTROL_A = "tools/probes/memory/medicina_control_a.bin"
SNAPSHOT_CONTROL_B = "tools/probes/memory/medicina_control_b.bin"
SNAPSHOT_DESPUES = "tools/probes/memory/medicina_despues.bin"

# Mismo criterio que buscar_bolsa_items.py.
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

    print(f"    contexto antes:  {context_before.hex(' ')}")
    print(f"    contexto despues: {context_after.hex(' ')}")

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
    print("   BUSCAR BOLSILLO DE MEDICINA")
    print("================================")
    print()

    reader = AzaharReader(process_name=None)

    print("Buscando proceso (sango-1 / sango-2)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    print(f"Azahar conectado correctamente. Proceso: {reader.process_name}")
    print()

    memory = reader.memory

    scan_start = get_bag_start_address(reader.process_name)
    scan_end = get_bag_end_address(reader.process_name)
    scan_size = scan_end - scan_start

    print(
        f"Rango de escaneo (bolsa ya confirmada): "
        f"0x{scan_start:08X} - 0x{scan_end:08X} ({scan_size} bytes)"
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
        "Segui sin tocar nada unos segundos. Presiona Enter para "
        "CONTROL B..."
    )

    print("Capturando CONTROL B...")
    snapshot_b = capture(memory, scan_start, scan_size)
    save_snapshot(SNAPSHOT_CONTROL_B, snapshot_b)

    control_changes = find_changed_offsets(snapshot_a, snapshot_b)

    print()
    print(
        f"Ruido de fondo detectado (CONTROL A -> B): "
        f"{len(control_changes)} bytes distintos (se van a ignorar)."
    )
    print()

    print(
        "AHORA: usa o compra UN item de MEDICINA (Pocion, Antidoto, "
        "lo que tengas) para que su cantidad cambie en 1. Anota bien "
        "que item y de cuanto a cuanto cambiaste."
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
            "Ningun offset cambio (fuera del ruido de fondo). Puede "
            "ser que el bolsillo de Medicina NO este dentro del "
            "rango ya confirmado (BAG_START/END_ADDRESS) -- en ese "
            "caso hace falta repetir la busqueda amplia, como se "
            "hizo la primera vez con buscar_bolsa_items.py."
        )
        return

    print(f"Offsets candidatos: {len(candidates)}")
    print()

    for offset in candidates:
        describe_candidate(
            scan_start, offset, snapshot_b, snapshot_despues
        )


if __name__ == "__main__":
    main()

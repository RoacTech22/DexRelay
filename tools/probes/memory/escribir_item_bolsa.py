"""
Escribe un item de Medicina (por defecto, Caramelo Raro) en la
bolsa, usando BagService (app/services/bag_service.py) -- la misma
logica que ya usa la pagina Herramientas de la GUI.

CORRECCION IMPORTANTE (07/09/2026, mismo dia que la version
original de este script): la primera version escribia en CUALQUIER
casillero vacio del tramo grande de la bolsa (BAG_START/END), sin
importar el bolsillo -- eso hacia que el Caramelo Raro apareciera en
el bolsillo "Objetos" en vez de "Medicina", y por estar en el
bolsillo equivocado usarlo NO descontaba la cantidad. Ahora este
script (via BagService) escribe DENTRO de la ventana del bolsillo de
Medicina, confirmada en vivo (Alpha Sapphire: Revivir en 0x08C6B5F0,
bajo de 6 a 5 al tirar uno). Ver app/memory/pointers.py, seccion
"BOLSILLO DE MEDICINA", para el detalle completo.

Solo pensado para items de Medicina (ver Category:Medicine_Pocket de
Bulbapedia) -- Caramelo Raro esta confirmado ahi oficialmente, no es
un supuesto de DexRelay. Si en el futuro se quiere agregar un item
de OTRO bolsillo (una Pocion, una Pokeball, etc), hace falta repetir
la investigacion de ese bolsillo primero (mismo proceso que ya se
siguio con Medicina) -- este script NO sirve para eso tal cual esta.

COMO USARLO:

    python -m tools.probes.memory.escribir_item_bolsa
    python -m tools.probes.memory.escribir_item_bolsa --item-id 50 --cantidad 10
    python -m tools.probes.memory.escribir_item_bolsa --item-id 50 --cantidad 10 --confirmar

Sin --confirmar, el script hace TODO excepto la escritura real
(conecta, busca el casillero, muestra que va a escribir) y se
detiene ahi -- para poder revisar tranquilo antes de animarse a
escribir de verdad.

ANTES DE USAR --confirmar POR PRIMERA VEZ:

    1. Guarda la partida y haz una copia de respaldo del archivo de
       save real de Azahar por fuera del emulador (por las dudas).
    2. Corre primero SIN --confirmar y revisa que el casillero
       elegido y el item/cantidad sean los esperados.
    3. Reconfirma en el juego (abriendo la bolsa, en la seccion
       Medicina) que el item aparecio con la cantidad correcta
       despues de escribir, y que USARLO descuenta la cantidad.
"""

import argparse

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    RARE_CANDY_ITEM_ID,
    MEDICINE_POCKET_SCAN_SLOTS,
    get_medicine_pocket_start_address,
)
from app.services.bag_service import BagService, BagWriteError


DEFAULT_ITEM_ID = RARE_CANDY_ITEM_ID
DEFAULT_QUANTITY = 1


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Escribe un item de Medicina en la bolsa (o suma "
            "cantidad si ya esta), usando BagService."
        )
    )

    parser.add_argument(
        "--item-id",
        type=int,
        default=DEFAULT_ITEM_ID,
        help=(
            f"Indice del item a agregar (default {DEFAULT_ITEM_ID} "
            f"= Caramelo Raro). Tiene que pertenecer al bolsillo de "
            f"Medicina."
        ),
    )

    parser.add_argument(
        "--cantidad",
        type=int,
        default=DEFAULT_QUANTITY,
        help=f"Cantidad a escribir (default {DEFAULT_QUANTITY}).",
    )

    parser.add_argument(
        "--confirmar",
        action="store_true",
        help=(
            "Sin esto, el script hace todo menos la escritura real "
            "(dry-run). Con esto, escribe de verdad en la memoria "
            "del juego."
        ),
    )

    args = parser.parse_args()

    print("================================")
    print("   ESCRIBIR ITEM DE MEDICINA")
    print("================================")
    print()

    reader = AzaharReader(process_name=None)

    print("Buscando proceso (sango-1 / sango-2)...")

    if not reader.connect():
        print("No se encontro ningun proceso conocido.")
        return

    print(f"Azahar conectado correctamente. Proceso: {reader.process_name}")
    print()

    pocket_start = get_medicine_pocket_start_address(reader.process_name)

    print(
        f"Bolsillo de Medicina: 0x{pocket_start:08X} "
        f"(ventana de busqueda: {MEDICINE_POCKET_SCAN_SLOTS} casilleros)"
    )
    print()

    service = BagService(reader)

    # Simulacion: leemos y decidimos el casillero SIN escribir,
    # reusando los metodos internos de BagService para mostrar
    # exactamente lo mismo que se escribiria despues.
    try:
        data = service._read_window(pocket_start, MEDICINE_POCKET_SCAN_SLOTS)
    except BagWriteError as error:
        print(str(error))
        return

    existing_offset = service._find_existing_slot(data, args.item_id)

    if existing_offset is not None:
        existing_id, existing_quantity = service._decode_slot(
            data, existing_offset
        )
        target_address = pocket_start + existing_offset
        print(f"El item {args.item_id} YA esta en el bolsillo:")
        print(f"  Direccion: 0x{target_address:08X}")
        print(f"  Cantidad actual: {existing_quantity}")
    else:
        empty_offset = service._find_empty_slot(data)

        if empty_offset is None:
            print(
                "No se encontro ningun casillero vacio dentro de la "
                "ventana del bolsillo de Medicina."
            )
            return

        target_address = pocket_start + empty_offset
        print(f"Casillero vacio encontrado en 0x{target_address:08X}.")

    print(f"  item_id a escribir: {args.item_id}")
    print(f"  cantidad a agregar: {args.cantidad}")
    print()

    if not args.confirmar:
        print(
            "Modo simulacion (sin --confirmar): no se escribio nada "
            "todavia. Si esto es lo esperado, volve a correr el "
            "script agregando --confirmar."
        )
        return

    print(
        "ATENCION: esto va a escribir en la memoria del juego de "
        "verdad. Asegurate de haber guardado la partida y tener un "
        "respaldo del save antes de continuar."
    )

    respuesta = input(
        "Escribi CONFIRMAR (en mayusculas) para continuar: "
    )

    if respuesta != "CONFIRMAR":
        print("Cancelado por el usuario.")
        return

    try:
        result = service.add_medicine_item(args.item_id, args.cantidad)
    except BagWriteError as error:
        print(f"Fallo: {error}")
        return

    print(
        f"Listo. 0x{result['address']:08X}: item_id={result['item_id']} "
        f"cantidad={result['new_quantity']}"
    )
    print(
        "Abri la bolsa en el juego (seccion Medicina) para confirmar "
        "que el item aparece con la cantidad correcta, y que usarlo "
        "descuenta la cantidad."
    )


if __name__ == "__main__":
    main()

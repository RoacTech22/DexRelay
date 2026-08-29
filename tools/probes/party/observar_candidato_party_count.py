"""
Observa en vivo el candidato a "cantidad de Pokémon en la party"
encontrado con Cheat Engine el 29/08/2026 (investigación del bug
del slot que no se limpia al depositar en la Caja PC).

SEGUNDO INTENTO (emulador reiniciado, puente recalculado desde
cero): el candidato traduce a 0x08CF7208 -- dentro del rango
normal de direcciones ya confirmadas de este proyecto
(0x0800xxxx - 0x08Fxxxxx), a diferencia del primer intento que
había dado 0x1281CF38 (descartado, fuera de rango). Además,
0x08CF7208 = PARTY_ORDER_ADDRESS (0x08CF71F0) + 0x18 -- el BYTE
SIGUIENTE al final de la tabla de 6 punteros (6 × 4 bytes = 0x18).
Es un lugar muy razonable para que el juego guarde "cuántos de
esos 6 son reales", pegado a la tabla que describe -- pero sigue
sin confirmar hasta probarlo en vivo (regla #12).

Traducción de esta sesión:

    ancla Cheat Engine:     0x2020A493230
    ancla del juego:        PARTY_ORDER_ADDRESS (0x08CF71F0)
    offset:                 0x2020179C040
    candidato Cheat Engine: 0x2020A493248
    candidato traducido:    0x08CF7208

Este script imprime el valor en esa dirección interpretado de 3
formas (1 byte, 2 bytes, 4 bytes) cada medio segundo. Lo que hay
que ver:

    - Con la party completa (6), el valor debería ser 6 (en alguna
      de las 3 interpretaciones -- no sabemos todavía cómo está
      codificado).
    - Al depositar un Pokémon en la Caja PC, el valor debería
      bajar a 5 en el mismo instante.
    - Al sacar otro, a 4. Y así.
    - Si el valor NO se mueve para nada mientras hacés esto, o se
      mueve con otra cosa (caminar, entrar a un menú, etc.), esta
      dirección no es la que buscamos -- hay que descartarla y
      seguir la búsqueda en Cheat Engine con otro filtro.

USO:
    python -m tools.probes.party.observar_candidato_party_count

    Con el script corriendo: fijate el valor con la party llena,
    después andá depositando Pokémon uno por uno en la PC y mirá
    si el valor baja de a uno, en el momento exacto del depósito.
"""

import struct
import time

from app.readers.azahar_reader import AzaharReader


# Traducida con el puente calculado en esta sesión (segundo
# intento, emulador reiniciado) -- NO reutilizar en otra sesión
# sin recalcular (el offset cambia cada vez que se reinicia el
# emulador, ver docstring arriba).
CANDIDATE_ADDRESS = 0x08CF7208


def main():
    print("================================")
    print("   OBSERVAR CANDIDATO A")
    print("   'CANTIDAD DE PARTY'")
    print("================================")
    print()
    print(f"Dirección candidata: {hex(CANDIDATE_ADDRESS)}")
    print()

    reader = AzaharReader()

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontro sango-2.")
        return

    print("Azahar conectado correctamente.")
    print("Presiona Ctrl+C para detener.")
    print()

    memory = reader.memory
    last_line = None

    try:
        while True:

            data = memory.read(
                CANDIDATE_ADDRESS,
                4,
            )

            if len(data) != 4:
                print("Lectura fallida (tamano incorrecto).")
                time.sleep(0.5)
                continue

            as_byte = data[0]

            as_2bytes = struct.unpack(
                "<H",
                data[:2],
            )[0]

            as_4bytes = struct.unpack(
                "<I",
                data,
            )[0]

            line = (
                f"1 byte={as_byte}   "
                f"2 bytes={as_2bytes}   "
                f"4 bytes={as_4bytes}   "
                f"(crudo: {data.hex()})"
            )

            marker = (
                " <-- CAMBIO"
                if line != last_line
                else ""
            )

            print(f"{line}{marker}")

            last_line = line

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Detenido.")


if __name__ == "__main__":
    main()

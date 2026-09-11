"""
Variante de imprimir_ancla_puente.py para cuando la dirección
natural (PARTY_ORDER_ADDRESS, el puntero de party) lee todo ceros
-- exactamente lo que pasó investigando Alpha Sapphire 1.4
(09/09/2026): esa dirección ya no tiene un puntero de party válido
ahí en la versión parcheada (justo el síntoma que estamos
investigando), así que el valor natural (0x00000000) es inútil
como ancla -- coincidiría con millones de lugares en Cheat Engine.

En vez de leer lo que ya hay, ESCRIBE un valor único e
inconfundible (0xDEADBEEF, imposible que aparezca "de casualidad"
en datos reales del juego) en esa misma dirección, y lo vuelve a
leer para confirmar que la escritura funcionó -- mismo mecanismo de
escritura ya probado en producción (escritura de items de la
bolsa, Documento Maestro 07/09/2026), así que no es una técnica
nueva sin probar, solo un uso puntual distinto.

RIESGO: bajo. La dirección ya se confirmó leyendo cero de forma
consistente (memoria no usada/reservada en esta versión parcheada,
no algo que el juego esté leyendo o escribiendo activamente ahora
mismo) -- pero como con cualquier escritura de memoria en vivo, no
hay garantía absoluta al 100%. Si te preocupa, guardá la partida
ANTES de correr esto (no hace falta reiniciar el juego después, la
escritura es solo en la RAM del emulador, no toca el archivo de
guardado).

CÓMO USARLO:

    python -m tools.probes.memory.escribir_ancla_temporal

Después, en Cheat Engine: New Scan, Value Type "4 Bytes", tildá
"Hex", pegá "DEADBEEF", Scan Type "Exact Value", First Scan --
debería salir 1 sola coincidencia (o muy pocas). Filtrá con
"Browse this memory region" si salen varias, buscando la que esté
en la región grande (RW, decenas/cientos de MB).
"""

from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import PARTY_ORDER_ADDRESS, PROCESS_NAME_ALPHA_SAPPHIRE

MARKER_BYTES = bytes.fromhex("EFBEADDE")  # 0xDEADBEEF en little-endian
MARKER_HEX_DISPLAY = "DEADBEEF"


def main():
    print("================================")
    print("   ANCLA TEMPORAL PARA EL PUENTE DE CHEAT ENGINE")
    print("   (marca escrita a mano, para cuando el ancla natural da 0)")
    print("================================")
    print()

    reader = AzaharReader(process_name=PROCESS_NAME_ALPHA_SAPPHIRE)

    print("Buscando proceso sango-2...")

    if not reader.connect():
        print("No se encontró sango-2.")
        return

    print("Azahar conectado correctamente.")
    print()

    before = reader.memory.read(PARTY_ORDER_ADDRESS, 4)
    print(f"Valor actual en {hex(PARTY_ORDER_ADDRESS)}: {before.hex() if before else before}")

    ok = reader.memory.citra.write_memory(PARTY_ORDER_ADDRESS, MARKER_BYTES)

    if not ok:
        print("La escritura falló -- no se tocó nada, no hay riesgo.")
        return

    after = reader.memory.read(PARTY_ORDER_ADDRESS, 4)

    if after != MARKER_BYTES:
        print(
            f"Advertencia: se escribió pero la relectura da "
            f"{after.hex() if after else after}, no coincide con lo "
            f"esperado -- algo raro pasó, no confíes en este ancla."
        )
        return

    print(f"Escritura confirmada en {hex(PARTY_ORDER_ADDRESS)}.")
    print()
    print(f"VALOR A BUSCAR EN CHEAT ENGINE (Hex): {MARKER_HEX_DISPLAY}")
    print()
    print(
        "En Cheat Engine: Value Type = '4 Bytes', marcá la casilla "
        "'Hex', pegá 'DEADBEEF', Scan Type = 'Exact Value', New Scan. "
        "Debería salir 1 sola coincidencia (o muy pocas) -- esa es la "
        "dirección host del ancla."
    )


if __name__ == "__main__":
    main()

"""
Busca dónde vive la party real en Omega Ruby, escaneando por
checksum PK6 válido -- mismo método ya usado para encontrar la
Caja PC (`buscar_caja_pc.py`), aplicado acá porque
`PARTY_ORDER_ADDRESS` (confirmada para Alpha Sapphire) dio
0x0 en los 6 slots probando en Omega Ruby (29/08/2026,
confirmado con `observar_orden_party.py`) -- la dirección
simplemente no es la misma entre las dos versiones.

Por qué este enfoque: el checksum de 16 bits que decrypt_data()
ya valida (structures.py) es una señal muy confiable para
reconocer un Pokémon real en memoria -- la probabilidad de que un
choque de bytes al azar lo pase por casualidad es de 1 en 65536.
No hace falta saber de antemano dónde está la tabla de punteros:
alcanza con encontrar la estructura de datos real de tu equipo
actual, en cualquier parte de la ventana escaneada.

COMO USARLO:

    1. Con Omega Ruby corriendo y tu equipo REAL cargado (no
       importa cuántos Pokémon tengas, ni cuáles), anotá el
       nickname/especie de al menos uno o dos para poder
       reconocerlos fácil en la salida.
    2. Corré:

           python -m tools.probes.party.buscar_party_omega_ruby

       (Tarda uno o dos minutos -- escanea una ventana grande de
       32MB.)
    3. Buscá en la lista de candidatos los que correspondan a tu
       equipo real (por nickname o especie). Anotá esas
       direcciones.
    4. Pasame esas direcciones -- con eso reconstruimos dónde
       vive la tabla de punteros real de Omega Ruby (o, si hace
       falta leer directo desde ahí sin tabla de punteros,
       ajustamos el lector para ese caso).
"""

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import PARTY_ORDER_ADDRESS, SLOT_DATA_SIZE
from app.memory.structures import Pokemon6, decrypt_data


# Misma ventana que buscar_caja_pc.py -- 32MB centrados en la
# dirección vieja de Alpha Sapphire, como punto de partida
# razonable (los bloques de datos de guardado suelen quedar cerca
# entre versiones hermanas, aunque las direcciones exactas
# cambien).
WINDOW_BEFORE = 0x1000000
WINDOW_AFTER = 0x1000000

ALIGNMENT = 4


def main():
    print("================================")
    print("   BUSCAR PARTY EN OMEGA RUBY")
    print("   (por checksum PK6)")
    print("================================")
    print()

    process_name = Config().get(
        "azahar", "process_name", default="sango-2"
    )

    reader = AzaharReader(process_name=process_name)

    print(f"Buscando proceso {process_name!r}...")

    if not reader.connect():
        print(f"No se encontro {process_name!r}.")
        return

    print("Azahar conectado correctamente.")
    print()

    memory = reader.memory

    scan_start = PARTY_ORDER_ADDRESS - WINDOW_BEFORE
    scan_size = WINDOW_BEFORE + WINDOW_AFTER

    print(
        f"Ventana de escaneo: {hex(scan_start)} - "
        f"{hex(scan_start + scan_size)} "
        f"({scan_size / 1024 / 1024:.1f} MB)"
    )
    print("Leyendo memoria (puede tardar un rato)...")

    data = memory.read(scan_start, scan_size)

    if len(data) != scan_size:
        print(
            "Lectura incompleta/fallida "
            f"({len(data)} de {scan_size} bytes)."
        )
        return

    print("Memoria leida. Escaneando por checksums validos...")
    print(
        "(esto es calculo local, no mas llamadas de red -- "
        "puede tardar uno o dos minutos)"
    )
    print()

    matches = []

    last_report = 0

    for offset in range(
        0,
        scan_size - SLOT_DATA_SIZE + 1,
        ALIGNMENT,
    ):

        progress = offset / scan_size
        if progress - last_report >= 0.1:
            print(f"  ... {progress * 100:.0f}%")
            last_report = progress

        chunk = data[offset:offset + SLOT_DATA_SIZE]

        if chunk[:8] == b"\x00" * 8:
            continue

        decrypted = decrypt_data(chunk)

        if not decrypted:
            continue

        pokemon = Pokemon6.__new__(Pokemon6)
        pokemon.raw_data = decrypted

        species_id = pokemon.species_id()

        if species_id < 1 or species_id > 721:
            continue

        nickname = pokemon.nickname()
        level = pokemon.level()

        absolute_address = scan_start + offset

        matches.append(
            (absolute_address, species_id, nickname, level)
        )

    print()
    print(f"Encontrados {len(matches)} candidatos con checksum valido.")
    print()

    if not matches:
        print(
            "Nada en esta ventana. La party de Omega Ruby puede "
            "estar más lejos de PARTY_ORDER_ADDRESS de lo "
            "esperado -- habría que ampliar la ventana o probar "
            "con Cheat Engine directamente (Opción A)."
        )
        return

    print(
        "Candidatos encontrados (dirección, especie, nivel, "
        "nickname) -- buscá los que correspondan a TU equipo "
        "real:"
    )
    print()

    for address, species_id, nickname, level in matches[:60]:

        print(
            f"  {hex(address)}  speciesId={species_id}  "
            f"nivel={level}  nickname={nickname!r}"
        )

    if len(matches) > 60:
        print(f"  ... y {len(matches) - 60} más")

    print()

    if len(matches) >= 2:

        gaps = {}

        for i in range(1, len(matches)):
            gap = matches[i][0] - matches[i - 1][0]
            gaps[gap] = gaps.get(gap, 0) + 1

        most_common_gap = max(
            gaps.items(),
            key=lambda item: item[1],
        )

        print(
            f"Separación más común entre candidatos: "
            f"{hex(most_common_gap[0])} bytes "
            f"({most_common_gap[1]} veces) -- si varios "
            f"candidatos consecutivos son de tu equipo real con "
            f"esta separación constante, es el stride real de la "
            f"party en Omega Ruby."
        )


if __name__ == "__main__":
    main()

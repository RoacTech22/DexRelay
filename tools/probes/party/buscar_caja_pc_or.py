"""
Busca la Caja PC en memoria para Omega Ruby, escaneando por checksum
valido -- mismo enfoque exacto que tools/probes/party/buscar_caja_pc.py
(que encontro BOX_BASE_ADDRESS para Alpha Sapphire), pero centrado en
la PARTY_ORDER_ADDRESS de Omega Ruby (0x08CFB1E0, ya confirmada en
vivo el 29/08/2026) en vez de la de Alpha Sapphire.

Por que un script separado y no tocar el original: buscar_caja_pc.py
sigue siendo la referencia que efectivamente encontro la Caja PC de
Alpha Sapphire -- no hay motivo para arriesgar esa lectura tocandolo.
Este es su equivalente para Omega Ruby, mismo algoritmo, otro ancla y
otro process_name.

Motivo de esta busqueda (29/08/2026): el usuario confirmo que el
Nuzlocke Tracker no detecta capturas que van directo a la Caja PC en
Omega Ruby (si funciona en Alpha Sapphire) -- sospecha principal:
BOX_BASE_ADDRESS/BOX_SLOT_STRIDE de pointers.py son especificas de
Alpha Sapphire y no fueron nunca confirmadas en Omega Ruby (mismo
patron ya confirmado con PARTY_ORDER_ADDRESS: NO todas las
direcciones coinciden entre versiones).

COMO USARLO:

    1. Confirmar que config.json -> azahar.process_name este en
       "sango-1" (Omega Ruby) antes de correr esto -- o, si no,
       editar PROCESS_NAME mas abajo directamente.
    2. Antes de correr esto, meter un Pokemon a la Caja PC a
       proposito (llenar la party a 6/6 y atrapar uno mas, o
       depositar uno a mano desde el PC) para tener algo fresco y
       facil de reconocer en el escaneo.
    3. Anotar el nickname/especie de ese Pokemon para poder
       reconocerlo en la salida.
    4. Correr:

           python -m tools.probes.party.buscar_caja_pc_or

    (Tarda un rato: el escaneo de CPU sobre una ventana de varios
    MB puede llevar uno o dos minutos, es normal.)
"""

from app.core.config import Config
from app.readers.azahar_reader import AzaharReader
from app.memory.pointers import (
    PROCESS_NAME_OMEGA_RUBY,
    get_party_order_address,
    POKEMON_POINTER_OFFSET,
    SLOT_DATA_SIZE,
)
from app.memory.structures import Pokemon6, decrypt_data


# Mismo tamaño de ventana que ya hizo falta para Alpha Sapphire
# (la primera pasada con 4MB por lado no alcanzo).
WINDOW_BEFORE = 0x1000000
WINDOW_AFTER = 0x1000000

ALIGNMENT = 4


def main():
    print("================================")
    print("   BUSCAR CAJA PC (Omega Ruby)")
    print("   (por checksum)")
    print("================================")
    print()

    process_name = Config().get(
        "azahar", "process_name", default=PROCESS_NAME_OMEGA_RUBY
    )

    if process_name != PROCESS_NAME_OMEGA_RUBY:
        print(
            f"Aviso: config.json tiene process_name={process_name!r}, "
            f"no {PROCESS_NAME_OMEGA_RUBY!r} (Omega Ruby). Se sigue "
            f"usando {process_name!r} para conectar, pero el ancla de "
            f"escaneo va a ser igual la de Omega Ruby -- si en "
            f"realidad estas en Alpha Sapphire, cancela (Ctrl+C) y "
            f"usa buscar_caja_pc.py en cambio."
        )
        print()

    party_order_address = get_party_order_address(
        PROCESS_NAME_OMEGA_RUBY
    )

    reader = AzaharReader(process_name=process_name)

    print(f"Buscando proceso {process_name!r}...")

    if not reader.connect():
        print(f"No se encontro {process_name!r}.")
        return

    print("Azahar conectado correctamente.")
    print()

    memory = reader.memory

    live_party_addresses = set()

    try:

        raw_pointers = reader.read_party_order()

        for raw_pointer in raw_pointers or []:

            if raw_pointer:
                live_party_addresses.add(
                    raw_pointer + POKEMON_POINTER_OFFSET
                )

    except Exception:
        pass

    scan_start = party_order_address - WINDOW_BEFORE
    scan_size = WINDOW_BEFORE + WINDOW_AFTER

    print(
        f"Ancla (PARTY_ORDER_ADDRESS Omega Ruby): "
        f"{hex(party_order_address)}"
    )
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

        absolute_address = scan_start + offset

        matches.append(
            (absolute_address, species_id, nickname)
        )

    print()
    print(f"Encontrados {len(matches)} candidatos con checksum valido.")
    print()

    if not matches:
        print(
            "Nada en esta ventana. Puede que la Caja PC este mas "
            "lejos de PARTY_ORDER_ADDRESS de lo esperado en Omega "
            "Ruby -- proximo paso seria Cheat Engine con el mismo "
            "ancla que ya funciono (CAPTURE_BUFFER_ADDRESS, "
            "compartida entre versiones)."
        )
        return

    print("Primeros 40 candidatos (dirección, especie, nickname):")

    for address, species_id, nickname in matches[:40]:

        tag = (
            " [EQUIPO ACTUAL]"
            if address in live_party_addresses
            else ""
        )

        print(
            f"  {hex(address)}  speciesId={species_id}  "
            f"nickname={nickname!r}{tag}"
        )

    if len(matches) > 40:
        print(f"  ... y {len(matches) - 40} más")

    new_matches = [
        m for m in matches
        if m[0] not in live_party_addresses
    ]

    print()
    print(
        f"De esos, {len(new_matches)} NO son tu equipo actual -- "
        f"son los que vale la pena revisar (buscá el nickname que "
        f"depositaste en la Caja PC)."
    )

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
            f"({most_common_gap[1]} veces) -- probablemente el "
            f"tamaño real de cada slot de la Caja PC en Omega Ruby."
        )


if __name__ == "__main__":
    main()

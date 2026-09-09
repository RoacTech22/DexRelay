"""
Verifica en vivo la acción nueva `item_list` del bridge (roadmap
07/09/2026 -- nombres de ítem para el catálogo de ítems, ver
Program.cs/HandleItemList()). Escrita sin poder compilar en esa
sesión (mejor conjetura del nombre real de la propiedad
`GameInfo.Strings.Item`) -- correr esto DESPUÉS de `dotnet publish`
para confirmar que compiló y que la lista sale bien, antes de
armar el catálogo de Python encima.

No necesita Azahar corriendo -- item_list() no lee memoria de
ningún juego, resuelve todo desde las tablas internas de
PKHeX.Core.

USO:
    python -m tools.probes.pkhex_item_list_probe
"""

from app.services.pkhex.bridge import PKHeXBridge


# Unos pocos ítems conocidos para chequear a ojo que los nombres
# salgan bien en español -- no hace falta imprimir los ~1000+
# completos para confirmar que anda.
ITEM_IDS_TO_SPOT_CHECK = {
    4: "Poké Ball",
    83: "Piedra Trueno (Thunder Stone)",
    50: "Caramelo Raro (Rare Candy, ya usado en BagService)",
    197: "Colmillo Afilado (Razor Fang, evolución de Gligar)",
}


def main():
    print("================================")
    print("   VERIFICAR item_list")
    print("================================")
    print()

    bridge = PKHeXBridge()

    result = bridge.item_list()

    if "error" in result:
        print(f"ERROR: {result['error']}")
        bridge.stop()
        return

    items = result.get("items", [])

    print(f"Total de ítems devueltos: {len(items)}")
    print()

    items_by_id = {item["id"]: item["name"] for item in items}

    print("Chequeo puntual:")
    for item_id, expected_hint in ITEM_IDS_TO_SPOT_CHECK.items():
        name = items_by_id.get(item_id, "*** NO ENCONTRADO ***")
        print(f"  id={item_id} ({expected_hint}): {name!r}")

    bridge.stop()

    print()
    print("Prueba finalizada.")


if __name__ == "__main__":
    main()

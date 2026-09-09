"""
Diagnóstico puntual (08/09/2026, reportado por el usuario:
"azurrill evoluciona a merril por amistad no esta saliendo eso
revisalo") -- imprime EXACTAMENTE lo que devuelve
species_details() para Azurill (#298) y Marill (#183), sin pasar
por ninguna otra capa (ni _build_evolution_chain(), ni
describe_evolution()), para ver si el problema está en:

  a) El bridge/PKHeX no reportando la evolución de Azurill (lista
     `evolutions` vacía o sin la entrada a Marill) -- problema en
     Program.cs / PKHeX.Core.
  b) El bridge SÍ reporta la evolución, pero con un `methodKey`
     que no es "LevelUpFriendship" (el único que está en la tabla
     de traducciones) -- problema de nombre de enum distinto al
     esperado.
  c) El bridge reporta todo bien, pero pre_evolution_index.json
     (el índice invertido armado por build_pre_evolution_index.py)
     no tiene a Marill apuntando a Azurill -- problema en ESE
     archivo, no en el bridge.

Revisar la revisión (a)/(b)/(c) le dice a Ronald (o a mí en la
próxima sesión) exactamente dónde está el problema real, en vez de
adivinar.

    python -m tools.probes.debug_azurill_marill_evolution
"""

import json

from app.core import paths
from app.services.pkhex.bridge import PKHeXBridge

AZURILL_ID = 298
MARILL_ID = 183


def main():
    print("=================================================")
    print("   DIAGNÓSTICO: AZURILL -> MARILL (amistad)")
    print("=================================================")
    print()

    bridge = PKHeXBridge()

    print(f"--- species_details({AZURILL_ID}) (Azurill) ---")
    azurill = bridge.species_details(AZURILL_ID)
    print(json.dumps(azurill, indent=2, ensure_ascii=False))
    print()

    print(f"--- species_details({MARILL_ID}) (Marill) ---")
    marill = bridge.species_details(MARILL_ID)
    print(json.dumps(marill, indent=2, ensure_ascii=False))
    print()

    bridge.stop()

    print("--- Análisis ---")

    azurill_evolutions = azurill.get("evolutions", [])

    if not azurill_evolutions:
        print(
            "PROBLEMA (a): la lista 'evolutions' de Azurill vino "
            "VACÍA. El bridge/PKHeX no está reportando ninguna "
            "evolución para esta especie -- revisar "
            "tree.Forward.GetForward() en Program.cs con este "
            "caso puntual."
        )
    else:
        marill_entry = next(
            (
                e for e in azurill_evolutions
                if e.get("toSpeciesId") == MARILL_ID
            ),
            None,
        )

        if marill_entry is None:
            print(
                "PROBLEMA (a-variante): Azurill SÍ tiene "
                f"evoluciones ({azurill_evolutions}), pero NINGUNA "
                f"apunta a Marill (id {MARILL_ID}). Revisar a qué "
                "especie apunta en realidad."
            )
        else:
            method_key = marill_entry.get("methodKey")
            print(
                f"Azurill -> Marill SÍ está en la lista, con "
                f"methodKey={method_key!r}, "
                f"level={marill_entry.get('level')}, "
                f"argument={marill_entry.get('argument')}"
            )

            if method_key != "LevelUpFriendship":
                print(
                    f"PROBLEMA (b): el methodKey real es "
                    f"{method_key!r}, NO 'LevelUpFriendship' como "
                    f"se había asumido -- hay que agregar "
                    f"{method_key!r} a EVOLUTION_METHOD_TEMPLATES "
                    f"en evolution_translations.py (y a "
                    f"METHOD_KEYS_USING_* si corresponde)."
                )
            else:
                print(
                    "El methodKey coincide con el ya traducido "
                    "('LevelUpFriendship') -- el bridge está bien, "
                    "el problema debe estar en (c), el índice de "
                    "pre-evolución, revisar abajo."
                )

    print()

    pre_evolution_index_path = paths.path(
        "data", "pre_evolution_index.json"
    )

    if not pre_evolution_index_path.exists():
        print(
            "AVISO: data/pre_evolution_index.json no existe -- "
            "hace falta correr "
            "tools.data_curation.build_pre_evolution_index primero."
        )
        return

    with open(
        pre_evolution_index_path, "r", encoding="utf-8"
    ) as file:
        pre_evolution_index = json.load(file)

    marill_pre_evolution = pre_evolution_index.get(str(MARILL_ID))

    print(
        f"pre_evolution_index.json['{MARILL_ID}'] (pre-evolución "
        f"registrada para Marill): {marill_pre_evolution}"
    )

    if not marill_pre_evolution:
        print(
            "PROBLEMA (c): el índice invertido NO tiene una "
            "pre-evolución registrada para Marill -- si "
            "species_details(Azurill) sí trae la evolución a "
            "Marill (revisar arriba), esto significa que "
            "build_pre_evolution_index.py hay que volver a "
            "correrlo (quizás se corrió ANTES de que esta parte "
            "del bridge funcionara bien, o falló silenciosamente "
            "para la especie #298 -- revisar el aviso de "
            "'especies fallidas' que imprime ese script)."
        )
    elif marill_pre_evolution.get("speciesId") != AZURILL_ID:
        print(
            f"PROBLEMA (c-variante): el índice dice que la "
            f"pre-evolución de Marill es "
            f"{marill_pre_evolution}, no Azurill (id "
            f"{AZURILL_ID}) -- revisar de dónde salió ese dato."
        )
    else:
        print(
            "El índice de pre-evolución está bien -- si el "
            "problema persiste, puede estar en "
            "_build_evolution_chain() (api.py) o en el frontend."
        )


if __name__ == "__main__":
    main()

"""
Valida app/services/evolution_translations.py contra los 33
methodKey REALES confirmados por
tools/probes/recolectar_evolution_method_keys.py (07/09/2026) --
no contra el enum completo de PKHeX.Core, que tiene variantes de
generaciones posteriores que ORAS nunca muestra.

    python -m tools.probes.test_evolution_translations
"""

from app.services.evolution_translations import describe_evolution


# Los 33 methodKey reales, tal como los confirmó el probe -- si
# alguno de estos faltara en la tabla, describe_evolution()
# devolvería "[methodKey]" en vez de una traducción real.
REAL_METHOD_KEYS = [
    "LevelUp",
    "LevelUpATK",
    "LevelUpAeqD",
    "LevelUpAffection50MoveType",
    "LevelUpBeauty",
    "LevelUpCold",
    "LevelUpDEF",
    "LevelUpECgeq5",
    "LevelUpECl5",
    "LevelUpElectric",
    "LevelUpFemale",
    "LevelUpForest",
    "LevelUpFormFemale1",
    "LevelUpFriendship",
    "LevelUpFriendshipMorning",
    "LevelUpFriendshipNight",
    "LevelUpHeldItemDay",
    "LevelUpHeldItemNight",
    "LevelUpInverted",
    "LevelUpKnowMove",
    "LevelUpMale",
    "LevelUpMorning",
    "LevelUpMoveType",
    "LevelUpNight",
    "LevelUpNinjask",
    "LevelUpShedinja",
    "LevelUpWithTeammate",
    "Trade",
    "TradeHeldItem",
    "TradeShelmetKarrablast",
    "UseItem",
    "UseItemFemale",
    "UseItemMale",
]


def test_los_33_methodkey_reales_tienen_traduccion():

    sin_traducir = []

    for method_key in REAL_METHOD_KEYS:

        text = describe_evolution(method_key, level=1, argument=1)

        if text == f"[{method_key}]":
            sin_traducir.append(method_key)

    assert not sin_traducir, (
        f"Estos methodKey reales no tienen traducción todavía: "
        f"{sin_traducir}"
    )

    print(
        f"OK - los {len(REAL_METHOD_KEYS)} methodKey reales "
        f"confirmados tienen traducción"
    )


def test_desconocido_no_inventa_texto():
    """
    Un methodKey que no esté en la tabla (ej. de una generación
    posterior, si algún día se agrega soporte) devuelve el
    methodKey crudo entre corchetes -- señal visible de que falta
    agregarlo, no un texto inventado que parezca válido.
    """

    text = describe_evolution("MethodKeyInventadoQueNoExiste")

    assert text == "[MethodKeyInventadoQueNoExiste]", (
        f"Un methodKey desconocido debería quedar entre "
        f"corchetes, dio {text!r}."
    )

    print(
        "OK - un methodKey desconocido no inventa texto, queda "
        "marcado entre corchetes"
    )


def test_sustituye_nivel_donde_corresponde():

    text = describe_evolution("LevelUp", level=16)

    assert text == "Sube al nivel 16", (
        f"Debería sustituir {{level}} en la plantilla, dio "
        f"{text!r}."
    )

    print("OK - sustituye {level} en las plantillas que lo usan")


def test_sustituye_nombre_de_objeto_cuando_se_resuelve():
    """
    07/09/2026: con item_name resuelto (ej. vía ItemCatalog),
    el texto usa el nombre real -- sin item_name, cae al genérico
    "un objeto" (nunca queda un "{item}" crudo sin reemplazar).
    """

    con_nombre = describe_evolution("UseItem", item_name="Piedra Trueno")
    assert con_nombre == "Se usa Piedra Trueno", (
        f"Debería usar el nombre real del objeto, dio {con_nombre!r}."
    )

    sin_nombre = describe_evolution("UseItem")
    assert sin_nombre == "Se usa un objeto", (
        f"Sin item_name debería caer al genérico, dio {sin_nombre!r}."
    )

    print(
        "OK - usa el nombre real del objeto cuando se resuelve, "
        "cae a 'un objeto' si no"
    )


def test_sustituye_nombre_de_movimiento_y_companero():
    """
    07/09/2026: mismo criterio que el objeto, para
    LevelUpKnowMove (movimiento) y LevelUpWithTeammate (especie
    compañera).
    """

    con_movimiento = describe_evolution("LevelUpKnowMove", move_name="Rollout")
    assert con_movimiento == "Sube de nivel conociendo Rollout", (
        f"Debería usar el nombre real del movimiento, dio "
        f"{con_movimiento!r}."
    )

    sin_movimiento = describe_evolution("LevelUpKnowMove")
    assert sin_movimiento == "Sube de nivel conociendo un movimiento específico", (
        f"Sin move_name debería caer al genérico, dio {sin_movimiento!r}."
    )

    con_companero = describe_evolution(
        "LevelUpWithTeammate", teammate_name="Remoraid"
    )
    assert con_companero == "Sube de nivel con Remoraid en el equipo", (
        f"Debería usar el nombre real del compañero, dio "
        f"{con_companero!r}."
    )

    sin_companero = describe_evolution("LevelUpWithTeammate")
    assert sin_companero == "Sube de nivel con un compañero específico en el equipo", (
        f"Sin teammate_name debería caer al genérico, dio "
        f"{sin_companero!r}."
    )

    print(
        "OK - usa el nombre real del movimiento/compañero cuando "
        "se resuelve, cae al genérico si no"
    )


def test_azurill_marill_tiene_etiqueta_compacta():
    """
    08/09/2026: caso real reportado por el usuario -- confirmado
    con tools/probes/debug_azurill_marill_evolution.py que Azurill
    evoluciona a Marill con methodKey='LevelUpFriendship',
    level=0, argument=0. El bug real estaba en el frontend (0 es
    falsy en JS), pero de este lado hace falta que exista una
    etiqueta compacta para este methodKey -- sin eso, el conector
    no tendría nada que mostrar.
    """

    from app.services.evolution_translations import (
        EVOLUTION_METHOD_COMPACT_LABELS,
    )

    assert EVOLUTION_METHOD_COMPACT_LABELS.get("LevelUpFriendship") == "Amistad"

    print("OK - LevelUpFriendship tiene etiqueta compacta ('Amistad')")


if __name__ == "__main__":
    test_los_33_methodkey_reales_tienen_traduccion()
    test_desconocido_no_inventa_texto()
    test_sustituye_nivel_donde_corresponde()
    test_sustituye_nombre_de_objeto_cuando_se_resuelve()
    test_sustituye_nombre_de_movimiento_y_companero()
    test_azurill_marill_tiene_etiqueta_compacta()

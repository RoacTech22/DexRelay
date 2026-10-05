from __future__ import annotations

import struct

from app.memory.memory_reader import MemoryReader


# Bloque 11 (ruta multijuego): estos valores viven ahora en el perfil de
# ORAS (app/games/oras/profile.py); acá se conservan los mismos nombres
# para no cambiar ningún import ni test. Los comentarios de
# investigación de abajo se quedan como referencia histórica.
from app.games.oras.profile import ALPHA_SAPPHIRE as _ORAS_PROFILE

_ORAS_MAP = _ORAS_PROFILE.memory_map

COMBAT_POINTER_ADDRESS = _ORAS_MAP.combat_pointer_address
COMBAT_HP_OFFSET = _ORAS_MAP.combat_hp_offset

# ============================================================
# FLAG SALVAJE / ENTRENADOR
# ============================================================
#
# Confirmado empiricamente el 27/08/2026, como parte de la
# investigacion del estado "perdido" automatico del Nuzlocke
# Tracker (ver DexRelay_Contexto_Deteccion_Perdido.md -- pieza 2 de
# 3, ya resuelta).
#
# Encontrado con tools/probes/memory/buscar_flag_tipo_combate.py:
# offset relativo a la base de combate (la misma base dinamica que
# ya usa COMBAT_HP_OFFSET) donde el juego deja la zona en CERO
# durante un combate de entrenador, y la deja con datos (valores
# constantes pero !=0, probablemente una entrada de una tabla de
# encuentro salvaje) durante un combate salvaje.
#
# Confirmado con 2 rondas de pruebas (9 muestras salvajes + 8 de
# entrenador en total, bases de combate distintas cada vez) y una
# prueba de robustez especifica: combate salvaje inmediatamente
# seguido de un combate de entrenador (sin otro salvaje en el
# medio), repetido 3 veces -- el valor de entrenador siguio dando 0
# las 3 veces, descartando que fuera memoria vieja del salvaje
# anterior sin limpiar (mismo tipo de trampa que ya paso una vez
# con LAST_CAUGHT_ADDRESS, seccion 14 del Documento Maestro).
#
# IMPORTANTE: se lee como flag booleano (0 = entrenador, !=0 =
# salvaje), NO se compara contra un valor exacto -- los valores
# vistos durante la investigacion (20, 227, etc.) se mantuvieron
# constantes en las pruebas realizadas, pero no hay garantia de que
# sean iguales para todas las especies/niveles no probados todavia.
# Comparar solo contra cero es mas robusto.
WILD_BATTLE_FLAG_OFFSET = _ORAS_MAP.wild_battle_flag_offset

# Confirmado con tools/probes/combat/observar_puntero_combate.py:
# al salir de combate, el puntero NO vuelve a 0x00000000. Se queda
# en este valor fijo (COMBAT_POINTER_ADDRESS - 4), que es memoria
# "basura" reutilizada por el juego, no una estructura de batalla
# real. Si se trata como puntero valido, CombatService devuelve un
# HP congelado (el ultimo leido antes de salir de combate) para
# siempre, en vez de reportar que ya no hay combate.
COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4

# Guard de plausibilidad (23/09/2026, log real del usuario: un
# "perdido" se registró solo con el jugador ni siquiera dentro de
# una partida cargada -- puntero de combate = 0x01023445, flag
# salvaje leído como SALVAJE). No es una dirección confirmada con
# un probe dedicado (regla 1/11 del Documento Maestro) -- es un
# chequeo de plausibilidad: TODAS las direcciones ya confirmadas en
# todo este proyecto (party, cajas, medallas, rival salvaje, el
# propio COMBAT_POINTER_ADDRESS -- ver pointers.py) caen en
# 0x08000000 o más arriba (el heap lineal/FCRAM del 3DS emulado que
# expone Azahar). 0x01023445 está muy por debajo de ese rango --
# consistente con memoria sin inicializar en ese slot antes de que
# el juego escriba una estructura de combate real ahí, no con un
# combate real. Si algún combate real confirmado alguna vez cae por
# debajo de este piso, HAY QUE subirlo o sacarlo -- no bajarlo a
# ciegas sin evidencia nueva.
MIN_PLAUSIBLE_COMBAT_POINTER = 0x08000000

# Dedup del print de abajo -- un valor de puntero implausible se
# puede repetir varios ciclos seguidos (200ms) mientras el juego
# sigue sin escribir nada real ahí; avisar una sola vez por valor
# distinto alcanza, no hace falta spamear la consola/Logs.
_warned_implausible_pointers: set[int] = set()


def _looks_like_real_combat_pointer(base_address: int) -> bool:
    if base_address >= MIN_PLAUSIBLE_COMBAT_POINTER:
        return True

    if base_address not in _warned_implausible_pointers:
        _warned_implausible_pointers.add(base_address)
        print(
            "[CombatService] Puntero de combate implausible "
            f"({hex(base_address)}, por debajo de "
            f"{hex(MIN_PLAUSIBLE_COMBAT_POINTER)}) -- se trata "
            "como 'sin combate'. Si esto rechaza un combate REAL "
            "alguna vez, avisar para revisar el piso.",
            flush=True,
        )

    return False


_warned_unknown_battle_pointers: set[int] = set()


def _warn_unknown_battle_pointer(base_address: int) -> None:
    """
    Combate con una base que el perfil no conoce (otro tipo de encuentro:
    horda, doble, Safari, etc.): no se adivina, se descarta la lectura y
    se avisa una vez por valor para poder agregarlo al perfil.
    """
    if base_address in _warned_unknown_battle_pointers:
        return

    _warned_unknown_battle_pointers.add(base_address)
    print(
        "[CombatService] Combate con una base desconocida "
        f"({hex(base_address)}): no se clasifica como salvaje ni de "
        "entrenador. Avisar para agregarla al perfil.",
        flush=True,
    )


LECTURA_DESCARTADA = object()


class CombatService:
    """Lee el HP de combate validando la consistencia del puntero."""

    def __init__(self, memory_reader: MemoryReader, profile_provider=None) -> None:
        self.memory_reader = memory_reader
        # Bloque 15: el mapa de combate sale del perfil del juego
        # conectado. Sin provider (tests y probes antiguos) se usa el de
        # ORAS de siempre.
        self.profile_provider = profile_provider

    def _combat_map(self):
        """MemoryMap del juego actual con el combate confirmado, o None."""

        if self.profile_provider is None:
            return _ORAS_MAP

        profile = self.profile_provider()

        if profile is None:
            return None

        memory_map = profile.memory_map

        if (
            memory_map.combat_pointer_address is None
            or memory_map.combat_inactive_pointers is None
        ):
            return None

        return memory_map

    def read(self):
        """Lee el HP de combate."""

        combat = self._combat_map()

        if combat is None or combat.combat_hp_offset is None:
            return None

        pointer_before = self.memory_reader.read(
            combat.combat_pointer_address,
            4,
        )

        # Bug real (04/09/2026, mismo patrón que ya se encontró en
        # azahar_reader.py y badges_service.py): memory_reader.read()
        # puede devolver None en un fallo transitorio de socket, no
        # solo lanzar una excepción -- len(None) tira TypeError en
        # vez de tratarse como una lectura descartada más.
        if pointer_before is None or len(pointer_before) != 4:
            return LECTURA_DESCARTADA

        base_address = struct.unpack(
            "<I",
            pointer_before,
        )[0]

        if base_address in combat.combat_inactive_pointers or not (
            _looks_like_real_combat_pointer(base_address)
        ):
            return None

        hp_data = self.memory_reader.read(
            base_address + combat.combat_hp_offset,
            2,
        )

        if hp_data is None or len(hp_data) != 2:
            return LECTURA_DESCARTADA

        pointer_after = self.memory_reader.read(
            combat.combat_pointer_address,
            4,
        )

        if pointer_after != pointer_before:
            return LECTURA_DESCARTADA

        return struct.unpack(
            "<H",
            hp_data,
        )[0]

    def read_combat_base_pointer(self):
        """
        Diagnóstico agregado el 23/09/2026 (log real del usuario:
        un "perdido" se registró solo -- flag salvaje = SALVAJE,
        snapshot en Pueblo Azuliza con total_caught=9 -- sin que
        hubiera ningún combate real en curso). Devuelve el valor
        CRUDO del puntero de combate (o None si la lectura falla),
        solo para loguearlo -- no decide nada, `read()`/
        `read_wild_flag()` siguen siendo la única fuente de verdad
        para eso.

        Hipótesis a confirmar con el próximo log real (no se toca
        la lógica de detección todavía, regla 1/11 del Documento
        Maestro -- no inventar sin confirmar en la instancia real):
        hoy solo se excluye UN valor conocido de "puntero en
        reposo" (COMBAT_INACTIVE_POINTER). Si el juego puede dejar
        el puntero en OTROS valores de reposo además de ese, un
        combate falso positivo como el reportado tendría sentido.
        Este método deja ver, la próxima vez que pase, exactamente
        qué valor tenía el puntero -- con eso se puede confirmar o
        descartar la hipótesis antes de tocar nada más.
        """

        if self.memory_reader is None:
            return None

        combat = self._combat_map()

        if combat is None:
            return None

        pointer_data = self.memory_reader.read(
            combat.combat_pointer_address,
            4,
        )

        if pointer_data is None or len(pointer_data) != 4:
            return None

        return struct.unpack("<I", pointer_data)[0]

    def read_wild_flag(self):
        """
        Lee si el combate activo es salvaje o de entrenador (ver
        WILD_BATTLE_FLAG_OFFSET arriba), con la misma validación
        de consistencia de puntero antes/después que read(). Usado
        por Runtime para la detección automática del estado
        "perdido" del Nuzlocke Tracker.

        Devuelve:
        - None: no hay combate activo.
        - True: hay un combate salvaje activo.
        - False: hay un combate de entrenador activo.
        - LECTURA_DESCARTADA: lectura inconsistente (el puntero
          cambió a mitad de lectura) -- igual que read(), se
          descarta y se reintenta el próximo ciclo.
        """

        combat = self._combat_map()

        if combat is None or (
            combat.wild_battle_flag_offset is None
            and combat.wild_battle_pointers is None
        ):
            return None

        pointer_before = self.memory_reader.read(
            combat.combat_pointer_address,
            4,
        )

        # Ídem read(): None es posible, no solo longitud invalida.
        if pointer_before is None or len(pointer_before) != 4:
            return LECTURA_DESCARTADA

        base_address = struct.unpack(
            "<I",
            pointer_before,
        )[0]

        if base_address in combat.combat_inactive_pointers or not (
            _looks_like_real_combat_pointer(base_address)
        ):
            return None

        if combat.wild_battle_pointers is not None:
            # X/Y: el tipo de combate lo da el valor de la celda.
            if base_address in combat.wild_battle_pointers:
                result = True
            elif base_address in (combat.trainer_battle_pointers or ()):
                result = False
            else:
                _warn_unknown_battle_pointer(base_address)
                return LECTURA_DESCARTADA
        else:
            flag_data = self.memory_reader.read(
                base_address + combat.wild_battle_flag_offset,
                1,
            )

            if flag_data is None or len(flag_data) != 1:
                return LECTURA_DESCARTADA

            result = flag_data[0] != 0

        pointer_after = self.memory_reader.read(
            combat.combat_pointer_address,
            4,
        )

        if pointer_after != pointer_before:
            return LECTURA_DESCARTADA

        return result

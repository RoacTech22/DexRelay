from __future__ import annotations

import struct

from app.memory.memory_reader import MemoryReader


COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_HP_OFFSET = 0x404

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
WILD_BATTLE_FLAG_OFFSET = 0x87F

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


LECTURA_DESCARTADA = object()


class CombatService:
    """Lee el HP de combate validando la consistencia del puntero."""

    def __init__(self, memory_reader: MemoryReader) -> None:
        self.memory_reader = memory_reader

    def read(self):
        """Lee el HP de combate."""

        pointer_before = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
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

        if base_address in (0, COMBAT_INACTIVE_POINTER) or not (
            _looks_like_real_combat_pointer(base_address)
        ):
            return None

        hp_data = self.memory_reader.read(
            base_address + COMBAT_HP_OFFSET,
            2,
        )

        if hp_data is None or len(hp_data) != 2:
            return LECTURA_DESCARTADA

        pointer_after = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
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

        pointer_data = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
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

        pointer_before = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
            4,
        )

        # Ídem read(): None es posible, no solo longitud invalida.
        if pointer_before is None or len(pointer_before) != 4:
            return LECTURA_DESCARTADA

        base_address = struct.unpack(
            "<I",
            pointer_before,
        )[0]

        if base_address in (0, COMBAT_INACTIVE_POINTER) or not (
            _looks_like_real_combat_pointer(base_address)
        ):
            return None

        flag_data = self.memory_reader.read(
            base_address + WILD_BATTLE_FLAG_OFFSET,
            1,
        )

        if flag_data is None or len(flag_data) != 1:
            return LECTURA_DESCARTADA

        pointer_after = self.memory_reader.read(
            COMBAT_POINTER_ADDRESS,
            4,
        )

        if pointer_after != pointer_before:
            return LECTURA_DESCARTADA

        return flag_data[0] != 0

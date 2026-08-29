# ============================================================
# PUNTEROS Y TAMAÑOS DE MEMORIA DE POKÉMON ALPHA SAPPHIRE / OMEGA RUBY
# ============================================================

# Nombres de proceso dentro de Azahar -- confirmados empíricamente
# (29/08/2026, ver Documento Maestro sección 14/17): las dos
# versiones NO comparten process_name, así que se usa como llave
# para elegir qué set de direcciones corresponde. Configurable en
# config.json -> azahar.process_name.
PROCESS_NAME_ALPHA_SAPPHIRE = "sango-2"
PROCESS_NAME_OMEGA_RUBY = "sango-1"

# Tabla que contiene el orden lógico de los Pokémon de la party.
# CONFIRMADO (29/08/2026): esta dirección NO es la misma entre
# Alpha Sapphire y Omega Ruby -- la de AS da 0x0 en los 6 slots
# probando en OR (investigación completa en el Documento Maestro,
# sección 14 y 19). Encontrada la de OR con el mismo método que
# PARTY_COUNT_ADDRESS: por la relación PARTY_COUNT = PARTY_ORDER +
# 0x18, ya confirmada para AS, aplicada a la inversa sobre el
# PARTY_COUNT_ADDRESS de OR (confirmado primero, en vivo, con
# Cheat Engine) para llegar a esta dirección -- y confirmada en
# vivo con observar_orden_party_or.py: 6 punteros no-cero que se
# reordenan solos al reordenar el equipo, igual que en AS.
_PARTY_ORDER_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08CF71F0,
    PROCESS_NAME_OMEGA_RUBY: 0x08CFB1E0,
}

# Cada entrada de la tabla ocupa 4 bytes.
ORDER_ENTRY_SIZE = 4

# Cantidad REAL de Pokémon en la party (1 byte) -- confirmada
# empíricamente el 29/08/2026 con Cheat Engine (investigación del
# bug donde el slot que quedaba libre al depositar en la Caja PC
# se seguía mostrando con el sprite del último Pokémon del
# equipo). Justo el byte siguiente al final de la tabla de 6
# punteros (PARTY_ORDER_ADDRESS + 0x18, ya que 6 punteros × 4
# bytes = 0x18) -- un lugar muy lógico, pegado a la tabla que
# describe. Misma relación confirmada para las dos versiones.
#
# Confirmado en vivo bajando de 6 a 2 en tiempo real (Alpha
# Sapphire) y subiendo/bajando 1→5→4 (Omega Ruby), exactamente en
# el momento de cada depósito/extracción. La causa real del bug:
# PARTY_ORDER_ADDRESS son 6 casilleros FIJOS que el juego siempre
# mantiene reservados en memoria -- al depositar un Pokémon, su
# puntero NO se limpia (sigue apuntando a datos válidos, por eso
# decodificaba bien y aparecía "fantasma" en el overlay). Hay que
# consultar esta dirección para saber cuántos de esos 6 punteros
# son realmente parte de la party actual.
_PARTY_COUNT_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08CF7208,
    PROCESS_NAME_OMEGA_RUBY: 0x08CFB1F8,
}


def get_party_order_address(process_name):
    """
    Devuelve la PARTY_ORDER_ADDRESS correcta según qué versión
    está corriendo (identificada por `process_name`, el mismo
    valor que ya usa AzaharReader para encontrar el proceso en
    Azahar). Si `process_name` no es ninguno de los confirmados,
    devuelve la de Alpha Sapphire como default -- mismo criterio
    que el resto del proyecto (preferir un valor conocido antes
    que fallar por completo), documentado para que quede claro
    que es una suposición, no una confirmación.
    """

    return _PARTY_ORDER_ADDRESS_BY_PROCESS.get(
        process_name,
        _PARTY_ORDER_ADDRESS_BY_PROCESS[
            PROCESS_NAME_ALPHA_SAPPHIRE
        ],
    )


def get_party_count_address(process_name):
    """Ídem get_party_order_address(), para PARTY_COUNT_ADDRESS."""

    return _PARTY_COUNT_ADDRESS_BY_PROCESS.get(
        process_name,
        _PARTY_COUNT_ADDRESS_BY_PROCESS[
            PROCESS_NAME_ALPHA_SAPPHIRE
        ],
    )


# Se mantienen como constantes planas también, apuntando a Alpha
# Sapphire -- para no romper código/tests/probes existentes que
# las importan directo sin pasar por el selector de versión (la
# gran mayoría de los usos actuales de DexRelay siguen siendo
# sobre Alpha Sapphire). El código que sí necesita ser correcto
# para las dos versiones (AzaharReader.read_party_order()) usa
# los getters de arriba en cambio.
PARTY_ORDER_ADDRESS = _PARTY_ORDER_ADDRESS_BY_PROCESS[
    PROCESS_NAME_ALPHA_SAPPHIRE
]
PARTY_COUNT_ADDRESS = _PARTY_COUNT_ADDRESS_BY_PROCESS[
    PROCESS_NAME_ALPHA_SAPPHIRE
]

# El puntero obtenido de la tabla apunta 0x40 bytes
# antes de la estructura principal del Pokémon.
POKEMON_POINTER_OFFSET = 0x40


# ============================================================
# ESTRUCTURA PK6
# ============================================================

# Tamaño de la estructura principal del Pokémon.
SLOT_DATA_SIZE = 232

# Tamaño de cada bloque utilizado durante el descifrado.
BLOCK_SIZE = 56


# ============================================================
# DATOS ADICIONALES
# ============================================================

# Offset de los datos adicionales respecto a la estructura.
STAT_DATA_OFFSET = 112

# Cantidad de bytes de datos adicionales que se leen.
STAT_DATA_SIZE = 22


# ============================================================
# ÚLTIMO POKÉMON ATRAPADO (buffer de captura)
# ============================================================

# Dirección FIJA confirmada empíricamente el 25/08/2026: contiene
# siempre el Pokémon capturado más recientemente, incluso si fue
# directo a la Caja PC porque la party estaba llena (en ese caso
# nunca aparece en la party ni en /api/team, así que sin esto el
# Nuzlocke Tracker no se enteraba de esas capturas).
#
# Se descubrió investigando la Caja PC: esta dirección es la
# séptima posición de un buffer que refleja los 6 miembros de la
# party actual + 1 posición extra con el último atrapado. Las
# primeras 6 posiciones están separadas por el mismo stride que la
# tabla real de la party (0x1E4 = 484 bytes cada una), PERO la
# séptima NO sigue ese mismo espaciado (queda a +0x230 de la sexta,
# no a +0x1E4) -- por eso se fija directamente el valor confirmado
# en vez de calcularlo con una fórmula, que daría un resultado
# incorrecto (0x88055EC en vez del real 0x8805638).
#
# Confirmado con dos capturas reales consecutivas (Pandy/Pancham y
# luego QAS/Phanpy): la misma dirección fija mostró cada vez el
# Pokémon recién atrapado, reemplazando al anterior.
CAPTURE_BUFFER_ADDRESS = 0x08804A94
CAPTURE_BUFFER_ENTRY_STRIDE = 0x1E4

LAST_CAUGHT_ADDRESS = 0x08805638


# ============================================================
# CONTADOR DE POKÉMON CAPTURADOS EN TOTAL
# ============================================================

# Dirección FIJA confirmada empíricamente el 25/08/2026 (con
# Cheat Engine + puente de traducción calculado con el puntero de
# party como ancla estable): sube en exactamente 1 cada vez que se
# captura un Pokémon real, sin importar si termina en la party o
# en la Caja PC. Verificado en vivo: no cambia con encuentros
# salvajes sin captura (huir/derrotar), sube justo al capturar.
#
# Se usa como "disparador" de confianza junto con
# LAST_CAUGHT_ADDRESS: LAST_CAUGHT_ADDRESS por sí sola resultó ser
# "último Pokémon salvaje contra el que se peleó" (se lo capture o
# no), así que no alcanza para saber si hubo captura real. Este
# contador sí lo confirma -- solo cuando sube, se confía en lo que
# haya en LAST_CAUGHT_ADDRESS en ese momento.
#
# Cae, como era de esperar, justo entre las otras dos direcciones
# fijas ya confirmadas de la partida (BADGES_ADDRESS=0x08C6DDD4 y
# PARTY_ORDER_ADDRESS=0x08CF71F0) -- buena señal de que están todas
# en la misma región de datos de guardado.
#
# NOTA (26-27/08/2026): ya NO se usa activamente para detectar
# capturas -- reemplazado por el escaneo directo de la Caja PC
# (BOX_BASE_ADDRESS más abajo), que es más simple y confiable.
# Se deja definida por si hace falta para otra función a futuro
# (ej. mostrar "capturados: XX" en la GUI).
TOTAL_CAUGHT_ADDRESS = 0x08C8729C


# ============================================================
# CAJA PC (Caja 1)
# ============================================================

# Direcciones FIJAS confirmadas empíricamente el 26-27/08/2026,
# escaneando memoria por checksum PK6 válido (mismo enfoque que ya
# se usó para badges y el contador de capturas: no adivinar un
# offset, buscar la señal real).
#
# A diferencia de LAST_CAUGHT_ADDRESS (un buffer reciclado de
# "último Pokémon salvaje enfrentado", con datos que tardaban en
# terminar de escribirse), esta es la Caja PC real y persistente:
# un array compacto de estructuras PK6 de 232 bytes cada una, sin
# padding entre slots (BOX_SLOT_STRIDE == SLOT_DATA_SIZE exacto).
#
# Confirmado con 3 escaneos reales (incluyendo uno después de
# reiniciar Azahar por completo): la dirección no se mueve entre
# reinicios, y el contenido coincidió exactamente con lo que había
# en la caja en cada momento (incluso reordenamientos manuales del
# usuario, no solo capturas nuevas). BOX_BASE_ADDRESS es el slot 1;
# confirmado también que el slot 2 real es BOX_BASE_ADDRESS +
# BOX_SLOT_STRIDE (0x08C9A22C), lo cual valida el stride.
#
# El formato de la Caja PC son los 232 bytes "box format" del PK6,
# SIN los datos extra de nivel/HP actual que sí tiene la party (ver
# AzaharReader.read_box()) -- el juego los recalcula al retirar el
# Pokémon, tiene sentido que no estén guardados en la caja.
#
# BOX_SLOT_COUNT es la capacidad estándar de una caja en ORAS (30).
# Solo se confirmaron empíricamente los primeros 5 slots -- el
# resto se asume por el tamaño estándar del juego, no está
# validado slot por slot.
BOX_BASE_ADDRESS = 0x08C9A144
BOX_SLOT_STRIDE = 0xE8
BOX_SLOT_COUNT = 30


# ============================================================
# ZONA/RUTA ACTUAL DEL JUGADOR
# ============================================================

# Dirección FIJA confirmada empíricamente el 27/08/2026, como parte
# de la investigación del estado "perdido" automático del Nuzlocke
# Tracker (ver DexRelay_Contexto_Deteccion_Perdido.md -- pieza 1 de
# 3, ya resuelta).
#
# Encontrada con tools/probes/memory/rastrear_zona_actual.py
# (escaneo por secuencia de lugares con al menos una repetición,
# filtrando "mismo lugar = mismo valor, lugar distinto = valor
# distinto") y confirmada con tools/probes/memory/
# verificar_zona_actual.py (observación en vivo).
#
# Pasó las tres pruebas necesarias antes de fijarla (regla #14):
#   1. Dos escaneos por secuencia independientes (distinta
#      secuencia de lugares, distinto save) -- mismo offset
#      sobrevivió ambos.
#   2. Filtro de estabilidad por offset (varias lecturas seguidas
#      con el jugador quieto) -- el valor no cambia estando quieto.
#   3. Confirmación en vivo manual: el valor se mantiene igual
#      caminando dentro de la MISMA ruta/zona, y solo cambia al
#      cruzar a una zona distinta -- exactamente el comportamiento
#      esperado de un ID de zona real.
#
# Nota importante de la investigación: una primera lectura rápida
# (una sola lectura por lugar, sin filtro de estabilidad) había
# hecho pasar este mismo offset como candidato en base a una
# coincidencia -- pero al observarlo en vivo mientras el usuario
# CAMINABA (no parado quieto) el valor cambiaba constantemente,
# haciendo sospechar que era ruido de movimiento/animación. Se
# resolvió repitiendo la prueba en vivo con el jugador parado
# quieto dentro de la misma zona (sin cambios) y recién después
# caminando hasta cruzar a otra zona (ahí sí cambia) -- confirmando
# que el candidato es válido y que el "cambio constante" de la
# primera observación fue simplemente que se cruzaba de zona muy
# seguido sin registrar cada cruce por separado.
#
# CURRENT_ZONE_ID_MIRROR_ADDRESS es una segunda dirección que
# siempre reportó el mismo valor que la principal en todas las
# pruebas -- el juego parece guardar el ID de zona duplicado en dos
# lugares. Se deja documentada por si en el futuro conviene leer
# ambas como chequeo de consistencia (mismo patrón defensivo que ya
# se usa en otras lecturas del proyecto), pero por ahora alcanza
# con leer la principal.
#
# Formato: 1 byte, valor crudo sin traducir. FALTA armar la tabla
# ID -> nombre de lugar (tabla NUEVA, separada de la que ya usa
# PKHeX para Met_Location -- no hay garantía de que coincidan los
# IDs). Valores confirmados hasta ahora durante la investigación
# (recolectados de las corridas de rastrear_zona_actual.py, no
# verificados individualmente uno por uno todavía):
#
#   Ruta101 = 23      PuebloEscaso = 7      Ruta103 = 25
#   BosquePetalia = 82   Ruta104 = 26   CiudadFerrica = 16
#   Ruta116 = 43         TunelFervegal = 75
CURRENT_ZONE_ID_ADDRESS = 0x08C6A7B2
CURRENT_ZONE_ID_MIRROR_ADDRESS = 0x08C6A894
# ============================================================
# PUNTEROS Y TAMAÑOS DE MEMORIA DE POKÉMON ALPHA SAPPHIRE
# ============================================================

# Tabla que contiene el orden lógico de los Pokémon de la party.
PARTY_ORDER_ADDRESS = 0x08CF71F0

# Cada entrada de la tabla ocupa 4 bytes.
ORDER_ENTRY_SIZE = 4

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
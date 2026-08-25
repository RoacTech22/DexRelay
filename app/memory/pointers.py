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
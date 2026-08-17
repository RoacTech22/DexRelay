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
# ============================================================
# PUNTEROS Y TAMAÑOS DE MEMORIA DE POKÉMON ALPHA SAPPHIRE / OMEGA RUBY
# ============================================================

# Nombres de proceso dentro de Azahar -- confirmados empíricamente
# (29/08/2026, ver Documento Maestro sección 14/17): las dos
# versiones NO comparten process_name, así que se usa como llave
# para elegir qué set de direcciones corresponde. Configurable en
# config.json -> azahar.process_name.
#
# REQUISITO REAL DE VERSIÓN DE JUEGO (04/09/2026): las direcciones
# de este archivo se confirmaron contra Omega Ruby CON la
# actualización 1.4 instalada. Sin el parche (juego base tal cual
# viene de fábrica), el mapa de memoria queda corrido y estas
# direcciones ya no apuntan a nada válido -- se manifiesta como
# "el equipo no carga" (Dashboard y página Pokémon vacíos) sin
# ningún error visible, ni una lectura fallida: la dirección
# simplemente cae en un lugar distinto de memoria. Encontrado
# porque al usuario se le había borrado por error la actualización
# de su copia de Omega Ruby. Alpha Sapphire no mostró este
# síntoma, pero probablemente aplica igual si le faltara su
# propia actualización -- no confirmado todavía, revisar si vuelve
# a aparecer un "no carga el equipo" sin explicación.
# REQUISITO REAL DE VERSIÓN DE JUEGO (04/09/2026): las direcciones
# de este archivo se confirmaron contra Omega Ruby CON la
# actualización 1.4 instalada. Sin el parche (juego base tal cual
# viene de fábrica), el mapa de memoria queda corrido y estas
# direcciones ya no apuntan a nada válido -- se manifiesta como
# "el equipo no carga" (Dashboard y página Pokémon vacíos) sin
# ningún error visible, ni una lectura fallida: la dirección
# simplemente cae en un lugar distinto de memoria. Encontrado
# porque al usuario se le había borrado por error la actualización
# de su copia de Omega Ruby.
#
# CONFIRMADO (04/09/2026): Alpha Sapphire tiene el MISMO problema
# al revés -- las direcciones actuales (PARTY_ORDER_ADDRESS =
# 0x08CF71F0 y el resto de _BY_PROCESS de acá abajo) están
# confirmadas contra el juego BASE de Alpha Sapphire, sin la
# actualización 1.4. Con el parche puesto, no funcionan (mismo
# síntoma: equipo vacío, sin error).
#
# PENDIENTE (a propósito, para otra sesión -- no urgente, el
# usuario decidió seguir jugando la versión base de AS por ahora):
# volver a investigar con Cheat Engine en vivo, jugando Alpha
# Sapphire CON la actualización 1.4, las direcciones equivalentes
# a PARTY_ORDER_ADDRESS/PARTY_COUNT_ADDRESS/BOX_BASE_ADDRESS/
# CURRENT_ZONE_ID_ADDRESS para esa versión -- mismo proceso que ya
# se hizo para Omega Ruby. Importante: el process_name (sango-2)
# es el MISMO esté parcheado o no -- Azahar no expone la versión
# del juego por este protocolo, así que DexRelay no puede elegir
# solo qué set de direcciones usar si en algún momento hay que
# soportar las dos versiones de AS a la vez (base y 1.4). Por
# ahora no hace falta resolver eso -- alcanza con una sola versión
# de AS confirmada, igual que ya pasa con Omega Ruby.
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
_BOX_BASE_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C9A144,
    PROCESS_NAME_OMEGA_RUBY: 0x08C9E134,
}

BOX_BASE_ADDRESS = _BOX_BASE_ADDRESS_BY_PROCESS[
    PROCESS_NAME_ALPHA_SAPPHIRE
]
BOX_SLOT_STRIDE = 0xE8
BOX_SLOT_COUNT = 30


def get_box_base_address(process_name):
    """Idem get_party_order_address(), para BOX_BASE_ADDRESS.

    Multi-version (30/08/2026): CONFIRMADO que BOX_BASE_ADDRESS NO es
    la misma entre Alpha Sapphire y Omega Ruby -- mismo patron ya
    visto con PARTY_ORDER_ADDRESS, no se puede asumir que coincide.

    Investigacion en Omega Ruby: escaneo por checksum PK6 alrededor
    de la PARTY_ORDER_ADDRESS de Omega Ruby
    (tools/probes/party/buscar_caja_pc_or.py) encontro un candidato
    aislado en 0x08C9E134 (sin vecinos con checksum valido -- patron
    esperado de una caja con un solo Pokemon adentro, a diferencia de
    otro cluster encontrado en la misma corrida que resulto ser
    ruido: un buffer distinto que mezclaba el equipo actual con la
    captura reciente, no la Caja PC real).

    BOX_SLOT_STRIDE confirmado IGUAL a Alpha Sapphire (0xE8) con una
    prueba en vivo (tools/probes/party/observar_caja_pc_or.py): al
    depositar un segundo Pokemon real en la caja, aparecio exactamente
    en BOX_BASE_ADDRESS + 0xE8, descartando el otro stride candidato
    (0x104, del cluster ruidoso).
    """

    return _BOX_BASE_ADDRESS_BY_PROCESS.get(
        process_name,
        _BOX_BASE_ADDRESS_BY_PROCESS[
            PROCESS_NAME_ALPHA_SAPPHIRE
        ],
    )


# Cantidad de cajas que DexRelay lee/muestra realmente.
#
# El juego (ORAS) soporta hasta 31 cajas de 30 slots cada una como
# maximo teorico, pero solo trae 7 habilitadas de fabrica -- las
# demas hay que comprarlas con dinero del juego. DECISION DE
# ALCANCE (09/09/2026, a pedido del usuario): DexRelay se queda en
# 7, no en 31. Motivo: en un Nuzlocke las capturas estan limitadas
# (un intento por encuentro/zona), asi que en la practica un run
# real nunca necesita mas de las 7 cajas de fabrica -- soportar
# hasta 31 hubiera sido complejidad sin uso real detras.
#
# Esto tambien resuelve de raiz las dos incertidumbres que habia
# quedado abiertas en el cierre de Fase C sobre el caso de las 31
# cajas (tamaño de la lectura UDP unica y direcciones 8-31 sin
# confirmar): como la app ya no pide ni muestra mas alla de la
# Caja 7, ninguna de las dos aplica mas.
#
# CONFIRMADO EMPIRICAMENTE (09/09/2026,
# tools/probes/party/confirmar_cajas_pc_rango.py, resultado
# reportado por el usuario): las Cajas 3, 5 y 7 aparecieron en la
# direccion contigua calculada al depositar un Pokemon real en cada
# una -- se suma a la Caja 2 ya confirmada el 06/09/2026. Con esto,
# TODO el rango 1-7 que la app realmente usa esta confirmado en
# vivo, no es extrapolacion. Cajas 8-31 (fuera del alcance elegido)
# quedan sin confirmar y sin necesidad de confirmarlas.
BOX_COUNT = 7

# Tamaño en bytes de una caja completa (30 slots * 232 bytes cada
# uno) -- usado para calcular donde empieza cada caja siguiente,
# asumiendo que son contiguas (ver get_box_address() mas abajo).
BOX_BLOCK_SIZE = BOX_SLOT_COUNT * BOX_SLOT_STRIDE


def get_box_address(process_name, box_index):
    """Direccion base de la caja `box_index` (1 = Caja 1, 2 = Caja
    2, etc.), para el `process_name` dado.

    CONFIRMADO EMPIRICAMENTE (06/09/2026,
    tools/probes/party/observar_cajas_pc_contiguas.py) que la Caja 2
    vive exactamente en BOX_BASE_ADDRESS + BOX_BLOCK_SIZE, sin
    padding entre cajas -- mismo patron que ya se habia confirmado
    para los SLOTS dentro de la Caja 1 (sin padding entre ellos,
    BOX_SLOT_STRIDE == SLOT_DATA_SIZE exacto). La confirmacion real:
    con un Mudkip apodado "Daron" depositado a mano en la Caja 2
    real del usuario, aparecio exactamente en esa direccion
    calculada -- mismo nivel de confirmacion (un salto real,
    Pokemon reconocible) que el que ya se acepto en su momento para
    validar BOX_SLOT_STRIDE dentro de la Caja 1.

    CONFIRMADO (09/09/2026, tools/probes/party/
    confirmar_cajas_pc_rango.py): Cajas 3, 5 y 7 tambien viven en la
    direccion contigua calculada, mismo patron que la Caja 2. Con
    esto, TODO el rango 1-7 -- el unico que BOX_COUNT expone hoy,
    ver su definicion mas arriba -- esta confirmado en vivo, no es
    extrapolacion. Mas alla de la Caja 7 (fuera del alcance elegido
    para la app) la formula sigue sin probarse, pero no hace falta:
    BOX_COUNT ya no deja pedir esos indices.

    `box_index` es 1-based (Caja 1 = box_index 1), para que coincida
    con la numeracion que ve el usuario en el juego.
    """

    base = get_box_base_address(process_name)

    return base + (box_index - 1) * BOX_BLOCK_SIZE


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
# Multi-version (30/08/2026): CONFIRMADO que CURRENT_ZONE_ID_ADDRESS
# de Alpha Sapphire NO sirve en Omega Ruby -- se detecto porque la
# deteccion automatica de "perdido" estaba registrando encuentros
# fantasma en una ruta placeholder "Zona 0" (zone_id=0, el valor
# que da leer la direccion de AS en la memoria de Omega Ruby).
#
# Encontrada con tools/probes/memory/rastrear_zona_actual_or.py
# (mismo algoritmo de estabilidad+consistencia que ya encontro la
# de Alpha Sapphire), ancla "badges" (BADGES_ADDRESS, compartida
# entre versiones). Validacion cruzada mas fuerte que un segundo
# escaneo comun: los valores encontrados para Ruta116 (43) y
# CiudadFerrica (16) coinciden EXACTO con los ya documentados para
# esos mismos lugares en Alpha Sapphire -- confirma que las dos
# versiones comparten el mismo esquema de IDs de zona. El candidato
# tambien aparecio en pareja separada por 0xE2 bytes, igual que la
# relacion ya confirmada entre CURRENT_ZONE_ID_ADDRESS y su espejo
# en Alpha Sapphire (0x08C6A894 - 0x08C6A7B2 == 0xE2).
_CURRENT_ZONE_ID_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6A7B2,
    PROCESS_NAME_OMEGA_RUBY: 0x08C6E7A2,
}
_CURRENT_ZONE_ID_MIRROR_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6A894,
    PROCESS_NAME_OMEGA_RUBY: 0x08C6E884,
}

CURRENT_ZONE_ID_ADDRESS = _CURRENT_ZONE_ID_ADDRESS_BY_PROCESS[
    PROCESS_NAME_ALPHA_SAPPHIRE
]
CURRENT_ZONE_ID_MIRROR_ADDRESS = (
    _CURRENT_ZONE_ID_MIRROR_ADDRESS_BY_PROCESS[
        PROCESS_NAME_ALPHA_SAPPHIRE
    ]
)


def get_current_zone_id_address(process_name):
    """Idem get_party_order_address(), para CURRENT_ZONE_ID_ADDRESS."""

    return _CURRENT_ZONE_ID_ADDRESS_BY_PROCESS.get(
        process_name,
        _CURRENT_ZONE_ID_ADDRESS_BY_PROCESS[
            PROCESS_NAME_ALPHA_SAPPHIRE
        ],
    )


# ============================================================
# BOLSA DE ITEMS (escritura de memoria -- Caramelo Raro y otros)
# ============================================================

# Confirmado empíricamente el 07/09/2026 (ver
# tools/probes/memory/buscar_bolsa_items.py y
# confirmar_bolsa_items.py, documentado en el Documento Maestro de
# esa sesión): en memoria viva la bolsa es UN SOLO array de
# casilleros de 4 bytes (u16 item_id LE + u16 cantidad LE), con
# TODOS los items de TODOS los bolsillos mezclados sin ningún orden
# por categoría -- la separación por bolsillo (Objetos/MTs/Bayas/
# etc) pasa solo al mostrarla en el juego, filtrando por rango de
# item_id, no en cómo se guarda en RAM.
#
# Candidatos validados EN VIVO por el usuario (cambio real
# reproducido en el juego, no solo "forma plausible"):
#   - Alpha Sapphire: item_id=2 (Ultra Ball) en 0x08C6AC84 bajó de
#     23 a 22 al tirar una.
#   - Omega Ruby: item_id=4 (Poké Ball) en 0x08C6EC70 bajó de 4 a 3
#     al tirar una.
#
# Multi-version (07/09/2026, mismo patrón ya visto con
# PARTY_ORDER_ADDRESS/BOX_BASE_ADDRESS/CURRENT_ZONE_ID_ADDRESS): la
# dirección NO coincide entre versiones -- pero a diferencia de esas
# otras direcciones, acá el desplazamiento entre AS y OR resultó ser
# una constante EXACTA (0x3FF0) tanto para el inicio como para el
# final del tramo confirmado por auto-detección
# (confirmar_bolsa_items.py: 740 casilleros / 2960 bytes en las DOS
# versiones, mismo tamaño exacto) -- fuerte señal de que es
# literalmente la misma estructura, corrida en memoria por ese
# offset fijo.
_BAG_START_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6AC80,
    PROCESS_NAME_OMEGA_RUBY: 0x08C6EC70,
}
_BAG_END_ADDRESS_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6B810,
    PROCESS_NAME_OMEGA_RUBY: 0x08C6F800,
}

BAG_START_ADDRESS = _BAG_START_ADDRESS_BY_PROCESS[
    PROCESS_NAME_ALPHA_SAPPHIRE
]
BAG_END_ADDRESS = _BAG_END_ADDRESS_BY_PROCESS[
    PROCESS_NAME_ALPHA_SAPPHIRE
]
BAG_SLOT_SIZE = 4

# Stack máximo real de un item en ORAS.
BAG_MAX_QUANTITY = 999

# Confirmado contra la tabla oficial de índices de Bulbapedia
# ("List of items by index number in Generation VI", la misma tabla
# de índices que usa ORAS) -- no es un valor supuesto de memoria.
RARE_CANDY_ITEM_ID = 50


def get_bag_start_address(process_name):
    """Idem get_party_order_address(), para BAG_START_ADDRESS."""

    return _BAG_START_ADDRESS_BY_PROCESS.get(
        process_name,
        _BAG_START_ADDRESS_BY_PROCESS[PROCESS_NAME_ALPHA_SAPPHIRE],
    )


def get_bag_end_address(process_name):
    """Idem get_party_order_address(), para BAG_END_ADDRESS."""

    return _BAG_END_ADDRESS_BY_PROCESS.get(
        process_name,
        _BAG_END_ADDRESS_BY_PROCESS[PROCESS_NAME_ALPHA_SAPPHIRE],
    )


# ============================================================
# BOLSILLO DE MEDICINA (Caramelo Raro pertenece aca)
# ============================================================

# CONFIRMADO (07/09/2026): al agregar Caramelo Raro en CUALQUIER
# casillero vacio del tramo grande de la bolsa (BAG_START/END), el
# juego lo mostraba en el bolsillo "Objetos" en vez de "Medicina" --
# y por estar en el bolsillo equivocado, usarlo no descontaba la
# cantidad (el menu de Objetos no tiene la logica de "usar sobre un
# Pokemon"). Esto reviso la hipotesis anterior de "una sola lista
# unificada sin separacion real": en realidad SI hay bolsillos
# separados (bloques contiguos de capacidad fija, uno detras del
# otro sin relleno, mismo patron de contiguidad ya visto en Cajas
# PC/orden de party) -- la posicion importa.
#
# Confirmado que Rare Candy/Caramelo Raro pertenece al bolsillo de
# Medicina en esta generacion contra la categoria oficial de
# Bulbapedia ("Category:Medicine_Pocket", que lista Rare Candy
# explicitamente junto a Revive/Zinc/Potion/etc) -- no es una
# suposicion de DexRelay, es la clasificacion real del juego.
#
# Anclaje validado EN VIVO (Alpha Sapphire): item_id=28 (Revivir) en
# 0x08C6B5F0 bajo de 6 a 5 al tirar uno. El dump alrededor mostro el
# bolsillo completo arrancando ahi mismo (racha de (0,0) justo antes,
# 5 items reales seguidos: Revivir/Zinc/Carbos/Cura Paralisis/Eter,
# racha de (0,0) despues).
#
# Omega Ruby: direccion calculada sumando el offset constante
# 0x3FF0 ya confirmado entre versiones para el inicio/fin del tramo
# completo de la bolsa (mismo desplazamiento exacto medido con
# BAG_START_ADDRESS y BAG_END_ADDRESS) -- inicialmente una
# prediccion, CONFIRMADA en vivo el mismo dia: el usuario agrego
# Caramelo Raro con esta direccion contra un save real de Omega
# Ruby y el juego lo mostro y conto correctamente dentro del
# bolsillo de Medicina (a diferencia del bug original, que lo
# mandaba a "Objetos").
_MEDICINE_POCKET_START_BY_PROCESS = {
    PROCESS_NAME_ALPHA_SAPPHIRE: 0x08C6B5F0,
    PROCESS_NAME_OMEGA_RUBY: 0x08C6B5F0 + 0x3FF0,
}

# Cuantos casilleros escanear hacia adelante desde el inicio del
# bolsillo de Medicina al buscar lugar para un item nuevo. Generoso
# respecto a los 5 items reales que se vieron en el dump (deja
# margen para que el jugador tenga muchos mas items de Medicina sin
# que la busqueda se quede corta), pero acotado -- no tan grande
# como para arriesgarse a cruzar al bolsillo siguiente si Medicina
# estuviera cerca de su limite real (que todavia no se confirmo con
# precision, ver dump_pocket_medicina.py).
MEDICINE_POCKET_SCAN_SLOTS = 100


def get_medicine_pocket_start_address(process_name):
    """Idem get_party_order_address(), para el bolsillo de Medicina."""

    return _MEDICINE_POCKET_START_BY_PROCESS.get(
        process_name,
        _MEDICINE_POCKET_START_BY_PROCESS[PROCESS_NAME_ALPHA_SAPPHIRE],
    )
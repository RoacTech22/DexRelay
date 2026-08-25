# DexRelay — Documento Maestro
## Estado consolidado del proyecto

**Fecha:** 25 de agosto de 2026
**Versión de este documento:** consolidada — reconstruida a partir de las 7 versiones históricas (`MASTER`, `v1`-`v6`) más todo el trabajo de las sesiones recientes, porque se detectó pérdida real de información entre `v5` (1364 líneas) y `v6` (289 líneas). Este documento reincorpora lo perdido y es, de aquí en adelante, la referencia única.

---

## 1. Identidad, objetivo e historia del proyecto

**Nombre oficial:** DexRelay
**Nombre anterior:** PokeOverlay (el proyecto se renombró al convertirse en aplicación de escritorio completa, no solo un overlay)

**Objetivo:** aplicación de escritorio tipo PokeLink para acompañar streams de Pokémon ejecutados mediante Azahar — lectura realtime del juego, overlays para OBS, servidor HTTP local, medallas y un futuro Nuzlocke Tracker.

**Streamer.bot queda fuera del proyecto.** DexRelay debe realizar directamente sus funciones principales; Streamer.bot podría quedar solo para integraciones de streaming opcionales, nunca como motor de una función principal.

**Nota histórica importante:** en algún punto del desarrollo el proyecto pasó por una etapa de "recuperación/refactorización" — la infraestructura de lectura de memoria (comunicación con Azahar, descifrado PK6, lectura de party) se reconstruyó dentro de una arquitectura nueva y más limpia, en vez de seguir extendiendo el código monolítico original de PokeOverlay. Esa base reconstruida es la que existe hoy. No hace falta rehacerla ni entender el código viejo de PokeOverlay para continuar.

---

## 2. Visión final del proyecto

```text
                         DEXRELAY
                            │
              ┌─────────────┴─────────────┐
              │                           │
           AZAHAR                       GUI
              │                           │
              ▼                           │
        MEMORY READER                     │
              │                           │
              ▼                           │
        CORE / RUNTIME ◄──────────────────┘
              │
       ┌──────┼───────────┐
       ▼      ▼           ▼
     TEAM   BADGES     NUZLOCKE
       │      │           │
       └──────┼───────────┘
              ▼
          HTTP SERVER
              │
       ┌──────┼─────────┐
       ▼      ▼         ▼
      OBS    TRACKER   FUTUROS
```

Flujo objetivo:

```text
Azahar → Memory Reader → Core/Runtime → Services → Data → HTTP → Overlays → OBS
```

### Árbol de carpetas objetivo (aspiracional, no todo existe todavía)

```text
DexRelay/
├── README.md
├── requirements.txt
├── config.json
├── .gitignore
│
├── app/
│   ├── main.py
│   ├── gui/                    ← FASE 4, pendiente
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   └── styles/
│   ├── core/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── events.py
│   │   ├── runtime.py
│   │   └── state.py
│   ├── readers/
│   │   ├── azahar_reader.py
│   │   └── citra.py
│   ├── memory/
│   │   ├── memory_reader.py
│   │   ├── pointers.py
│   │   └── structures.py
│   ├── services/
│   │   ├── badges_service.py
│   │   ├── badges_storage.py
│   │   ├── combat_service.py
│   │   ├── species_resolver.py
│   │   ├── nuzlocke_service.py  ← FASE 5, pendiente
│   │   └── pkhex/
│   │       ├── __init__.py
│   │       └── bridge.py
│   └── server/
│       └── http_server.py
│
├── dotnet/
│   └── DexRelay.PKHeX/
│       ├── DexRelay.PKHeX.csproj
│       └── Program.cs
│
├── data/
│   ├── badges.json
│   └── nuzlocke.json           ← pendiente (Nuzlocke Tracker)
│
├── overlays/
│   ├── team/
│   ├── badges/
│   └── nuzlocke/               ← pendiente
│
├── assets/                     ← pendiente formalizar
│   ├── pokemon/
│   ├── badges/
│   ├── effects/
│   └── ui/
│
├── tools/
│   ├── pkhex_probe/
│   └── probes/
│       ├── party/
│       ├── badges/
│       ├── memory/
│       └── combat/
│
├── tests/
├── docs/
├── logs/                       ← pendiente
└── releases/                   ← pendiente
```

---

## 3. Principios de diseño

### Separación de responsabilidades

**La GUI no lee memoria. Los overlays no leen memoria. El Tracker no conoce detalles de Azahar.**

```text
Azahar → Reader → Core/Services → Data → HTTP/Overlay
```

Las funciones de memoria deben permanecer siempre separadas de presentación y transporte.

### Estado actual vs. historial

Estado actual (puede cambiar en cualquier momento, refleja el presente):
- party
- HP
- nivel
- especie
- medallas actuales

Historial (una vez registrado, no se borra):
- capturas
- muertes
- evoluciones
- encuentros
- rutas
- eventos

**Regla crítica para el futuro Nuzlocke Tracker:** una muerte registrada en el historial nunca debe desaparecer porque el Pokémon sea curado o revivido por algún medio del juego. Esto es distinto del `.nuzlocke-dead` visual que ya existe en el Team Overlay — ese es un estado *actual* basado en `HP <= 0` en tiempo real (aparece y desaparece según el HP real del Pokémon), no un registro histórico persistente. El overlay resuelve "¿se ve debilitado ahora mismo?"; el futuro Nuzlocke Tracker deberá resolver "¿alguna vez murió, aunque hoy esté sano?" — son dos preguntas distintas y no deben confundirse cuando se implemente el Tracker real.

### Reglas de integración de memoria (aprendidas por experiencia, con costo real)

1. No copiar prototipos completos al proyecto — reutilizar solo la lógica ya validada.
2. Validar siempre las direcciones de memoria en la instancia real de Azahar antes de confiar en ellas, aunque vengan de un proyecto de referencia o de otro juego/versión.
3. Mantener el lector de party (estable) separado de lectores especializados (badges, combate) — un bug en uno no debe poder romper el otro.
4. No asumir el formato de una estructura de memoria (p. ej. "seguro es un bitmask") sin comprobarlo empíricamente.
5. Antes de fijar un offset como constante en código de producción, confirmarlo con un probe dedicado en `tools/probes/`, y solo integrar después de una lectura repetible y estable.

---

## 4. Comunicación con Azahar

DexRelay utiliza la interfaz UDP nativa de Azahar/Citra para depuración de memoria.

```text
Host: 127.0.0.1
Puerto: 45987
```

El proceso de juego dentro de Azahar es:

```text
sango-2
```

`app/readers/citra.py` (`Citra`) implementa:
- `read_memory`
- `process_list`
- `set_process` / `get_process`

`app/memory/memory_reader.py` (`MemoryReader`) es una capa fina sobre `Citra` que expone `.read(address, size)`, usada por todos los lectores especializados (party, badges, combate).

**Resuelto (24/08/2026):** el nombre de proceso ya no está hardcodeado. `AzaharReader` acepta `process_name` en el constructor (default `"sango-2"` para no romper probes/tests existentes que lo instancian sin argumentos), `find_game_process()` compara contra `self.process_name`, y `Application` (`app/core/app.py`) lee `config.get("azahar", "process_name")` y se lo pasa al construir el reader.

---

## 5. Memoria — Party realtime

**Estado: 🟢 funcional y validado.**

### Constantes confirmadas (`app/memory/pointers.py`)

```python
PARTY_ORDER_ADDRESS = 0x08CF71F0   # tabla de orden de la party (6 punteros de 4 bytes)
ORDER_ENTRY_SIZE = 4

POKEMON_POINTER_OFFSET = 0x40      # el puntero de la tabla apunta 0x40 bytes ANTES
                                    # de la estructura real del Pokémon
SLOT_DATA_SIZE = 232               # tamaño de la estructura PK6 principal
BLOCK_SIZE = 56                    # tamaño de cada uno de los 4 bloques del descifrado

STAT_DATA_OFFSET = 112             # offset de datos adicionales respecto al final del slot
STAT_DATA_SIZE = 22                # bytes de datos adicionales leídos
```

`read_party_order()` lee la tabla de 24 bytes (6 × 4) y devuelve los 6 punteros crudos. Importante (aprendido durante la investigación de combate): esta tabla es de **orden**, no de identidad fija — si reordenas el equipo en el juego, la dirección real de cada Pokémon puede aparecer bajo un slot distinto la próxima vez que se lea.

### Descifrado PK6 (`app/memory/structures.py`)

`decrypt_data()` implementa el algoritmo de cifrado XOR+LCG de la estructura PK6 (semilla `pv`, valor de shuffle `sv`, 4 bloques de 56 bytes reordenados según tabla `block_position`).

**Validación de checksum — agregada tras un bug real (24/08/2026).** El formato PK6 guarda un checksum en la cabecera (bytes `0x06-0x07`, sin cifrar): la suma de 16 bits de los 4 bloques recién descifrados, en su orden físico original (antes de `shuffle_array`). Hasta antes de este fix, esa validación no existía: una lectura de memoria "torn" (a mitad de una escritura del juego — típicamente al evolucionar o reordenar la party) se descifraba "con éxito" pero producía basura — `speciesId` aleatorio (evoluciones fantasma en el overlay) y `nickname` aleatorio (que al decodificarse como texto UTF-16LE caía a menudo en caracteres CJK, un artefacto clásico de este tipo de corrupción). Ahora se calcula y verifica el checksum; si no coincide, `raw_data` queda vacío y `azahar_reader.read_pokemon()` lo trata como `READ_FAILED`, reutilizando el último dato válido conocido del slot en vez de mostrar basura. Verificado con un roundtrip sintético (cifrar/descifrar con checksum correcto se acepta; con un byte corrupto se rechaza).

`Pokemon6` expone: `species_id()`, `nickname()`, `level()`, `hp()`, `max_hp()`. Offsets dentro de `raw_data` (post-descifrado): `speciesId` en `0x08-0x0A`, `nickname` en `0x40-0x58` (UTF-16LE), `level` en `0xEC`, `hp` en `0xF0-0xF2`, `maxHp` en `0xF2-0xF4`.

### `AzaharReader` (`app/readers/azahar_reader.py`)

Obtiene: `slot`, `especie`, `speciesId`, `nickname`, `nivel`, `hp`, `maxHp`.

Flujo:

```text
Azahar → Citra → MemoryReader → AzaharReader → Pokemon6 → datos normalizados
```

Salida normalizada por slot:

```json
{
  "slot": 1,
  "empty": false,
  "nickname": "Ejemplo",
  "species": "Pokemon",
  "speciesId": 123,
  "level": 20,
  "hp": 50,
  "maxHp": 60
}
```

**Manejo de lecturas fallidas:** `ReadFailure`/`READ_FAILED` distingue un slot genuinamente vacío (`pointer == 0`) de una lectura de memoria que falló de forma transitoria (paquete UDP perdido, checksum inválido). `_last_known_party` guarda el último dato válido por slot y se reutiliza en caso de falla transitoria, para que un Pokémon no "desaparezca" del overlay por una sola lectura perdida.

### Ejemplo real de validación (partida real del usuario, referencia histórica)

```text
Slot 1: Hugo    — nivel 10 — 35/35 HP
Slot 2: Conter  — nivel 6  — 0/20 HP
Slot 3: Daron   — nivel 12 — 25/37 HP
Slot 4: Carlos  — nivel 11 — 36/36 HP
Slot 5: Rin     — nivel 10 — 29/29 HP
Slot 6: vacío
```

---

## 6. Especies — SpeciesResolver + Bridge PKHeX

**Estado: 🟢 completado.**

`app/services/species_resolver.py` transforma `speciesId → species`. Usa datos estáticos opcionales, una caché de resultados, y `PKHeXBridge` como fuente automática en runtime.

### Bridge PKHeX (`dotnet/DexRelay.PKHeX/`)

```text
.NET 10
PKHeX.Core 26.7.7
```

Proceso .NET independiente (`Program.cs`), recibe JSON por stdin, soporta `action: "species"`:

```json
{ "action": "species", "id": 269 }
```
→
```json
{ "id": 269, "name": "Beautifly" }
```

`app/services/pkhex/bridge.py` (`PKHeXBridge`): inicia el proceso, mantiene stdin/stdout, envía/recibe JSON, detecta errores, reinicia el proceso cuando corresponde, se detiene correctamente. Herramientas de validación en `tools/pkhex_probe/` y `tools/probes/pkhex_bridge_probe.py`.

**Acciones adicionales del bridge (25/08/2026):** `met_location`, `species_list`, `location_list` — agregadas para automatizar el Bloque C del Nuzlocke Tracker. Detalle completo en la sección 14.

**Pendiente de fase final:** publicar el bridge como ejecutable self-contained (no `dotnet run`) para el empaquetado de distribución (FASE 6).

---

## 7. Medallas

**Estado: 🟢 memoria validada, servicio implementado, overlay implementado.**

### Investigación de memoria (historial completo)

Se probaron primero direcciones históricas de proyectos externos de referencia (`PokeReader`, `Gen6CTRPFrameworkOverhauled`), que **no funcionaron** en la instancia real de Azahar:

```text
0x08C71DB8 → 00...00
0x08C71DC4 → 00
0x08CFB26C → 00...00
```

La dirección que sí funciona vino del prototipo `pokemon-overlay`:

```text
0x08C6DDD4
```

Validado con una partida de 3 medallas (`0x07` = `00000111`, bits 0-2 activos) y confirmado al obtener la 4ª medalla (`0x0F` = `00001111`, bits 0-3 activos).

**Conclusión metodológica (aplicada luego también a combate):** no copiar direcciones históricas de proyectos externos sin validarlas en la instancia real — sirven como referencia de estructura, no como verdad absoluta.

```text
PokeReader / Gen6CTRPFrameworkOverhauled → referencia histórica
        ↓
pokemon-overlay → candidato 0x08C6DDD4
        ↓
prueba real en Azahar → CONFIRMADO
```

### Formato confirmado

```text
Dirección: 0x08C6DDD4
Tamaño:    1 byte
Formato:   bitfield
```

```text
bit 0 → Roxanne / Stone Badge
bit 1 → Brawly / Knuckle Badge
bit 2 → Wattson / Dynamo Badge
bit 3 → Flannery / Heat Badge
bit 4 → Norman / Balance Badge
bit 5 → Winona / Feather Badge
bit 6 → Tate & Liza / Mind Badge
bit 7 → Wallace-Juan / Rain Badge
```

Confirmada estable across reinicios del emulador.

### Implementación

- `app/services/badges_service.py` — lee `0x08C6DDD4` (1 byte), interpreta bits, expone `{value, count, badges: [bool x8]}`.
- `app/services/badges_storage.py` + `data/badges.json` — persistencia.
- Integrado en `Runtime` y `ApplicationState`.
- `/api/badges` en el HTTP server.
- Probes históricos de badges se conservan en `tools/probes/` (documentan por qué se descartaron las direcciones antiguas — no eliminar).

### Badges Overlay (`overlays/badges/`, agregado 23/08/2026)

Sirve en `/overlay/badges`. 8 medallas en fila usando imágenes reales del usuario (`sprites/1.png`...`8.png`, mismo orden que arriba). Mismo patrón anti-bug que Team Overlay: slots creados una sola vez, polling de `/api/badges` cada 200ms solo cambia clases, nunca reconstruye el DOM.

- No obtenida: imagen clara/desaturada (`brightness` + `grayscale`), sin aro.
- Obtenida: sin aro ni fondo, solo resplandor en capas (glow blanco pegado a la forma + halo cálido más difuso) simulando que está iluminada. Animación de "pop" al momento exacto de obtenerla.

---

## 8. Combate — HP en tiempo real

**Estado: 🟢 integrado en backend y en el Team Overlay, con una limitación conocida (slot fijo).**

### Descubrimiento original (prototipo `pokemon-overlay (8).zip`)

El HP de combate no usa dirección fija — el juego reubica la estructura de combate en cada batalla. El prototipo usaba un puntero fijo + offset dinámico:

```text
Puntero fijo ORAS: 0x083F8658
Offset hasta HP:   0x404
```

```text
base_combate = leer_u32(0x083F8658)
si base_combate == 0: no hay combate activo
hp = leer_u16(base_combate + 0x404)
```

Con validación de consistencia antes/después (leer puntero → leer HP → releer puntero → si cambió, descartar la lectura) para evitar HP incoherente si la estructura de combate se destruye/recicla justo durante la lectura. El prototipo documentaba un segundo puntero espejo `0x083F8654`, pero la implementación validada usa `0x083F8658 + 0x404`.

### Implementación actual (`app/services/combat_service.py`)

```python
COMBAT_POINTER_ADDRESS = 0x083F8658
COMBAT_HP_OFFSET = 0x404
```

**Bug real encontrado y corregido (22-23/08/2026): el puntero de combate no vuelve a `0x00000000` al salir de combate.** Se queda en un valor fijo y estable, `COMBAT_POINTER_ADDRESS - 4` (`0x083F8654` — resulta que es exactamente el "puntero espejo" que el prototipo original ya había anotado, sin llegar a explicar por qué), memoria reutilizada por el juego, no una estructura de batalla real. Confirmado empíricamente con `tools/probes/combat/observar_puntero_combate.py` (dos salidas de combate distintas, mismo valor exacto ambas veces). Antes de este fix, `CombatService` lo trataba como puntero válido y devolvía el último HP visto (ej. `3`) indefinidamente después de salir de combate — ese valor se colaba en la barra del overlay.

```python
COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4  # == 0x083F8654
# ambos (0 y este valor) significan "sin combate"
```

`LECTURA_DESCARTADA` es el sentinel para una lectura inconsistente (puntero cambió a mitad de lectura) — se descarta, se conserva el último estado de combate válido.

### `ApplicationState` y `/api/combat`

`combat_active` (booleano) y `combat_hp` en el estado. Otro bug corregido en el mismo bloque: `runtime.py` no distinguía bien los 3 resultados posibles de `CombatService.read()` (HP válido / `None` sin combate / `LECTURA_DESCARTADA`); una lectura descartada se colaba como si fuera HP válido, rompiendo el JSON. Ahora los tres casos se manejan por separado.

```json
{ "active": true, "hp": 3 }
```
fuera de combate:
```json
{ "active": false, "hp": null }
```

### Team Overlay — barra de HP animada

`app.js` consulta `/api/team` y `/api/combat` en el mismo ciclo de 200ms. Mientras `combat.active` es `true`, el slot en combate usa el HP de `/api/combat` en vez del de `/api/team` para calcular la barra, logrando la animación de bajada progresiva (`31 → 24 → 18 → 3`) en vez de un salto directo, aprovechando la transición CSS `width 0.4s ease` que ya existía. Fuera de combate, `/api/team` vuelve a ser la fuente. El HP de combate nunca sobreescribe el `hp` permanente de la party — solo afecta el cálculo visual de la barra.

### Limitación conocida: slot fijo

El overlay asume que el Pokémon en combate es siempre el del **slot 1**. Se investigó extensamente cómo detectar el slot real y **ninguna hipótesis dio resultado**:

1. **`speciesId` como valor plano dentro de la estructura de combate** (`buscar_offset_slot_combate.py`): un speciesId chico (15) apareció en 2 offsets por coincidencia numérica; otro (92) no apareció en ningún offset. Descartado.
2. **Puntero de vuelta hacia la dirección real del Pokémon en la party** (`buscar_puntero_slot_combate.py`): se calculó la dirección real de cada uno de los 6 miembros (`PARTY_ORDER_ADDRESS + POKEMON_POINTER_OFFSET`) y se buscó como entero de 4 bytes dentro de la estructura de combate, ventana `0x600` y luego `-0x800/+0x2000`. Sin coincidencias.
3. **Escaneo diferencial alrededor de `COMBAT_POINTER_ADDRESS`** (`rastrear_slot_activo.py`): al ser una dirección fija/global (a diferencia de `base_address`, dinámica), se buscó un byte fijo cercano cuyo valor siguiera el índice de slot (0-5), con secuencias de 4 slots distintos, ventanas de `0x8000` y luego `0x100000` (1MB) a cada lado. Cero coincidencias en ambos casos.
4. **Hipótesis del reordenamiento de la party** (que el juego pusiera al Pokémon activo en slot 1 internamente durante combate, como en algunos títulos): descartada, confirmado por el usuario que `/api/team` no cambia de orden ni durante ni después del combate.
5. **Cheat Engine conectado directamente al proceso de Azahar:** se hizo el puente de traducción entre direcciones "del juego" y las que ve Cheat Engine en el proceso host, y se corrió "Unknown initial value → Exact Value narrowing" cambiando de Pokémon activo varias veces. Se redujo de ~64 millones de resultados a 1 candidato — **falso positivo** (el valor seguía cambiando sin relación real con el slot activo).
6. **HP máximo de combate como "huella"** (`probar_maxhp_combate.py`): se probó la hipótesis de que el maxHp estuviera en `COMBAT_HP_OFFSET + 2` (mismo patrón que `Pokemon6`: hp en `0xF0`, maxHp en `0xF2`), para comparar contra el `maxHp` de cada slot de `/api/team`. Descartada: no coincidió.

**Manifestación observada:** al cambiar manualmente a un Pokémon activo que no es el slot 1 durante un combate, el overlay le aplica el HP de combate (de ese otro Pokémon) a lo que sea que `/api/team` reporte como slot 1 — puede mostrar, por ejemplo, la barra de un Pokémon sano en 0 si el que realmente está peleando está debilitado. No es un bug de implementación nuevo, es el costo directo de la simplificación de slot fijo.

**Decisión:** se mantiene slot 1 fijo. Es una limitación conocida y documentada, no bloquea el resto del proyecto. Para retomarlo en el futuro, lo más prometedor sería un debugger real conectado al código ARM emulado (no solo al proceso host de Windows ni al protocolo UDP de Azahar) — ambos enfoques usados hasta ahora llegaron a su límite práctico sin esa visibilidad.

**Override desactivado temporalmente en el overlay (24/08/2026).** Reportado: la limitación de arriba estaba afectando visualizaciones que ya funcionaban bien (barra de un Pokémon sano mostrando 0 por aplicarle el HP de otro Pokémon en combate). Se comentó (no se borró) en `overlays/team/app.js`: el fetch de `COMBAT_API_URL`, `COMBAT_SLOT_INDEX`, y el bloque de cálculo de `hp`/`inCombat` en `renderSlot()`. La barra vuelve a usar siempre `/api/team` (igual que fuera de combate). El backend (`combat_service.py`, `/api/combat`) sigue intacto y funcionando — no afecta nada visualmente por sí solo, y facilita reactivar todo esto de un solo commit cuando se resuelva la detección real del slot.

---

## 9. Muertes / debilitamiento

Hay **dos sistemas distintos** relacionados con "muerte" en el proyecto. Ya no son independientes — desde el 24/08/2026 el overlay consume el resultado del segundo, pero conceptualmente siguen siendo dos cosas distintas:

### 9.1. Nuzlocke Tracker (`data/nuzlocke.json`) — 🟢 implementado (Bloque A, sección 14)

Registro **permanente**: `Pokémon se debilita → pasa al graveyard → aunque se cure después, no vuelve al roster`. Portado desde la lógica validada del prototipo (PokeOverlay) a `app/services/nuzlocke_service.py`. Expuesto en `/api/nuzlocke`.

### 9.2. Animación/estado visual de "debilitado" en el Team Overlay — 🟢 implementado, con muerte persistente (24/08/2026)

`overlays/team/app.js` calcula `isDead = pokemon.hp <= 0 || nickname en graveyard de /api/nuzlocke`. El chequeo de HP dispara la animación en el instante exacto (el backend tarda hasta un ciclo de 200ms en registrar la muerte); el chequeo del cementerio mantiene la apariencia de muerto para siempre, sin importar el HP después — corrigiendo la regresión respecto al comportamiento original de PokeOverlay, donde la muerte visual sí era persistente. Todo el slot (nickname, nivel, barra de HP), no solo el sprite, se atenúa en gris cuando `isDead` es `true` (clase `dead` en el `<div class="slot">`). Ver sección 12 y sección 14 para el detalle completo.

---

## 10. HTTP Server

**Estado: 🟢 funcional.**

```text
http://localhost:8080
```

Rutas activas:
- `/api/status` → `{azahar_connected, reader_active}`
- `/api/team` → party actual
- `/api/badges` → `{value, count, badges}`
- `/api/combat` → `{active, hp}` (implementado; ver sección 8 sobre el override del overlay desactivado)
- `/api/nuzlocke` → `{roster, graveyard}`
- `/overlay/team`, `/overlay/team/*` → sirve `overlays/team/`
- `/overlay/badges`, `/overlay/badges/*` → sirve `overlays/badges/`
- `/overlay/nuzlocke`, `/overlay/nuzlocke/*` → sirve `overlays/nuzlocke/`

**Bug del overlay — RESUELTO.** Los slots 5 y 6 se alternaban por agotamiento del pool de conexiones del navegador. Solución vigente (no revertir):
- HTTP/1.1 + keep-alive (`protocol_version = "HTTP/1.1"`)
- `request_queue_size = 32`
- Los 6 slots del overlay se crean una sola vez (no en cada ciclo)
- No reconstruir sprites/DOM innecesariamente cada 200ms
- Reintentos de carga de sprites (`loadSpriteWithRetry`)
- Polling cada 200ms sin query string variable

**Bug de CSS/JS sin cargar — RESUELTO (24/08/2026).** Al entrar a `/overlay/{nombre}` **sin barra final**, el navegador resolvía los `<link>`/`<script>` relativos (`style.css`, `app.js`) contra el directorio padre (`/overlay/`) en vez de `/overlay/{nombre}/`, dando 404 silencioso en ambos. Fix: las 3 rutas de overlay (antes casi duplicadas) se unificaron en `_serve_overlay(overlay_name)`, que redirige (301) a la versión con `/` al final cuando falta, sirve `index.html` con la barra, y sirve archivos estáticos con el prefijo completo. Verificado end-to-end contra el servidor real para los 3 overlays.

**Desconexiones de cliente silenciadas (24/08/2026).** `ConnectionAbortedError`/`ConnectionResetError`/`BrokenPipeError` son tráfico normal de keep-alive cuando el navegador (u OBS) cierra/recarga una conexión a medio camino — no bugs. `handle_error()` es un método del **servidor** (`socketserver.BaseServer`), no del request handler; `_QuietThreadingHTTPServer` (subclase de `ThreadingHTTPServer`) lo sobreescribe para filtrar solo esos 3 errores esperados, dejando pasar cualquier otro al reporte normal.

La GUI futura (FASE 4) deberá poder iniciar/detener este servidor y mostrar/copiar las URLs para OBS.

---

## 11. Runtime

`app/core/runtime.py` ejecuta el ciclo realtime cada ~200ms (`config.json` → `realtime.refresh_ms`):

1. conexión/reconexión con Azahar
2. lectura de party
3. actualización de estado
4. lectura de medallas
5. persistencia de medallas
6. lectura de HP de combate (con el manejo correcto de los 3 casos: válido / sin combate / descartado — ver sección 8)

---

## 12. Team Overlay

**Estado: 🟢 funcional, con las animaciones de evolución/muerte/entrada corregidas.**

Ubicación: `overlays/team/` (`index.html`, `style.css`, `app.js`, `sprites/`)

URL: `http://localhost:8080/overlay/team`

### Diseño

- fondo transparente, sin `frame.png`
- separación 32px, slots 145px, sprites 140px
- nickname en fuente Teko, azul con borde blanco
- nivel debajo
- barra HP 105×7px, verde/amarillo/rojo según porcentaje, efecto de HP crítico (`criticalPulse`)
- soporte visual shiny y Pokémon debilitado (`.nuzlocke-dead`)
- animaciones de entrada, evolución, subida de nivel, y muerte

### HP de combate animado

Ver sección 8 — el slot en combate usa `/api/combat` para la barra en vez de `/api/team`.

### Bugs de animación encontrados y corregidos (24/08/2026)

Se compararon contra la lógica de referencia del proyecto anterior (`PokeOverlay`, específicamente `view/team_realtime_fixed.html`) y se encontraron tres problemas reales:

1. **Detección de evolución sin chequeo de nickname.** Solo comparaba `speciesId`, así que reordenar el equipo y que otro Pokémon (con especie distinta) ocupara un slot se confundía con una evolución. Corregido: ahora requiere `nickname` igual + `speciesId` distinto, igual que la referencia.

2. **Animación de muerte inexistente.** No había ninguna detección de `HP <= 0` en `app.js`; la clase `.nuzlocke-dead` ya existía en el CSS pero nunca se aplicaba, y no había keyframe de transición a muerto. Además, debilitarse no cambia `nickname` ni `speciesId`, así que `needsRebuild` nunca se activaba para ese caso — ni siquiera había gancho para dispararla. Agregado: `isDead`/`wasDead`/`died` basados en `pokemon.hp` (el HP real de la party, **no** el HP en vivo de combate — la muerte es un estado de la party, no algo que dependa de una pelea sin sincronizar), fuerza reconstrucción del slot al morir, dispara `sprite-wrapper-death` (keyframe `pokemonDeath`, agregado a `style.css`), y `.nuzlocke-dead` se mantiene aplicada mientras el Pokémon siga debilitado (se revisa en cada ciclo, no solo en el instante de la muerte).

3. **Animación de "entrada" solo se disparaba con slot vacío.** La condición era `!previous` — pero al reordenar el equipo, un Pokémon distinto puede ocupar un slot que ya tenía otro Pokémon (`previous` no es `null`). Se agregó el caso `changed` (mismo slot, `nickname` distinto) para que también dispare la entrada, igual que el flag `pokemonChanged` de la referencia.

**Nota importante:** las evoluciones/muertes "fantasma" que se veían de forma intermitente (junto con nicknames mostrando caracteres CJK) **no eran un bug de esta lógica de animación** — eran el síntoma del bug de checksum PK6 (sección 5): datos de memoria corruptos llegando como si fueran válidos. Ambos bugs se corrigieron en la misma sesión pero son causas independientes.

---

## 13. Badges Overlay

Ver sección 7.

**Nuzlocke Overlay** (`overlays/nuzlocke/`, cementerio + estadísticas): ver sección 14, Bloque B.

---

## 14. Nuzlocke Tracker

**Estado: 🟢 Bloques A, B y C completos** (con automatización de ruta real, no solo carga manual — mucho más de lo que se había planeado originalmente para el Bloque C). No confundir la muerte persistente de esta sección con la detección visual del overlay (sección 9) — están integradas entre sí (ver más abajo) pero conceptualmente siguen siendo dos cosas distintas.

- **Bloque A — Núcleo** (🟢 completo): captura automática, evolución sin duplicar registro, muerte persistente, `/api/nuzlocke`.
- **Bloque B — Overlay** (🟢 completo): cementerio visual + estadísticas.
- **Bloque C — Encuentros por ruta** (🟢 completo, con automatización real vía PKHeX, no solo el panel manual planeado originalmente).

### Bloque A — Núcleo (`app/services/nuzlocke_service.py` + `nuzlocke_storage.py`)

Portado directamente desde la lógica ya validada en el prototipo (`PokeOverlay/scripts/azahar_reader_nuzlocke_realtime.py`), adaptado a la arquitectura de servicios actual.

**Identidad:** solo `nickname`. Acá la identidad tiene que ser estable a través de **toda la partida**, incluyendo evoluciones — una evolución actualiza el registro existente, no crea uno nuevo.

**Regla clave:** una vez que un `nickname` aparece en `graveyard`, nunca vuelve a `roster` aunque el HP actual sea > 0 — la muerte es historial permanente.

El disco es la fuente de verdad: `NuzlockeService` carga una sola vez y cachea en memoria, escribiendo a disco solo cuando algo cambia. Integrado en `Runtime.update()`, expuesto en `/api/nuzlocke`.

### Bloque B — Overlay del cementerio (`overlays/nuzlocke/`)

Sirve en `/overlay/nuzlocke`. Barra de estadísticas + grilla del cementerio, reutilizando sprites del Team Overlay vía ruta relativa.

### Muerte visual persistente en el Team Overlay

`overlays/team/app.js` consulta `/api/nuzlocke` y arma un `Set` de nicknames en `graveyard`. `isDead` es `true` si `hp <= 0` **o** si el nickname ya está en el cementerio (mantiene la apariencia para siempre, sin importar el HP después). Todo el slot (nickname, nivel, barra de HP) se atenúa, no solo el sprite.

### Bloque C — Encuentros por ruta (COMPLETO, 24-25/08/2026)

**Automatización completa vía PKHeX** — mucho más ambicioso que el plan original (que era solo un panel de carga manual). Se descubrió que el formato PK6 guarda el lugar de encuentro real dentro del propio Pokémon (`Met_Location`), y que ya se capturan completos y sin huecos los 232 bytes donde vive ese campo (los mismos que usan `species_id()`/`nickname()`/etc. en `structures.py`) — no hizo falta investigar memoria nueva.

**Extensión del bridge PKHeX** (`dotnet/DexRelay.PKHeX/Program.cs`), 3 acciones nuevas, todas verificadas contra documentación oficial de PKHeX (no adivinadas):

- `met_location`: recibe los 232 bytes ya descifrados de un Pokémon, construye un `PK6`, devuelve `metLocationName` (vía `pk.MetLocation` + `GameInfo.GetLocationName(...)`) y `shiny` (`pk.IsShiny` — de paso se conectó un campo que **nunca había estado conectado** en el backend, a pesar de que el CSS/JS del Team Overlay ya tenían el estilo shiny listo).
- `species_list`: lista completa `{id, name}` de especies, para el buscador del panel.
- `location_list`: lista completa `{id, name}` de ubicaciones, vía `GameInfo.GetLocationList(GameVersion.AS, EntityContext.Gen6, egg: false)` — la misma fuente que `met_location` usa para una captura real, **a propósito**, para que los nombres coincidan siempre.

**Servicios Python nuevos:**
- `app/services/location_resolver.py`: resuelve `metLocation` + `shiny`, cacheado por `nickname` (el lugar de encuentro de un Pokémon puntual no cambia nunca — evita golpear el bridge en cada ciclo de 200ms).
- `app/services/species_catalog.py` / `app/services/location_catalog.py`: listas completas cacheadas en memoria y disco (`data/species_cache.json` / `data/location_cache.json`). **Importante:** se cachea el dato **crudo** de PKHeX, y el filtro/orden/traducción se aplican siempre frescos al leer — si se cacheara el resultado ya procesado, cualquier mejora futura al filtro quedaría "atrapada" en el caché viejo (pasó una vez con la traducción al español, corregido).
- `app/services/hoenn_locations_es.py`: tabla de traducción español (España) verificada contra fuentes confiables (WikiDex, PokéWiki Fandom) el 25/08/2026 — **77 de 93 ubicaciones confirmadas**, las ~16 restantes (zonas post-juego/DexNav poco comunes: cuevas y ruinas secundarias) quedan en inglés a propósito por no poder confirmarlas con una fuente confiable. **Se aplica en dos lugares a la vez** (`LocationCatalog` y `LocationResolver`), obligatoriamente — si solo se tradujera uno de los dos, el nombre mostrado no coincidiría con el que reporta una captura real y reaparecería el bug de duplicados.

**Filtro y orden de ubicaciones** (`location_catalog.py`): confirmado con datos reales que **todas** las ubicaciones de Hoenn (ORAS) caen entre el ID 170 y el 354, sin excepciones — fuera de ese rango queda Kalos completo (IDs 2-168), eventos/torneos (40000+), transferencias entre juegos (30000+) y regalos especiales (60000+). Se ordena además por progresión narrativa aproximada (`_STORY_ORDER_IDS`), no por el orden crudo de PKHeX.

**`nuzlocke_service.py` — modelo de datos final:**
```json
{
  "roster": [...], "graveyard": [...],
  "encounters": [
    { "location": "...", "nickname": "...", "species": "...", "status": "...", "updatedAt": "ISO 8601" }
  ],
  "pending_encounters": [
    { "nickname": "...", "speciesId": ..., "species": "...", "shiny": bool, "caughtAt": "ISO 8601" }
  ],
  "starter_assigned": bool
}
```

`status` (antes `result`) admite: `sin_intentar`, `capturado`, `perdido`, `muerto`, `intercambiado`, `regalo`, `shiny`.

**Lógica de `_register_new_capture()` (orden de decisión):**
1. **Primer Pokémon de toda la partida** → se registra como `"Inicial"` **sin importar** lo que diga `metLocation` (regalo del inicial no reporta ruta real). `starter_assigned=True`. **"Inicial" nunca se puede resetear**, ni siquiera si ese Pokémon murió después — `delete_encounter()` lo rechaza explícitamente (ValueError / 404 vía HTTP), y el botón de reseteo del panel ni se renderiza para esa fila.
2. **Regla de especie repetida (species clause):** si ya hay otro Pokémon de la **misma especie vivo** en el roster, la captura no cuenta — no se registra en `encounters` ni en `pending_encounters`. Sigue existiendo en `roster` con normalidad (Bloque A no cambia). En cuanto el primero de esa especie muere, una captura nueva de esa especie vuelve a contar normal.
3. **Con `metLocation` resuelto:** se registra directo en `encounters` — **pero solo si esa ubicación todavía no tiene un encuentro registrado**. Si ya hay uno, no se pisa (protección contra sobrescritura) — cae a `pending_encounters` para revisión manual.
4. **Sin `metLocation`** (huevo, regalo, intercambio, bridge caído): cae a `pending_encounters` como siempre.

**Sync automático con el cementerio:** cuando un Pokémon muere (Bloque A), cualquier `encounter` con su mismo `nickname` pasa a `status="muerto"` automáticamente.

**Endpoints nuevos** (`http_server.py`):
- `GET /api/species`, `GET /api/locations`
- `GET /api/nuzlocke/pending-encounters`
- `POST /api/nuzlocke/encounters` (manual, ahora con `nickname`+`status`)
- `POST /api/nuzlocke/encounters/assign` (asignar ruta a una captura pendiente)
- `POST /api/nuzlocke/encounters/delete` (botón de reseteo por ruta — borra el encuentro **y** el Pokémon del roster/graveyard; rechaza `"Inicial"`)
- `POST /api/nuzlocke/pending-encounters/discard` (botón "Descartar" — saca de pendientes sin registrar, el Pokémon sigue en roster)
- `POST /api/nuzlocke/reset` (botón "Reiniciar Nuzlocke Tracker", provisional — borra roster/graveyard/encounters/pending/starter_assigned de un solo golpe, doble confirmación en el panel)

**Panel** (`panels/nuzlocke/`, servido en `/panel/nuzlocke` — no es un overlay para OBS, es una página de control para el usuario, mismo patrón `_serve_static_page` que los overlays):
- Sección "Capturas sin ruta asignada" (solo aparecen los casos que PKHeX no pudo resolver solo), con botones **Asignar** y **Descartar**, refresco automático cada 3s.
- Tabla de rutas (Ruta / Nickname / Especie / Estado) precargada desde `/api/locations`, con botón de reseteo (✕) por fila (oculto en "Inicial").
- Buscador de especie propio (`createSpeciesPicker`, reemplaza `<datalist>` nativo por poco confiable entre navegadores) con sprite al lado, reutilizando `/overlay/team/sprites/{id}.png` — no hizo falta ninguna carpeta ni sprite nuevo para esto.
- Guard: solo se guarda un encuentro cuando `nickname` **y** `species` tienen contenido (antes, cualquier click en un input vacío creaba un registro fantasma).
- `NuzlockeService` es una **instancia compartida única** entre `Runtime` y `HTTPServer` (antes cada uno tenía la suya) — el panel necesita escribir sobre los mismos datos que el resto del sistema lee.

**Bugs encontrados y corregidos en el camino:**
- El campo `shiny` nunca había estado conectado en el backend (arreglado de paso, gratis con la misma llamada a PKHeX).
- `refreshEncounters()` disparaba la animación de "guardado" en cada refresh automático aunque nada hubiera cambiado (parpadeo azul constante) — ahora solo resalta si algo cambió de verdad.
- Caché en disco de `LocationCatalog` servía datos ya procesados (viejos, en inglés, de antes de la traducción) para siempre — corregido cacheando el dato crudo y aplicando filtro/traducción siempre frescos.

### Pendiente / mejoras futuras

- ~16 ubicaciones post-juego/DexNav siguen en inglés (no se pudo confirmar una traducción confiable) — completar cuando se identifiquen con certeza.
- Ronald mencionó (25/08/2026) que sigue teniendo cosas para mejorar en el Tracker, sin especificar cuáles todavía — retomar en la próxima sesión.
- Reglas configurables del run (dupes clause completa, etc.) en un futuro campo `run.ruleset`.
- Exportar resumen del run al terminar.
- Notificaciones tipo "toast" en el overlay ante eventos importantes (captura, muerte) — aprovechando el futuro bus de eventos (sección 16).
- Leer la caja (PC) completa, no solo el equipo activo, para que el roster incluya todo lo capturado — requiere investigar la dirección del box.

---

## 15. GUI (futuro)

**Estado: 🔴 pendiente.**

```text
AZAHAR
● Detectado / Conectado
[ INICIAR LECTOR ] [ DETENER LECTOR ]

HTTP SERVER
● Activo — Puerto: 8080
[ INICIAR SERVIDOR ] [ DETENER SERVIDOR ]

OVERLAYS
Team       [ URL ] [ COPIAR ]
Badges     [ URL ] [ COPIAR ]
Nuzlocke   [ URL ] [ COPIAR ]

NUZLOCKE
Capturados: XX   Muertos: XX   Medallas: X/8
[ ABRIR TRACKER ]
```

---

## 16. Sistema de eventos (futuro)

**Estado: 🟡 nombres definidos, bus no implementado.**

`app/core/events.py` ya define los nombres de eventos previstos:

```python
GameConnected
GameDisconnected
PokemonChanged
PokemonEvolved
PokemonFainted
BadgeObtained
TeamUpdated
```

Pero no hay todavía un bus/dispatcher que los emita o los consuma — es solo una clase de constantes. Se incorporará el bus completo cuando la cantidad de módulos lo justifique (por ejemplo, cuando la GUI, el Tracker y los overlays necesiten reaccionar a los mismos eventos sin acoplarse directamente entre sí).

---

## 17. Configuración

`config.json`:

```json
{
  "azahar": {
    "process_name": "sango-2"
  },
  "server": {
    "host": "localhost",
    "port": 8080
  },
  "realtime": {
    "refresh_ms": 200
  }
}
```

`app/core/config.py` (`Config`) ya sabe leer esto (`.get(*keys, default=...)`). **Resuelto (24/08/2026):** `Application` ya lee `config.get("azahar", "process_name")` y lo pasa a `AzaharReader` (ver sección 4). Evitar rutas absolutas y configuraciones duplicadas en múltiples módulos.

---

## 18. Concurrencia — RESUELTO (24/08/2026)

**Modelo elegido: threads, no asyncio.**

Motivo:
- `HTTPServer` ya corría en su propio `Thread` (`ThreadingHTTPServer`) — era continuar un patrón existente, no introducir uno nuevo.
- Las GUI de escritorio en Python (Tkinter, PyQt/PySide) esperan correr su propio mainloop bloqueante en el **hilo principal**. Con threads, eso encaja naturalmente: la GUI ocupará el hilo principal cuando exista (FASE 4), y el loop realtime + el HTTP server siguen en hilos de fondo leyendo/escribiendo el mismo `ApplicationState`.
- Asyncio hubiera significado reescribir `citra.py` (UDP) y el HTTP server (vía `aiohttp` u otro) para un beneficio de escala que este proyecto no necesita — un puñado de overlays locales, no miles de conexiones concurrentes.

**Implementación:** `Application.run()` ya no ejecuta el loop realtime directamente en el hilo principal. `start()` lanza un `Thread` daemon (`_runtime_thread`) que corre `_run_realtime_loop()` (mismo pacing por `time.monotonic()` que antes). `run()` pasó a ser un simple bucle de espera (`time.sleep(0.25)`) que mantiene vivo el proceso mientras los hilos de fondo trabajan — el hilo principal queda libre para el mainloop de la GUI. `stop()` hace `join()` del hilo realtime (timeout 2s) además de detener el HTTP server, para un apagado limpio.

Verificado con un test de ciclo de vida completo sobre la clase `Application` real (`Config`/`Runtime` reemplazados por fakes, sin necesitar Azahar real): el hilo corre separado del principal, `update()` se llama periódicamente según `refresh_ms`, y `stop()` termina el hilo limpiamente sin updates fantasma después.

**Nota de thread-safety:** `ApplicationState` ahora se escribe desde el hilo del `Runtime` y se lee desde el hilo del `HTTPServer` concurrentemente — la misma categoría de concurrencia que ya existía antes (antes era hilo principal vs. hilo de `HTTPServer`, ahora es hilo de `Runtime` vs. hilo de `HTTPServer`). No se agregó ningún lock explícito: las asignaciones simples de atributos en Python son atómicas a nivel del GIL, y el peor caso posible es leer un frame de estado ligeramente desactualizado (un overlay mostrando el ciclo anterior por 200ms), no una corrupción de datos. Si en el futuro `ApplicationState` crece a estructuras más complejas con actualizaciones multi-paso, revisar si conviene agregar un `threading.Lock`.

---

## 19. Git / Versionado

GitHub es el sistema principal de versiones. `backups/` no es (ni debe ser) el sistema principal de versionado.

Ramas previstas: `main`, `feature/badges`, `feature/http-server`, `feature/gui`, `feature/nuzlocke-tracker`.
Tags previstos: `v0.1.0`, `v0.2.0`, ... `v1.0.0`.

### Historial de commits (de más reciente a más antiguo)

```text
26e452a Boton provisional para reiniciar todo el Nuzlocke Tracker
8ea0871 Corregir cache de ubicaciones desactualizado (mostraba nombres viejos en ingles)
d8129f2 Traducir nombres de ubicaciones de Hoenn al español (España), verificado
a3c4935 Filtrar y ordenar /api/locations por rango de Hoenn y progresion de historia
2a41a41 Inicial permanente, regla de especie repetida, boton Descartar en pendientes
c887af4 Lista de rutas desde PKHeX (fix de raiz de duplicados), boton de reseteo, guard de campos vacios
1cf4401 Corregir bugs del panel: Inicial, duplicados, parpadeo, buscador con sprite
0a53b02 Panel: columna de nickname, buscador de especies y estados ampliados
a418267 Backend: deteccion automatica de ruta via PKHeX, nickname, estado ampliado
4a03722 Agregar probe para investigar la zona actual en memoria
aaeddd5 Automatizar captura de encuentros: especie y resultado se detectan solos
b9f0a4c Nuzlocke Tracker (Bloque C): panel de encuentros por ruta (carga manual)
5a02152 Actualizar Documento Maestro: cierre de sesion (Nuzlocke Tracker, fixes HTTP, muerte persistente)
49227cb Aplicar el gris de 'muerto' a todo el slot (nickname, nivel, barra de HP)
991324b Muerte visual persistente en el overlay + desactivar HP de combate temporalmente
9e1fdcc Corregir CSS/JS que no cargaban por falta de redirect a barra final
d0db13f Nuzlocke Tracker (Bloque B): overlay del cementerio + estadisticas
8d69dee Nuzlocke Tracker (Bloque A): captura automatica y muerte persistente
cf6746b Sincronizar ajustes visuales manuales del usuario (team/badges) y sprites de medallas
12ab6e1 Silenciar tracebacks de desconexiones esperadas del cliente (keep-alive)
3634a5d Marcar decision de concurrencia como resuelta en el Documento Maestro
579525a Mover el loop realtime a su propio hilo (decision de concurrencia: threads)
8747683 Marcar fix de process_name como resuelto en el Documento Maestro
3f0a0ff Leer process_name desde config.json en vez de hardcodearlo
5f9f7f7 Documentar logica reutilizable de muerte persistente del prototipo (Nuzlocke)
aca7dc8 Reconstruir Documento Maestro consolidado a partir de las 7 versiones historicas
05238cd Actualizar Documento Maestro (bugs de animaciones + checksum PK6)
7ebac26 Corregir lecturas corruptas de party (checksum PK6) y animacion de entrada al reordenar
01ed424 Corregir animaciones de evolucion y agregar animacion de muerte faltante
774a325 Actualizar Documento Maestro (HP de combate + Badges Overlay)
a07a408 Añadir Badges Overlay y probes de investigacion de slot activo en combate
91ca1a2 Corregir deteccion de fin de combate (puntero no vuelve a 0)
5ceffdc Integrar HP de combate en la barra del Team Overlay
54568eb Añadir Team Overlay (HTML/CSS/JS) y servirlo desde el HTTP server
563a84b Integrar lectura de HP de combate realtime
2a58363 Añadir API de equipo e integrar especies con PKHeX
78c1a31 Mejorar reconexion de Azahar y API de estado
eee35c7 Añadir API HTTP de medallas
4b2e125 Persistir estado de medallas
4902ed9 Implementar loop realtime de DexRelay
11cd0d9 Integrar lectura realtime de medallas
fdcf875 Integrar base realtime y validación de medallas
7a7efa4 Mejorar estabilidad del bridge de PKHeX
5737c7a Conectar Python con bridge de PKHeX
9e8c19f Crear bridge de PKHeX
```

*(Nota: algunas versiones antiguas de este documento mencionan además `1be5256 Crear lector de party de Azahar`, `d6b78c3 Integrar resolución de especies`, `fb931a2 Validar integración de PKHeX moderno` como commits intermedios de esa etapa; no aparecen en el log más reciente revisado, posiblemente por squash/rebase en algún punto. No es motivo de alarma, pero si en algún momento el historial de git no coincide con esta lista, confiar en `git log` real, no en este documento.)*

**Ajustes visuales manuales sincronizados (24/08/2026):** el usuario ajustó a mano, sobre el proyecto local, tres valores de estilo que ya quedaron incorporados aquí:
- `overlays/team/style.css`: separación entre slots `gap: 32px → 54px`.
- `overlays/badges/style.css`: separación entre medallas `gap: 14px → 30px`; `.badge.pending` sin borde (`border: none`, antes `3px solid`); `opacity: 0.55 → 0.8`.
- `overlays/badges/sprites/` ya tiene las 8 imágenes reales del usuario (antes solo se documentaba dónde debían ir).

Siempre que el usuario suba una copia del proyecto, comparar contra este repo antes de asumir que coinciden — este documento se actualiza cuando se detectan diferencias reales, pero puede haber una ventana corta sin sincronizar.

---

## 20. Herramientas / Probes

`tools/probes/` — separados del código principal a propósito (regla de diseño, no accidente).

```text
tools/probes/
├── party/       — probes de lectura de party
├── badges/      — incluye los históricos de direcciones descartadas (0x08C71DC4, 0x08C71DB8...);
│                  NO eliminar, documentan por qué se descartaron
├── memory/
└── combat/
    ├── observar_puntero_combate.py       — observa COMBAT_POINTER_ADDRESS en vivo
    ├── buscar_offset_slot_combate.py     — intento fallido: speciesId como valor plano
    ├── buscar_puntero_slot_combate.py    — intento fallido: puntero de vuelta a la party
    ├── rastrear_slot_activo.py           — intento fallido: escaneo diferencial de índice de slot
    └── probar_maxhp_combate.py           — intento fallido: maxHp como huella
```

`tools/pkhex_probe/` — herramienta de prueba del bridge PKHeX.

### Validación usada

```bash
python -m compileall app
git diff --check
```

---

## 21. Roadmap

### FASE 1 — BASE REALTIME
**✅ COMPLETADA**

- [x] Comunicación con Azahar
- [x] Lectura realtime de party (con checksum PK6)
- [x] `AzaharReader`
- [x] Overlay del equipo + animaciones (entrada, evolución, muerte, subida de nivel)
- [x] HP de combate realtime integrado en overlay
- [ ] Detección del slot real en combate (pausada sin resultado — sección 8)
- [ ] Detección persistente de muertes tipo Nuzlocke (la del prototipo, no la visual — sección 9.1, todavía no reimplementada en la arquitectura actual)
- [x] Mover `process_name` a `config.json` (sección 4/17)
- [x] Decidir modelo de concurrencia (threads) e implementarlo (sección 18)

### FASE 2 — MEDALLAS
**✅ COMPLETADA**

- [x] Probe de memoria, localización y validación de dirección
- [x] `badges_service.py` + `badges_storage.py` + `badges.json`
- [x] Integración realtime en `Runtime`/`ApplicationState`
- [x] `/api/badges`
- [x] Badge overlay

### FASE 3 — SERVIDOR HTTP
**✅ MAYORMENTE COMPLETADA**

- [x] HTTP server propio (hilo separado, keep-alive, `request_queue_size`)
- [x] `/api/status`, `/api/team`, `/api/badges`, `/api/combat`
- [x] Rutas `/overlay/team`, `/overlay/badges`
- [ ] `/api/nuzlocke`, `/overlay/nuzlocke` (esperando FASE 5)
- [ ] URLs copiables desde GUI (esperando FASE 4)

### FASE 4 — GUI
**🔴 PENDIENTE**

- [ ] Ventana principal, estado de Azahar, control del reader/runtime/servidor
- [ ] URLs copiables, estado de servicios, logs, configuración

### FASE 5 — NUZLOCKE TRACKER
**🟢 MAYORMENTE COMPLETA — Bloques A, B y C completos**

- [x] Base de datos (JSON — `data/nuzlocke.json`)
- [x] Capturas automáticas, muertes persistentes, evoluciones (sección 14, Bloque A)
- [x] Overlay del Tracker (cementerio + estadísticas, sección 14, Bloque B)
- [x] Encuentros por ruta/zona — detección automática vía PKHeX (`met_location`), no solo carga manual (sección 14, Bloque C)
- [x] Panel de control (`panels/nuzlocke/`): asignar/descartar pendientes, resetear por ruta, resetear todo
- [ ] ~16 ubicaciones post-juego sin traducir al español (confirmar cuando se identifiquen)
- [ ] Partidas (multi-run), gestión manual desde GUI

### FASE 6 — APLICACIÓN
**🔴 PENDIENTE**

- [ ] Empaquetado, `DexRelay.exe`, configuración portable, instalador, iconos, documentación, pruebas
- [ ] Publicar el bridge PKHeX como self-contained (no `dotnet run`)

### FASE 7 — RELEASE
**🔴 PENDIENTE**

Objetivo: `DexRelay v1.0` con lector, overlays, servidor, GUI, medallas, Tracker, configuración, logs y versionado.

---

## 22. Reglas de desarrollo

1. No romper funciones comprobadas como estables.
2. Antes de cambios críticos, crear commit estable.
3. Mantener probes separados del código principal.
4. No mezclar memoria con presentación.
5. Separar estado actual de historial (sección 3).
6. Streamer.bot no forma parte del motor de DexRelay.
7. No implementar arquitectura compleja antes de necesitarla.
8. Usar Git/GitHub como fuente principal de versiones.
9. Actualizar este documento ante cambios importantes.
10. Marcar una función como COMPLETADA solo después de probarla.
11. No copiar directamente prototipos completos al proyecto — reutilizar solo la lógica validada.
12. Validar siempre las direcciones/estructuras de memoria en la instancia real de Azahar, nunca confiar ciegamente en proyectos de referencia externos.
13. Mantener el lector de party separado de lectores especializados (badges, combate).
14. Antes de fijar un offset como constante de producción, confirmarlo con un probe dedicado (workflow: escanear → confirmar → recién ahí fijar).
15. Cuando una lectura de memoria pueda ser "torn" (a mitad de escritura del juego), preferir un mecanismo de validación del propio formato (checksum, consistencia de puntero antes/después) en vez de confiar en que "si descifró, es válido".

---

## 23. Preferencias de trabajo

### Históricas (etapa ChatGPT, documentadas en versiones anteriores — contexto, no vinculantes hoy)

El usuario históricamente pidió: respuestas concisas, instrucciones directas, pasos concretos, código completo siempre que hubiera que modificar/crear un archivo, no preguntar innecesariamente qué paso hacer, no hacer commits sin indicación explícita.

### Vigentes en esta conversación (Claude) — estas mandan sobre las de arriba cuando hay conflicto

- **Código por archivo, no proyecto completo:** para cada cambio, dar el código completo del/los archivo(s) tocados, listo para copiar y pegar. Nada de zip del proyecto completo en cada paso.
- **Zip completo solo al cerrar un bloque importante** (a criterio de Claude), siempre acompañado de la actualización de este Documento Maestro.
- Preguntar cuando una decisión técnica sea genuinamente ambigua y el costo de adivinar mal sea alto (por ejemplo, cómo identificar el slot activo en combate) — no simplemente para evitar tomar una decisión razonable.
- Confirmar antes de hacer commits/cambios (esto se ha mantenido: cada commit en esta sesión se hizo después de que el usuario confirmara que un cambio funcionaba).

---

## 24. Estado actual (resumen)

```text
COMUNICACIÓN CON AZAHAR      🟢 FUNCIONAL
PARTY REALTIME                🟢 FUNCIONAL (con checksum PK6)
SPECIES ID / RESOLVER         🟢 FUNCIONAL (PKHeX integrado)
PKHEX BRIDGE                  🟢 VALIDADO (falta self-contained para release)
MUERTES — VISUAL (OVERLAY)    🟢 FUNCIONAL (persistente, integrada con el Tracker)
MUERTES — TRACKER PERSISTENTE 🟢 FUNCIONAL (Bloque A del Nuzlocke Tracker, sección 14)
MEDALLAS — MEMORIA            🟢 VALIDADO
MEDALLAS — SERVICIO/API       🟢 FUNCIONAL
BADGES OVERLAY                🟢 FUNCIONAL
NUZLOCKE TRACKER — NÚCLEO     🟢 FUNCIONAL (captura/evolución/muerte automáticas)
NUZLOCKE OVERLAY               🟢 FUNCIONAL (cementerio + estadísticas)
NUZLOCKE — ENCUENTROS/RUTA     🟢 FUNCIONAL (automático vía PKHeX, no solo carga manual)
NUZLOCKE — PANEL DE CONTROL    🟢 FUNCIONAL (/panel/nuzlocke: asignar, descartar, resetear)
HP DE COMBATE — BACKEND       🟢 FUNCIONAL (sigue corriendo, no afecta overlay)
HP DE COMBATE — OVERLAY       🟡 DESACTIVADO TEMPORALMENTE (comentado en app.js, no borrado)
DETECCIÓN DE SLOT EN COMBATE  🔴 PAUSADA, SIN RESULTADO
TEAM OVERLAY — ANIMACIONES    🟢 FUNCIONAL (evolución/muerte/entrada corregidas)
HTTP SERVER                   🟢 FUNCIONAL (bug de rutas sin barra final corregido)
RUNTIME LOOP                  🟢 FUNCIONAL (en su propio hilo)
CONFIG — process_name         🟢 RESUELTO (lee config.json)
CONCURRENCIA (asyncio/threads) 🟢 RESUELTO (threads; loop realtime en su propio hilo)
SISTEMA DE EVENTOS             🟡 NOMBRES DEFINIDOS, BUS NO IMPLEMENTADO
GUI                            🔴 PENDIENTE
EMPAQUETADO                    🔴 PENDIENTE
```

---

## 25. Continuidad entre conversaciones

Este documento es el hilo maestro de DexRelay.

Si se pierde contexto:
1. Proporcionar este documento.
2. Revisar sección 24 (Estado actual) y sección 21 (Roadmap).
3. Continuar desde la fase actual — no rehacer funciones marcadas 🟢.
4. Mantener el nombre DexRelay y la arquitectura existente salvo razón técnica clara.
5. No asumir que las direcciones/offsets de memoria de este documento son universales — siempre son específicos de esta instancia de Azahar/ORAS y deben re-validarse si algo deja de coincidir.

El documento debe actualizarse cuando: se complete una fase, cambie la arquitectura, se tome una decisión técnica importante, se añada/elimine un módulo, o cambie el flujo principal de datos.

---

## 26. Historial de actualizaciones de este documento

- **2026-08-19:** primeras versiones (`MASTER`, `v1`-`v3`) — base realtime, investigación y validación de medallas.
- **2026-08-21:** `v4`/`v5` — HTTP server, PKHeX bridge integrado como fuente automática, badges persistente, roadmap corregido.
- **2026-08-22:** `v6` — versión fuertemente condensada (pérdida de detalle detectada posteriormente).
- **2026-08-23:** Team Overlay, HP de combate animado, fix del puntero de combate, Badges Overlay.
- **2026-08-24:** fix de checksum PK6 y de animación de entrada al reordenar; reconstrucción consolidada de este documento a partir de las 7 versiones históricas para recuperar contexto perdido; agregada referencia a la lógica de muerte persistente ya validada en el prototipo (`PokeOverlay/scripts/azahar_reader_nuzlocke_realtime.py`), pendiente de portar cuando se retome la FASE 5; `process_name` movido de código hardcodeado a `config.json`; decisión de concurrencia resuelta (threads) e implementada — loop realtime movido a su propio hilo; silenciados los tracebacks de desconexiones esperadas del cliente (keep-alive); sincronizados los ajustes visuales manuales del usuario en `overlays/team/style.css` y `overlays/badges/style.css` + sprites reales de medallas; **Nuzlocke Tracker Bloques A y B completos** (captura/evolución/muerte automáticas + overlay de cementerio y estadísticas, portado desde el prototipo); corregido bug de CSS/JS sin cargar por falta de redirect a barra final en las 3 rutas de overlay; muerte visual del Team Overlay ahora es persistente (integrada con el cementerio del Tracker) y se extiende a todo el slot (nickname, nivel, barra de HP), no solo al sprite; HP de combate en tiempo real desactivado temporalmente en el overlay (comentado, no borrado) por estar afectando visualizaciones ya funcionales mientras la detección real del slot sigue pendiente.
- **2026-08-25:** **Nuzlocke Tracker Bloque C completo**, con automatización real vía PKHeX (mucho más de lo planeado originalmente): descubierto que el formato PK6 guarda el lugar de encuentro real del Pokémon (`Met_Location`), extendido el bridge C# con 3 acciones nuevas (`met_location`, `species_list`, `location_list`) verificadas contra documentación oficial de PKHeX; panel de control nuevo (`panels/nuzlocke/`) con buscador de especies + sprite, capturas pendientes con Asignar/Descartar, reseteo por ruta, y botón de reinicio total del Tracker; campo `shiny` conectado al backend por primera vez (nunca lo había estado); "Inicial" siempre primero y permanente (no se puede resetear); regla de especie repetida (species clause); protección contra sobrescribir una ruta ya registrada; lista de rutas filtrada por rango de ID de Hoenn y ordenada por progresión de historia (en vez de una lista escrita a mano, que tenía errores reales); 77 de 93 ubicaciones traducidas al español verificadas contra fuentes confiables (WikiDex, PokéWiki), aplicada en los dos lugares a la vez (catálogo y resolución de capturas) para no reintroducir el bug de duplicados; corregido un bug de caché en disco que servía nombres viejos en inglés indefinidamente.

**Este archivo es la referencia maestra de continuidad del proyecto.**

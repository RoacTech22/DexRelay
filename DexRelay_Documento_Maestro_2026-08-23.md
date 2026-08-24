# DexRelay — Documento Maestro
## Estado consolidado del proyecto
**Fecha:** 23 de agosto de 2026 (actualizado — bloque: HP de combate en overlay + Badges Overlay)

## 1. Identidad y objetivo
**Nombre oficial:** DexRelay.

Aplicación de escritorio para acompañar streams de Pokémon ejecutados mediante Azahar, con lectura realtime del juego, overlays, servidor HTTP local, medallas y futuras funciones Nuzlocke.

**Streamer.bot queda fuera del proyecto.** DexRelay debe realizar directamente sus funciones principales.

## 2. Arquitectura actual
Azahar → Citra/Azahar reader → MemoryReader → servicios DexRelay → ApplicationState → HTTP Server → overlays/clientes web.

Especies:
Azahar → party → speciesId → SpeciesResolver → PKHeXBridge → PKHeX.Core → nombre.

Combate:
Azahar → memoria → CombatService → HP realtime → ApplicationState → /api/combat → Team Overlay.

## 3. Estado realtime de Azahar
DexRelay detecta `sango-2`, selecciona el proceso de juego, comprueba conexión y puede reconectarse después de una desconexión.

Estado:
- `azahar_connected`
- `reader_active`

También se corrigió el manejo de `ConnectionResetError` al cerrar Azahar.

## 4. Party realtime
La party proporciona:
- `slot`
- `empty`
- `nickname`
- `species`
- `speciesId`
- `level`
- `hp`
- `maxHp`

Ejemplo confirmado:
```json
{
  "slot": 1,
  "empty": false,
  "nickname": "Conter",
  "species": "Bunnelby",
  "speciesId": 659,
  "level": 11,
  "hp": 29,
  "maxHp": 29
}
```

## 5. Memoria
`app/memory/structures.py` contiene el descifrado y `Pokemon6`, incluyendo species ID, nickname, level, HP y max HP.

## 6. PKHeX
Bridge:
`dotnet/DexRelay.PKHeX/`

Cliente:
`app/services/pkhex/bridge.py`

PKHeX.Core:
`26.7.7`

Acción actual:
`species`

`SpeciesResolver` usa datos estáticos opcionales, caché y PKHeX como fuente dinámica.

## 7. API HTTP
Servidor:
`http://localhost:8080`

Endpoints:
- `/api/status`
- `/api/team`
- `/api/badges`
- `/api/combat`

`/api/status`:
```json
{
  "azahar_connected": true,
  "reader_active": true
}
```

`/api/team` devuelve la party actual.

`/api/badges` devuelve las medallas.

`/api/combat` expone (implementado y confirmado, ver secciones 9 y 14):
```json
{
  "active": true,
  "hp": 3
}
```
y fuera de combate:
```json
{
  "active": false,
  "hp": null
}
```

## 8. Medallas
Servicios:
- `app/services/badges_service.py`
- `app/services/badges_storage.py`
- `data/badges.json`

Ya existe lectura realtime, persistencia y API.

## 9. CombatService
`app/services/combat_service.py` está integrado en runtime, state y HTTP.

Pruebas confirmadas:
- fuera de combate: `{'active': False, 'hp': None}`
- combate: `{'active': True, 'hp': 31}`
- daño: `{'active': True, 'hp': 3}`

La lectura realtime de HP de combate ya funciona.

**Bug resuelto — puntero de combate no vuelve a 0 al salir de combate.**
`COMBAT_POINTER_ADDRESS` (`0x083F8658`) no vuelve a `0x00000000` cuando termina el combate: se queda en un valor fijo y estable, `COMBAT_POINTER_ADDRESS - 4` (`0x083F8654`), memoria reutilizada por el juego, no una estructura de batalla real. Confirmado empíricamente con `tools/probes/combat/observar_puntero_combate.py` (dos salidas de combate distintas, mismo valor exacto ambas veces). `CombatService` lo trataba como puntero válido y devolvía el último HP visto (ej. `3`) indefinidamente después de salir de combate, y ese valor se colaba en la barra del overlay.

Fix: `COMBAT_INACTIVE_POINTER = COMBAT_POINTER_ADDRESS - 4` se trata igual que `0` (sin combate).

También se corrigió que `runtime.py` no distinguía bien los 3 resultados posibles de `CombatService.read()` (HP válido / `None` sin combate / `LECTURA_DESCARTADA` por lectura inconsistente): antes, una lectura descartada se colaba como si fuera HP válido, rompiendo el JSON. Ahora los tres casos se manejan por separado y `ApplicationState` gana el campo `combat_active`.

## 10. ApplicationState
Contiene:
- `azahar_connected`
- `reader_active`
- `team`
- `badges`
- `combat_active` (agregado en este bloque)
- `combat_hp`

## 11. Runtime
`app/core/runtime.py` ejecuta el ciclo realtime aproximadamente cada 200 ms:
1. conexión/reconexión;
2. party;
3. estado;
4. medallas;
5. persistencia;
6. HP de combate.

## 12. Team Overlay
Ubicación:
`overlays/team/`

Estructura:
```text
overlays/team/
├── index.html
├── style.css
├── app.js
└── sprites/
```

URL:
`http://localhost:8080/overlay/team`

También:
`http://localhost:8080/overlay/team/index.html`

Diseño final definido por el usuario:
- fondo transparente;
- sin `frame.png`;
- solo el espacio necesario para el equipo;
- separación de 32 px;
- slots de 145 px;
- sprites de 140 px;
- nickname Teko, azul con borde blanco;
- nivel debajo;
- barra HP 105×7 px;
- verde/amarillo/rojo según porcentaje;
- efecto de HP crítico;
- soporte visual shiny y Pokémon muerto;
- animaciones de entrada, evolución y subida de nivel.

El CSS proporcionado por el usuario el 22/08/2026 es la referencia visual final.

**HP de combate ya integrado (ver sección 14 para el detalle completo).** `app.js` consulta `/api/team` y `/api/combat` en el mismo ciclo de 200ms; mientras `combat.active` es `true`, el slot 1 usa el HP de `/api/combat` para la barra en vez del de `/api/team`, logrando la animación de bajada progresiva (`31 → 24 → 18 → 3`) en vez de un salto directo.

## 12bis. Badges Overlay — COMPLETADO

Ubicación:
`overlays/badges/`

Estructura:
```text
overlays/badges/
├── index.html
├── style.css
├── app.js
└── sprites/          (1.png ... 8.png, provistas por el usuario)
```

URL:
`http://localhost:8080/overlay/badges`

Diseño:
- fondo transparente, sin `frame.png` (mismo criterio que Team Overlay);
- 8 medallas en fila, imagen real de cada una vía `sprites/{1-8}.png` (orden: 1 Roxanne/Stone, 2 Brawly/Knuckle, 3 Wattson/Dynamo, 4 Flannery/Heat, 5 Norman/Balance, 6 Winona/Feather, 7 Tate & Liza/Mind, 8 Wallace-Juan/Rain);
- no obtenida: imagen clara/desaturada (`brightness` + `grayscale`), sin aro sólido;
- obtenida: sin aro ni fondo, solo resplandor en capas (glow blanco pegado a la forma + halo cálido más difuso) simulando que está iluminada;
- animación de "pop" en el momento exacto que se obtiene una medalla nueva.

Mismo patrón anti-bug que Team Overlay: los 8 slots se crean una sola vez al cargar la página; el polling de `/api/badges` cada 200ms solo cambia clases/estado, nunca reconstruye el DOM.

Consume `/api/badges` (ver sección 8) tal cual ya estaba expuesto — no requirió cambios de backend más allá de las nuevas rutas de servido estático (`/overlay/badges`, `/overlay/badges/*`) en `http_server.py`.

## 13. Bug del overlay — RESUELTO
Los slots 5 y 6 se alternaban por agotamiento del pool de conexiones del navegador contra el servidor HTTP.

La solución actual del proyecto actualizado incluye:
- HTTP/1.1;
- keep-alive;
- `request_queue_size = 32`;
- seis slots creados una sola vez;
- no reconstruir innecesariamente los sprites cada 200 ms;
- reintentos de carga de sprites;
- polling de `/api/team` cada 200 ms sin query string.

**No revertir esta solución.**
No volver a reconstruir todo el DOM y los `<img>` en cada ciclo.

## 14. HP de combate en el overlay — COMPLETADO

Objetivo cumplido: la barra del Pokémon en combate usa el HP realtime de `/api/combat` y baja progresivamente (`31 → 24 → 18 → 3`), en vez de saltar directamente.

Arquitectura implementada:
```text
CombatService
    ↓
combat_active / combat_hp
    ↓
ApplicationState
    ↓
/api/combat  {"active": bool, "hp": int|null}
    ↓
Team Overlay (app.js consulta /api/team + /api/combat cada 200ms)
    ↓
barra HP animada (CSS transition: width 0.4s ease, ya existente)
```

Fuera de combate, `/api/team` sigue siendo la fuente normal de `hp/maxHp`. El HP de combate no se convierte en el HP permanente de la party: solo afecta el cálculo visual de la barra del slot en combate.

**Slot fijo (limitación conocida, decisión explícita del usuario):** el overlay asume que el Pokémon en combate es siempre el del **slot 1**. No hay todavía forma de detectar cuál slot real está peleando — ver sección 14bis para el detalle de la investigación (pausada, sin resultado).

Pruebas realizadas y confirmadas:
- entrar en combate — barra baja en pasos reales;
- recibir varios daños seguidos — pasos correctos;
- salir de combate — vuelve a `/api/team` sin quedarse pegada (bug corregido, ver sección 9);
- volver a entrar — funciona de nuevo;
- no reaparece el bug de conexiones de los slots 5/6.

## 14bis. Detección del Pokémon enviado a combate — PAUSADA, SIN RESULTADO

Se investigó extensamente cómo identificar, desde memoria, cuál de los 6 slots de la party es el que está peleando en un momento dado (para dejar de asumir slot 1 fijo). Ninguna hipótesis dio resultado hasta ahora:

1. **`speciesId` como valor plano dentro de la estructura de combate** (`tools/probes/combat/buscar_offset_slot_combate.py`): un speciesId chico (15) apareció en 2 offsets por pura coincidencia numérica; otro speciesId (92) no apareció en ningún offset. Descartado: la estructura no duplica el speciesId como número plano en esa zona.

2. **Puntero de vuelta hacia la dirección real del Pokémon en la party** (`tools/probes/combat/buscar_puntero_slot_combate.py`): se calculó la dirección real de cada uno de los 6 miembros de la party (`PARTY_ORDER_ADDRESS` + `POKEMON_POINTER_OFFSET`) y se buscó esa dirección como entero de 4 bytes dentro de la estructura de combate, primero en una ventana de `0x600` bytes, después ampliada a `-0x800/+0x2000` alrededor de `base_address`. Sin ninguna coincidencia en ningún caso. Descartado (al menos dentro de esas ventanas): la estructura de combate no guarda un puntero directo de vuelta a la party.

3. **Escaneo diferencial alrededor de `COMBAT_POINTER_ADDRESS`** (`tools/probes/combat/rastrear_slot_activo.py`): como `COMBAT_POINTER_ADDRESS` es una dirección fija/global (a diferencia de `base_address`, que es memoria dinámica del heap y cambia cada combate), se probó buscar un byte fijo cercano cuyo valor seguiera el índice del slot activo (0-5). Se probó con ventana de `0x8000` (antes/después) usando una secuencia de 4 slots distintos: cero coincidencias. Se amplió a `0x100000` (1MB) a cada lado (2MB total): también cero coincidencias.

4. **Hipótesis descartada: reordenamiento de la party.** Se consideró que el juego pudiera mover al Pokémon activo al slot 1 internamente durante el combate (como pasa en algunos títulos). Confirmado por el usuario que **no es así**: `/api/team` no cambia de orden ni durante ni después del combate.

5. **Cheat Engine conectado directamente al proceso de Azahar:** se hizo el puente de traducción entre direcciones "del juego" (las que usa `citra.py`) y las direcciones que ve Cheat Engine en el proceso host, y se corrió el flujo clásico "Unknown initial value → Exact Value narrowing" cambiando de Pokémon activo varias veces. Se redujo de ~64 millones de resultados a 1 candidato, pero resultó ser un **falso positivo**: el valor seguía cambiando sin relación real con el slot activo.

**Decisión:** se mantiene el slot 1 fijo como Pokémon "en combate" para la barra de HP del overlay. Es una limitación conocida y documentada, no bloquea el resto del proyecto. Para retomar esta investigación en el futuro, lo más prometedor sería un debugger real conectado al código ARM emulado (no solo al proceso host de Windows), ya que el enfoque de escaneo por valores desde Python (por UDP) y desde Cheat Engine (proceso host) llegó a su límite práctico sin esa visibilidad.

## 15. Configuración
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

## 16. Herramientas
`tools/probes/` contiene probes de memoria, party, badges, PKHeX bridge y species resolver.

`tools/probes/combat/` (nuevo en este bloque):
- `observar_puntero_combate.py` — observa en vivo `COMBAT_POINTER_ADDRESS`, usado para confirmar el bug del puntero que no vuelve a 0 (ver sección 9).
- `buscar_offset_slot_combate.py`, `buscar_puntero_slot_combate.py`, `rastrear_slot_activo.py` — probes de investigación de detección del slot activo en combate, sin resultado por ahora (ver sección 14bis). Se conservan para retomar la investigación más adelante.

`tools/pkhex_probe/` contiene la herramienta de prueba del bridge.

## 17. Validación
Se ha utilizado:
```bash
python -m compileall app
git diff --check
```

## 18. Historial relevante
```text
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

Nota: el usuario hizo ajustes visuales manuales adicionales sobre `overlays/badges/style.css` después del commit `a07a408` (afinando el brillo/resplandor). Verificar con `git status`/`git diff` antes de asumir que el estado local coincide exactamente con este documento.

## 19. Reglas de continuidad
No reintroducir:
- Streamer.bot;
- dependencias innecesarias del proyecto antiguo;
- `frame.png` como frame obligatorio;
- reconstrucción completa del overlay cada 200 ms;
- conexiones HTTP innecesarias;
- fuentes antiguas cuando DexRelay ya dispone del dato realtime.

## 20. Cuándo actualizar este documento
Actualizarlo después de bloques importantes: HP de combate integrado al overlay, eventos realtime, detección del Pokémon enviado a combate, GUI, Nuzlocke Tracker, sistema completo de overlays o distribución.

Si se inicia un chat nuevo o el contexto empieza a quedarse corto, avisar explícitamente al usuario y usar este documento como referencia antes de continuar.

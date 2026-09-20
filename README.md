# DexRelay

Aplicación de escritorio *companion* para partidas de **Pokémon Omega Ruby / Alpha Sapphire** ejecutadas en el emulador **Azahar**. Lee la memoria del juego en vivo (sin modificar el ROM ni el save) y la muestra en una GUI propia, en overlays para OBS y en un servidor HTTP local.

> Estado: **v0.3.0-alpha** — funciona y se probó en partidas reales, pero puede tener bugs.
> [Descargar el último release](https://github.com/RoacTech22/DexRelay/releases/tag/v0.3.0-alpha)

## Qué incluye

- **Dashboard:** estado de la conexión con Azahar, equipo actual, medallas y URLs de los overlays.
- **Pokémon:** equipo y las 7 primeras cajas, detalle de cada Pokémon, modal Pokédex (tipos, stats base, habilidades, evoluciones con ramas, resistencias y debilidades) y modales de movimientos y habilidades.
- **Medallas y líderes de gimnasio:** progreso, retratos y equipos de cada líder.
- **Nuzlocke Tracker:** encuentros por ruta con captura automática, cementerio, level cap del siguiente líder, reglas editables y registro automático de encuentros **perdidos** (huida o derrota sin captura).
- **Overlays para OBS** (Browser Source): Team (1170×210), Badges (656×100) y Nuzlocke (376×270).
- **Herramientas:** agregar Caramelo Raro a la bolsa. Es la única función que **escribe** en memoria, con aviso visible; todo lo demás es solo lectura.
- **Soporte del ROM hack Rising Ruby / Sinking Sapphire** (opcional, desactivado por defecto): líderes propios, cambios de evolución, de tipo/habilidad/stats y de movimientos. Se activa desde Configuración, sin reiniciar.
- **Reconexión automática:** si cierras y reabres Azahar con DexRelay abierto, vuelve a detectar el juego solo, incluso si abres el otro.

Todo corre **100 % offline**: no hay ninguna dependencia de red en tiempo de ejecución.

## Requisitos

- Windows 10/11 de 64 bits.
- [Azahar](https://azahar-emu.org/) con el juego cargado (DexRelay se conecta por UDP al puerto `45987`).
- **Pokémon Omega Ruby o Alpha Sapphire con la actualización 1.4 instalada.** Las direcciones de memoria son específicas de esa versión exacta del juego: con el juego base el mapa de memoria queda corrido y DexRelay no lee nada (equipo vacío, sin error visible).
- Microsoft Edge WebView2 Runtime (ya viene con Windows 11 y con Edge actualizado).

No hace falta instalar .NET: el release incluye el bridge PKHeX autocontenido.

## Instalación (release)

1. Descarga `DexRelay-v0.3.0-alpha-win-x64.zip` desde la [página de releases](https://github.com/RoacTech22/DexRelay/releases).
2. Descomprímelo en una carpeta con permisos de escritura (tu progreso se guarda dentro de `data/`).
3. Abre `DexRelay.exe`. Windows SmartScreen puede avisar que el ejecutable no está firmado ("Más información" → "Ejecutar de todas formas").
4. Abre Azahar con el juego y pulsa **Comenzar**. DexRelay detecta el juego solo.

### Overlays en OBS

Añade una fuente *Browser Source* con la URL y el tamaño indicados. La página **Overlays** de la app muestra las URLs y permite copiarlas:

| Overlay | URL | Tamaño |
|---|---|---|
| Team | `http://localhost:8080/overlay/team` | 1170×210 |
| Badges | `http://localhost:8080/overlay/badges` | 656×100 |
| Nuzlocke | `http://localhost:8080/overlay/nuzlocke` | 376×270 |

## Ejecutar desde el código fuente

Requisitos: Python 3.13, y el SDK de .NET 10 si no publicas el bridge (en desarrollo se usa `dotnet run`).

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Para publicar el bridge y empaquetar (Git Bash, con la `.venv` activada):

```bash
cd dotnet/DexRelay.PKHeX
dotnet publish -c Release -r win-x64 --self-contained true \
    -p:PublishSingleFile=true \
    -p:IncludeNativeLibrariesForSelfExtract=true \
    -o ../../releases/pkhex-bridge
cd ../..
pip install pyinstaller
pyinstaller DexRelay.spec --noconfirm --clean
```

El resultado queda en `dist/DexRelay/`. El spec genera una `config.json` de distribución limpia y **no** empaqueta tu progreso (`badges`, `nuzlocke_*`, `team_overlay_settings`).

## Arquitectura

```text
Azahar (UDP 45987) → lector de memoria (Python) → Runtime / ApplicationState
                                                   ├─ GUI de escritorio (pywebview)
                                                   └─ servidor HTTP local
                                                       ├─ overlays para OBS
                                                       └─ panel web del Nuzlocke
Bridge PKHeX (.NET 10, PKHeX.Core) ← JSON por stdin/stdout, para nombres, tipos, stats y evoluciones
```

La GUI, los overlays y el Nuzlocke Tracker nunca leen memoria directamente: todo pasa por `Runtime` y `ApplicationState`. La lógica de Pokémon se delega en PKHeX en vez de reimplementarla.

## Limitaciones conocidas

- El HP en combate del overlay asume que el Pokémon activo es el del slot 1 (no se logró detectar el slot real).
- Solo se leen las cajas 1 a 7.
- Las capturas raras (huevos, regalos, intercambios) o sin ubicación resuelta caen a "pendientes" para revisión manual.
- Si un perdido no puede leer la especie del rival, se registra como "Desconocido" y se edita desde el panel web (`/panel/nuzlocke`).
- El overlay Nuzlocke muestra hasta 8 caídos sin recorte.

## Reportar problemas

Abre un [issue](https://github.com/RoacTech22/DexRelay/issues) e incluye lo que aparezca en la pestaña **Logs** de la app.

## Créditos

- [PKHeX.Core](https://github.com/kwsch/PKHeX) para la lectura y decodificación de datos de Pokémon.
- [PokéAPI](https://pokeapi.co/) como fuente de datos de movimientos, curados una sola vez de forma offline.
- Emulador Azahar y su interfaz de depuración por UDP.

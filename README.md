# DexRelay

<p align="center">
  <img src="docs/images/dexrelay_logo.png" alt="DexRelay" width="420">
</p>

<p align="center">
  <strong>Tu compañero para Pokémon ORAS, X/Y y Sol/Luna en Azahar</strong>
</p>

<p align="center">
  Equipo en tiempo real · Nuzlocke · Pokédex · Medallas · OBS
</p>

<p align="center">

  <a href="https://github.com/RoacTech22/DexRelay/releases#release-v0.9.0-alpha">
    <img src="https://img.shields.io/badge/Descargar-v0.9.0--alpha-00c8d7?style=for-the-badge" alt="Descargar DexRelay">
  </a>

  <a href="https://github.com/RoacTech22/DexRelay/issues">
    <img src="https://img.shields.io/badge/Reportar%20problema-GitHub-111827?style=for-the-badge" alt="Reportar problema">
  </a>

</p>

---

## ¿Qué es DexRelay?

**DexRelay** es una aplicación de escritorio para partidas de **Pokémon Omega Ruby y Alpha Sapphire (ORAS)**, de **Pokémon X e Y** y de **Pokémon Sol y Luna** ejecutadas en **Azahar**.

Lee los datos de la partida en tiempo real y los convierte en información útil para jugar, gestionar un Nuzlocke y transmitir tus partidas.

DexRelay integra en una sola aplicación:

- Equipo Pokémon en tiempo real.
- Información detallada de Pokémon.
- Pokédex integrada.
- Cajas Pokémon.
- Medallas y líderes de gimnasio (en Alola, el Desafío de las islas).
- Bosses: rivales, villanos y combates de historia, con detección automática.
- Nuzlocke Tracker.
- Overlays para OBS.
- Servidor HTTP local.
- Herramientas adicionales para la partida.

La aplicación funciona **100 % offline** y no necesita servicios externos durante su ejecución.

> **Estado actual:** v0.9.0-alpha  
> Bosses y detección automática de combates ganados en Pokémon X/Y (Kalos), y shiny y objeto equipado visibles en tus Pokémon.

---

## Vista general

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Dashboard de DexRelay" width="900">
</p>

El Dashboard reúne en una sola pantalla el estado de Azahar, el lector de memoria, el Runtime, el servidor HTTP, el equipo actual, las medallas y los overlays disponibles.

---

# Funciones principales

## Pokémon en tiempo real

DexRelay detecta automáticamente el juego conectado a Azahar y muestra el equipo actual.

<p align="center">
  <img src="docs/screenshots/team.png" alt="Equipo Pokémon en DexRelay" width="900">
</p>

Para cada Pokémon puedes consultar información como:

- Nombre y apodo.
- Nivel.
- Género.
- Tipo o tipos.
- Habilidad.
- Movimientos.
- HP actual y máximo.
- Estadísticas.
- Si es shiny y el objeto que lleva equipado.
- Información detallada del Pokémon.

También puedes consultar las cajas del PC (las primeras **7** en Hoenn y Kalos y las **8** de Alola).

---

## Pokédex integrada

DexRelay incluye una Pokédex integrada con información detallada de las especies.

<p align="center">
  <img src="docs/screenshots/pokedex.png" alt="Pokédex de DexRelay" width="900">
</p>

La ficha de cada especie puede mostrar:

- Tipo.
- Estadísticas base.
- Habilidades.
- Habilidad oculta.
- Altura y peso.
- Categoría.
- Evoluciones.
- Evoluciones ramificadas.
- Formas regionales de Alola, con su evolución regional.
- Debilidades.
- Resistencias.
- Inmunidades.

---

## Medallas y líderes de gimnasio

Consulta el progreso de las 8 medallas de Hoenn o de Kalos y la información de los líderes, el Alto Mando y el campeón de cada región.

En **Pokémon Sol y Luna** no hay medallas: la página muestra el **Desafío de las islas**, con las 7 pruebas de capitán y las 4 Grandes Pruebas de los Kahuna por isla, más la Liga Pokémon de Alola (Kaudan, Mayla, Zarala, Kahili y el campeón Kukui) con sus retratos.

DexRelay muestra:

- Medallas obtenidas y pendientes.
- Líder correspondiente.
- Ciudad.
- Tipo de gimnasio.
- Equipo del líder.
- Alto Mando y campeón, con sus equipos.
- Próximo líder y nivel máximo recomendado.
- Información específica para Rising Ruby / Sinking Sapphire cuando el modo hackrom está activado.

---

## Bosses

La pestaña **Bosses** reúne los combates de historia de la región: tu rival y tus amigos, villanos, profesores, líderes, Alto Mando y campeón.

DexRelay puede:

- Marcar automáticamente los combates ya ganados (los líderes, por medalla).
- Mostrar el equipo de cada boss con niveles, movimientos y habilidades.
- Indicar el **Siguiente boss**, agrupando los combates que van seguidos.
- Permitir marcar o desmarcar un combate a mano.

Disponible en ORAS, en X/Y y en Sol/Luna. En Alola cubre los **37 combates** de la historia (rivales, capitanes, dominantes, Kahuna, villanos, Alto Mando y campeón), con la naturaleza, la habilidad y el objeto de cada dominante; el Alto Mando se puede hacer en cualquier orden y cada combate se marca al terminar. La detección de algunos combates de Kalos tiene pocas observaciones y puede fallar; en ese caso puedes marcarlos a mano.

---

# Nuzlocke Tracker

DexRelay incluye un tracker de Nuzlocke integrado con la partida.

<p align="center">
  <img src="docs/screenshots/nuzlocke.png" alt="Nuzlocke Tracker de DexRelay" width="900">
</p>

El tracker permite gestionar:

- Primer encuentro por ruta.
- Capturas detectadas automáticamente.
- Pokémon vivos.
- Cementerio.
- Encuentros perdidos.
- Reglas de la partida.
- Nivel máximo del siguiente líder (en Alola, del siguiente dominante, Kahuna o campeón).
- Estadísticas generales.
- Tiempo de juego.
- Seguimiento de rutas y zonas (en Alola, agrupadas por isla).

El sistema también puede detectar automáticamente encuentros que terminan sin captura y dejarlos registrados para revisión cuando la información disponible no permite resolverlos completamente.

---

# Overlays para OBS

DexRelay incluye overlays compatibles con **OBS Browser Source**.

Puedes utilizar:

### Team Overlay

Muestra el equipo actual con sprites, nombres, niveles y estado.

**Tamaño recomendado:** 1170 × 210

### Badges Overlay

Muestra el progreso de las medallas.

**Tamaño recomendado:** 656 × 100

### Nuzlocke Overlay

Muestra información del progreso de la partida Nuzlocke.

**Tamaño recomendado:** 376 × 270

Las URLs se generan automáticamente dentro de DexRelay y pueden copiarse desde la página **Overlays**.

---

## DexRelay para streams

<p align="center">
  <img src="docs/screenshots/stream.png" alt="DexRelay utilizado en un stream" width="1000">
</p>

Los overlays están pensados para integrarse directamente en tus escenas de OBS y mostrar información de la partida sin tener que actualizarla manualmente.

---

# Rising Ruby / Sinking Sapphire

DexRelay incluye soporte opcional para los hackroms:

- **Rising Ruby**
- **Sinking Sapphire**

El modo hackrom está desactivado por defecto y puede activarse desde **Configuración**.

Cuando está activo, DexRelay puede utilizar los datos específicos del hackrom para:

- Líderes de gimnasio.
- Equipos de líderes.
- Cambios de tipo.
- Cambios de habilidades.
- Cambios de estadísticas base.
- Cambios de movimientos.
- Evoluciones modificadas.

---

# Requisitos

## Sistema

- Windows 10/11 de 64 bits.
- Microsoft Edge WebView2 Runtime.
- Azahar con el juego cargado.

## Juego

Actualmente DexRelay soporta:

- Pokémon Omega Ruby — actualización **1.4**.
- Pokémon Alpha Sapphire — actualización **1.4**.
- Pokémon X — actualización **1.5**.
- Pokémon Y — actualización **1.5**.
- Pokémon Sol — actualización **1.2**.
- Pokémon Luna — actualización **1.2**.

> Las direcciones de memoria utilizadas por DexRelay corresponden a estas versiones exactas del juego. Los juegos base sin la actualización indicada no están soportados.

## .NET

No necesitas instalar .NET para utilizar la versión publicada.

El bridge de PKHeX utilizado por DexRelay está incluido en el release como ejecutable autocontenido.

---

# Instalación

## 1. Descargar DexRelay

Descarga:

**DexRelay v0.9.0-alpha**

Archivo:

`DexRelay-v0.9.0-alpha-win-x64.zip`

## 2. Extraer

Descomprime el archivo en una carpeta donde tengas permisos de escritura.

DexRelay guarda determinados datos de progreso dentro de su carpeta `data/`.

## 3. Ejecutar

Abre:

`DexRelay.exe`

## 4. Iniciar Azahar

Abre Azahar y carga Pokémon Omega Ruby, Alpha Sapphire, X, Y, Sol o Luna.

DexRelay detectará automáticamente el juego compatible.

## 5. Comenzar

Pulsa **Comenzar** desde DexRelay.

Cuando la conexión sea correcta, el Dashboard mostrará:

- Azahar conectado.
- Reader activo.
- Runtime ejecutándose.
- Servidor HTTP activo.
- Equipo detectado.

---

# OBS — configuración rápida

1. Abre DexRelay.
2. Conecta Azahar.
3. Ve a **Overlays**.
4. Copia la URL del overlay que quieras utilizar.
5. En OBS añade una fuente **Navegador / Browser Source**.
6. Introduce la URL.
7. Configura el tamaño recomendado.

Las URLs locales tienen este formato:

`http://localhost:8080/overlay/team`

`http://localhost:8080/overlay/badges`

`http://localhost:8080/overlay/nuzlocke`

El overlay de medallas tiene tres estilos (se elige en la página **Medallas** de la GUI): ícono de medalla, retrato del líder de medio cuerpo o líder de cuerpo completo; los líderes se ven "apagados" hasta ganar su medalla. Tamaño recomendado en OBS: 656 × 100 (medallas), 914 × 100 (medio cuerpo) o 668 × 100 (cuerpo completo).

En **Sol y Luna** el overlay muestra los 4 **Kahuna** (Kaudan, Mayla, Denio y Hela), en medio cuerpo o cuerpo completo; el estilo de medallas no aparece en esos juegos.

No necesitas publicar ningún puerto de Internet.

---

# Funcionamiento offline y privacidad

DexRelay funciona localmente en tu ordenador.

La aplicación:

- No necesita conexión a Internet para funcionar.
- No envía los datos de tu partida a servidores externos.
- Utiliza un servidor HTTP únicamente en tu propio ordenador.
- Lee la memoria de Azahar localmente.
- Utiliza datos estáticos incluidos con la aplicación.

La excepción funcional es la página **Herramientas**, donde existe una operación específica para agregar Caramelos Raros a la bolsa.

> **Importante:** esta es actualmente la única función de DexRelay que escribe en la memoria del juego. El resto de las funciones de lectura funcionan en modo de solo lectura.

---

# Herramientas

DexRelay incluye herramientas adicionales para la partida.

Actualmente se puede agregar **Caramelo Raro** a la bolsa desde la página Herramientas, en ORAS y en X/Y.

La operación:

- Requiere una conexión activa.
- Muestra una advertencia antes de ejecutarse.
- Vuelve a leer la memoria después de escribir.
- Muestra la cantidad realmente detectada.

---

# Reconexión automática

DexRelay puede volver a detectar Azahar si el emulador se cierra y vuelve a abrirse mientras DexRelay permanece abierto.

También puede detectar automáticamente si se inicia otro de los juegos compatibles.

---


# Reportar un problema

Si encuentras un error, abre un issue en GitHub.

Cuando sea posible incluye:

- Versión de DexRelay.
- Versión de Azahar.
- Juego utilizado.
- Versión del juego.
- Si utilizas Rising Ruby / Sinking Sapphire.
- Pasos para reproducir el problema.
- Qué esperabas que ocurriera.
- Qué ocurrió realmente.
- Información de la pestaña **Logs**.

Los reportes con información reproducible son especialmente útiles para mejorar DexRelay.

---


# Créditos

DexRelay utiliza:

- **PKHeX.Core** para lectura, decodificación y lógica de datos Pokémon.
- **PokéAPI** como fuente para datos que fueron curados e incorporados localmente.
- **Azahar** y su interfaz de depuración por UDP.

---

# Licencia

**DexRelay** (la aplicación) es software propietario: © 2026 RoacTech22. Todos los derechos reservados. Puedes usarlo gratis, pero no redistribuirlo ni modificarlo. Consulta [`LICENSE.txt`](LICENSE.txt).

**Bridge de PKHeX** (`DexRelay.PKHeX.exe`, incluido en cada release): su código fuente está en la carpeta [`bridge/`](bridge/) y se distribuye bajo la licencia **GNU GPLv3**, porque utiliza [PKHeX.Core](https://github.com/kwsch/PKHeX). Consulta [`bridge/LICENSE`](bridge/LICENSE).

---

<p align="center">
  <strong>DexRelay</strong>
  <br>
  Tu compañero para Pokémon ORAS, X/Y y Sol/Luna en Azahar.
</p>

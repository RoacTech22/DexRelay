"""
API expuesta a JavaScript (pywebview) para la GUI v2 de DexRelay.

Bloque 1 (GUI v2, pywebview): esqueleto -- Bienvenida, Espera,
Conectado, y el shell principal (sidebar + Dashboard placeholder).
Reemplaza en el flujo principal a la GUI Tkinter/ttkbootstrap
(`app/gui/`), que se deja intacta en el proyecto sin usarse --
mismo criterio que con los probes viejos (Documento Maestro:
"documenta lo que ya se probó, no estorba, no se borra").

Decisión de diseño: todos los métodos que devuelven datos leen
directo de `Application`/`ApplicationState` en memoria -- no pasan
por el HTTP server (`/api/*`), aunque esos endpoints sigan
existiendo igual para overlays/panel. Motivo: el webview carga la
UI desde un archivo local (file://), y un fetch() cross-origin
hacia http://localhost:8080 quedaría sujeto a la política CORS del
motor embebido (WebView2/GTK) sin que el HTTPServer mande
Access-Control-Allow-Origin -- no vale la pena agregar eso solo
para la GUI cuando el bridge JS<->Python de pywebview ya resuelve
lo mismo sin ser una petición de red real.
"""

from __future__ import annotations

import base64
import time
import webbrowser

import webview

from app.core import paths
from app.core import log_capture
from app.core.version import get_app_version as resolve_app_version
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
    RARE_CANDY_ITEM_ID,
    BOX_COUNT,
    BOX_SLOT_COUNT,
)
from app.services.bag_service import BagService, BagWriteError
from app.services.gym_leaders import GymLeaderCatalog
from app.services.location_catalog import LocationCatalog
from app.services.playtime_service import PlaytimeService
from app.services.pokemon_detail_resolver import PokemonDetailResolver
from app.services.species_catalog import SpeciesCatalog
from app.services.pkhex.bridge import PKHeXBridge
from app.services.move_data import MoveDataCatalog, merge_move_details
from app.services.move_description import MoveDescriptionCatalog
from app.services.ability_description import AbilityDescriptionCatalog
from app.services.type_effectiveness import (
    TypeChartCatalog,
    compute_effectiveness,
    categorize_effectiveness,
)
from app.services.evolution_translations import (
    describe_evolution,
    METHOD_KEYS_USING_ITEM_ARGUMENT,
    METHOD_KEYS_USING_MOVE_ARGUMENT,
    METHOD_KEYS_USING_TEAMMATE_ARGUMENT,
    EVOLUTION_METHOD_COMPACT_LABELS,
)
from app.services.item_catalog import ItemCatalog
from app.services.species_extra import SpeciesExtraCatalog
from app.services.pre_evolution_catalog import PreEvolutionCatalog

# La versión de la app YA NO se hardcodea acá -- se resuelve en
# `app/core/version.py` (`resolve_app_version()`, importado
# arriba) a partir de `git describe` en modo desarrollo, o de un
# archivo `VERSION` generado por el script de empaquetado en un
# build congelado. Antes había una constante `APP_VERSION = "v0.3.0"`
# escrita a mano acá que nadie actualizaba en cada release real
# (por eso mostraba "v0.3.0" con el repo ya en v0.1.0-alpha) --
# se quitó entera, no queda nada que la referencie.

# Igual que GAME_VERSIONS de la GUI vieja
# (app/gui/welcome_screen.py), sin el subtítulo de "soporte
# parcial" de Omega Ruby -- la compatibilidad OR quedó cerrada
# para todo lo que importa hoy (Documento Maestro, cierre del
# 30/08/2026). Si en el futuro se agrega un juego nuevo, sumar acá
# una entrada más alcanza -- ninguna otra parte de la GUI depende
# de que sean exactamente dos.
#
# "background" es el nombre del archivo en assets/ui/ (arte de
# Groudon/Kyogre provisto por el usuario el 31/08/2026,
# reescalado a 700x700 y comprimido a JPEG -- las originales eran
# PNG de 2000x2000 sin transparencia real, ~1-1.6MB cada una,
# demasiado pesadas para mandar como data URI en cada arranque de
# la GUI sin necesidad).
GAME_VERSIONS = [
    {
        "label": "Alpha Sapphire",
        "process_name": PROCESS_NAME_ALPHA_SAPPHIRE,
        "badge": "AS",
        "background": "bg_alpha_sapphire.jpg",
    },
    {
        "label": "Omega Ruby",
        "process_name": PROCESS_NAME_OMEGA_RUBY,
        "badge": "OR",
        "background": "bg_omega_ruby.jpg",
    },
]

_GAME_LABELS = {
    game["process_name"]: game["label"] for game in GAME_VERSIONS
}

# Title ID (hex, 16 dígitos, sin "0x") -> región. Tabla confirmada
# por el usuario el 31/08/2026 (una tabla encontrada antes tenía
# datos mezclados/incorrectos -- descartada). Todos los juegos
# Pokémon de 3DS de esta lista son region-free: un solo Title ID
# vale para USA/EUR/JPN, así que van con "FREE" en vez de un valor
# de región real. Se deja la tabla completa (no solo AS/OR) porque
# el usuario planea sumar otros juegos más adelante -- si alguno
# de esos SÍ tiene Title IDs distintos por región, hay que agregar
# una entrada por cada Title ID regional acá con su región real
# ("USA"/"EUR"/"JPN"), no "FREE". Un Title ID que no esté en esta
# tabla no se inventa -- get_connection_status() devuelve `None` y
# el frontend lo muestra como "Desconocido".
TITLE_ID_REGIONS = {
    "0004000000055D00": "FREE",  # Pokémon X
    "0004000000055E00": "FREE",  # Pokémon Y
    "000400000011C400": "FREE",  # Pokémon Omega Ruby
    "000400000011C500": "FREE",  # Pokémon Alpha Sapphire
    "0004000000164800": "FREE",  # Pokémon Sun
    "0004000000175E00": "FREE",  # Pokémon Moon
    "00040000001B5000": "FREE",  # Pokémon Ultra Sun
    "00040000001B5100": "FREE",  # Pokémon Ultra Moon
}

# Repositorio real del proyecto (confirmado 05/09/2026 -- el
# mockup de Configuración traía un placeholder, "roniidex/dexrelay",
# que no es el repo real; corregido acá). Usado en el link del
# footer de Bienvenida y en la página de Configuración.
GITHUB_URL = "https://github.com/RoacTech22/DexRelay"
ISSUES_URL = GITHUB_URL + "/issues"

# Valores por defecto reales -- los mismos que usa
# `Application.__init__()` (app/core/app.py) como fallback cuando
# una clave no está en config.json. "Restablecer" de la página
# Configuración vuelve a estos, no a lo que el usuario tenga
# guardado ahora. `azahar.process_name` (default real: "sango-2",
# ver Application.__init__) NO se expone acá a propósito -- desde
# que la GUI v2 detecta el juego solo (start_auto(), Bienvenida sin
# selección manual), ese valor es solo un fallback interno antes de
# la primera conexión y se re-sincroniza solo (restart_reader());
# exponerlo como campo editable invitaría a tocar algo que ya no
# hace falta tocar a mano.
DEFAULT_CONNECTION_SETTINGS = {
    "host": "127.0.0.1",
    "port": 8080,
    "refresh_ms": 200,
}


class Api:
    """
    Clase expuesta como `window.pywebview.api` en el frontend. Cada
    método público acá es invocable desde JS
    (`pywebview.api.nombre_metodo(...)`, devuelve una Promise).
    """

    def __init__(self, application) -> None:
        self.app = application

        # Página Pokémon (Bloque 3) -- ver
        # app/services/pokemon_detail_resolver.py sobre por qué
        # esto vive acá (solo GUI) y no en Application (no lo usa
        # ningún overlay ni el HTTP server).
        self.pokemon_detail_resolver = PokemonDetailResolver()

        # Modales de movimiento/habilidad/especie (07/09/2026,
        # roadmap 4.1/4.2) -- instancia PROPIA del bridge, mismo
        # criterio que ya usa PokemonDetailResolver (cada resolver/
        # catálogo de la GUI arranca su propio proceso .NET en vez
        # de compartir uno global; no es lo más liviano posible,
        # pero es el patrón ya establecido en el resto de este
        # archivo, no se cambia acá de paso). Se llama
        # "modal_bridge" (no "move_details_bridge" como al
        # principio) porque ahora también resuelve species_details()
        # para el modal Pokédex de especie, no solo movimientos.
        # MoveDataCatalog/MoveDescriptionCatalog/
        # AbilityDescriptionCatalog/TypeChartCatalog son lecturas de
        # JSON cacheadas, sin costo de mantener vivas.
        self.modal_bridge = PKHeXBridge()
        self.move_data_catalog = MoveDataCatalog()
        self.move_description_catalog = MoveDescriptionCatalog()
        self.ability_description_catalog = AbilityDescriptionCatalog()
        self.type_chart_catalog = TypeChartCatalog()
        self.item_catalog = ItemCatalog()
        self.species_extra_catalog = SpeciesExtraCatalog()
        self.pre_evolution_catalog = PreEvolutionCatalog()

        # Página Nuzlocke (GUI v2, 04/09/2026) -- mismo criterio
        # que pokemon_detail_resolver: instancias propias, solo
        # para la GUI. species_catalog/location_catalog ya existen
        # también dentro de HTTPServer (para /api/species,
        # /api/locations que usa panels/nuzlocke/) -- se duplica la
        # instancia acá en vez de compartirla para no tener que
        # tocar Application/HTTPServer, mismo patrón que ya se usó
        # con PokemonDetailResolver.
        self.species_catalog = SpeciesCatalog()
        self.location_catalog = LocationCatalog()
        self.playtime_service = PlaytimeService()

        # Pestaña Líderes del Nuzlocke (Fase B, roadmap 3.1/3.2) --
        # dataset estático curado en Fase A, no necesita el bridge
        # PKHeX ni memoria en vivo para el JSON en sí (aunque sí
        # necesita el bridge la primera vez para resolver
        # abilityEs/movesEs, ver gym_leaders.py).
        #
        # Fase E (09/09/2026): soporte para el hack Rising Ruby /
        # Sinking Sapphire (Drayano) -- toggle manual en
        # Configuración (config.json -> hackroom.enabled), decisión
        # del usuario: Azahar no expone si el ROM cargado es el
        # juego base o el hack parcheado, así que no hay forma de
        # detectarlo solo.
        #
        # CORRECCIÓN (09/09/2026, a pedido del usuario: "el cambio
        # al hackroom no se puede hacer sin reiniciar la app"): se
        # instancian los DOS catálogos de una vez acá (vanilla y
        # rrss) en vez de elegir uno solo al arrancar -- cada uno
        # cachea su propio JSON en memoria por separado, así que
        # tenerlos los dos vivos no duplica trabajo real. Cuál se
        # usa se decide en cada pedido (_active_gym_leader_catalog()
        # más abajo), leyendo config.json en el momento -- así el
        # toggle de Configuración surte efecto ni bien se guarda,
        # sin reiniciar DexRelay.
        self.gym_leader_catalog = GymLeaderCatalog()
        self.gym_leader_catalog_hackroom = GymLeaderCatalog(
            data_path=paths.path("data", "gym_leaders_rrss.json")
        )

    # -----------------------------------------------------------
    # Bienvenida
    # -----------------------------------------------------------

    def get_game_versions(self):
        """
        Cada entrada trae su `background` ya resuelto como data URI
        (ver `_asset_data_uri()`), listo para usar directo como
        `background-image` en CSS -- el frontend no necesita saber
        nada de rutas de archivo.
        """

        versions = []

        for game in GAME_VERSIONS:
            entry = dict(game)
            entry["background"] = self._asset_data_uri(
                "ui", game["background"], mime="image/jpeg"
            )
            versions.append(entry)

        return versions

    def get_app_version(self):
        return resolve_app_version()

    def get_logo_data_uri(self):
        """
        Devuelve el logo como data URI base64 en vez de una ruta
        de archivo -- evita depender de la posición relativa entre
        `app/gui_web/web/` y `assets/ui/`, que cambia entre modo
        desarrollo y build empaquetado (ver `app/core/paths.py`,
        que ya centraliza ese criterio). `None` si el archivo no
        está (por ejemplo, alguien corrió el código sin extraer el
        asset del zip) -- el frontend cae a un título de texto.
        """

        return self._asset_data_uri(
            "ui", "dexrelay_logo.png", mime="image/png"
        )

    def get_welcome_background_data_uri(self):
        """
        Arte de fondo de la pantalla Bienvenida (imagen provista por
        el usuario el 01/09/2026, reescalada a 1200px de ancho y
        comprimida a JPEG ~165KB -- el original eran 1360x768 sin
        comprimir, ~440KB). El CSS la funde con el degradado oscuro
        existente (#view-welcome::before) para que quede sutil, no
        a color pleno -- mismo espíritu que el mockup original del
        usuario (Kyogre apenas visible detrás del logo). `None` si
        el archivo no está.
        """

        return self._asset_data_uri(
            "ui", "bg_welcome.jpg", mime="image/jpeg"
        )

    # Miniaturas reales de cada overlay (página Overlays, GUI v2,
    # 05/09/2026) -- capturas provistas por el usuario, recortadas
    # al contenido real (sin el margen blanco de la captura
    # original). Mismo criterio que el logo/fondo de arriba: data
    # URI vía _asset_data_uri(), no dependen de que el HTTP server
    # esté corriendo (a diferencia de los sprites de /overlay/team/
    # sprites/, que sí).
    _OVERLAY_PREVIEW_FILES = {
        "team": "overlay_preview_team.png",
        "badges": "overlay_preview_badges.png",
        "nuzlocke": "overlay_preview_nuzlocke.png",
    }

    def get_overlay_preview_data_uri(self, overlay_id: str):
        filename = self._OVERLAY_PREVIEW_FILES.get(overlay_id)

        if filename is None:
            return None

        return self._asset_data_uri(
            "ui", filename, mime="image/png"
        )

    @staticmethod
    def _asset_data_uri(*parts: str, mime: str):
        """
        Helper compartido para servir cualquier archivo de
        `assets/` como data URI -- mismo criterio que
        `get_logo_data_uri()` ya usaba, generalizado acá para no
        repetirlo por cada imagen nueva (fondos de versión, y lo
        que haga falta en los próximos bloques). `None` si el
        archivo no está.
        """

        asset_path = paths.path("assets", *parts)

        try:
            data = asset_path.read_bytes()
        except (FileNotFoundError, OSError):
            return None

        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    # -----------------------------------------------------------
    # Espera / Conectado
    # -----------------------------------------------------------

    def start(self, process_name: str):
        """
        Arranca Application (Runtime + HTTPServer) con una versión
        elegida a mano -- se deja por compatibilidad, pero la
        pantalla de Bienvenida actual ya no la usa (ver
        start_auto()). Mismo criterio que
        `WaitingScreen._start_and_poll()` en la GUI Tkinter
        (`app/gui/waiting_screen.py`).
        """

        self.app.reader.process_name = process_name
        self.app.config.set(
            "azahar", "process_name", value=process_name
        )
        self.app.config.save()

        if not self.app.running:
            self.app.start()

        return True

    def start_auto(self):
        """
        "Comenzar" de la pantalla Bienvenida (02/09/2026 en
        adelante: ya no hace falta elegir versión, se detecta
        sola). Pone `reader.process_name` en `None` -- modo
        automático, ver `AzaharReader.find_game_process()` -- y
        arranca Application; el loop realtime normal se encarga de
        encontrar cualquiera de los juegos conocidos apenas
        aparezca, sin que la GUI tenga que hacer nada especial acá.
        """

        self.app.reader.process_name = None

        if not self.app.running:
            self.app.start()

        return True

    def cancel(self):
        """
        Cancela la espera de conexión o vuelve a Bienvenida
        ("Salir" del sidebar, mismo botón) deteniendo Application.

        Limpia también la identidad cacheada del proceso
        (`process_id`/`title_id`) -- no estrictamente necesario
        después del fix de is_connected() del 02/09/2026, pero dejar
        esto en cero acá evita depender de esa única protección
        para un "Salir" que se sienta realmente limpio.
        """

        if self.app.running:
            self.app.stop()

        self.app.reader.process_id = None
        self.app.reader.title_id = None

        return True

    def get_connection_status(self):
        """
        Consultado por la pantalla de Espera (hasta que
        `connected` sea `True`) y por el bloque de estado del
        sidebar en el shell principal (sección "RUNNING" de los
        mockups).

        `region` sale de `TITLE_ID_REGIONS`, buscando por el
        Title ID real que reportó Azahar (`reader.title_id`) --
        nunca se asume por `process_name`. Si el Title ID todavía
        no se conoce (recién conectando) o no está en la tabla
        (juego no confirmado todavía), devuelve `None` en vez de
        inventar algo; el frontend lo muestra como "Desconocido".
        """

        return self._connection_fields()

    def get_dashboard_data(self):
        """
        Todo lo que necesita la página Dashboard (GUI v2, Bloque 2)
        en una sola llamada -- incluye los mismos campos que
        `get_connection_status()` (así `pollMain()` en app.js puede
        usar esta única llamada también para el bloque de estado
        del sidebar, en vez de pedir las dos cosas por separado
        cada segundo).

        `team` y `badges` son exactamente lo que ya lee el Runtime
        realtime hacia `ApplicationState` -- no se recalcula nada
        acá, es una lectura directa. Los sprites de cada Pokémon y
        de cada medalla NO viajan por acá: se sirven como
        `<img src>` directo contra el HTTPServer que ya está
        corriendo (`http_server.base_url` + la misma ruta que usan
        los overlays, `/overlay/team/sprites/{speciesId}.png` y
        `/overlay/badges/sprites/{n}.png`) -- son archivos
        estáticos, no hace falta mandarlos en base64 por el puente
        JS<->Python en cada ciclo.

        `graveyard_nicknames` (02/09/2026): nicknames del
        cementerio del Nuzlocke Tracker, para que la tarjeta de
        equipo pueda mostrar en gris un Pokémon que murió aunque
        hoy esté sano (mismo criterio que ya usa
        overlays/team/app.js) -- no se recalcula nada, es
        `state.nuzlocke` tal cual ya lo escribe el Runtime.

        `other_game_detected` (02/09/2026): si NO hay conexión y
        había un juego configurado antes, se fija -- sin gastar la
        llamada UDP en el camino normal -- si hay un juego
        CONOCIDO DISTINTO corriendo en Azahar ahora mismo. El
        frontend lo usa para sugerir "hacé clic en Reiniciar" en
        vez de solo decir "se perdió la conexión".

        Campos del mockup de Dashboard que NO están acá a
        propósito: "FPS del juego" y "Memoria base" -- no hay
        ninguna fuente real para esos dos todavía (no se
        investigaron), así que no se inventan.
        """

        state = self.app.state
        reader = self.app.reader
        fields = self._connection_fields()

        uptime_seconds = None

        if self.app.runtime_running and self.app._runtime_started_at is not None:
            uptime_seconds = time.monotonic() - self.app._runtime_started_at

        badges = state.badges

        if not isinstance(badges, dict):
            # Todavía no hubo ninguna lectura de medallas exitosa
            # en esta sesión (recién conectando) -- placeholder
            # honesto, no una lectura real.
            badges = {"value": 0, "count": 0, "badges": [False] * 8}

        nuzlocke = state.nuzlocke or {}
        graveyard_nicknames = [
            entry.get("nickname")
            for entry in nuzlocke.get("graveyard", [])
            if entry.get("nickname")
        ]

        other_game_label = None

        if not state.azahar_connected and reader.process_name is not None:
            detected_name = reader.detect_process_name()

            if (
                detected_name is not None
                and detected_name != reader.process_name
            ):
                other_game_label = _GAME_LABELS.get(
                    detected_name, detected_name
                )

        fields.update({
            "uptime_seconds": uptime_seconds,
            "http_server": {
                "host": self.app.http_server.host,
                "port": self.app.http_server.port,
                "base_url": self.get_server_base_url(),
                # Página Overlays (GUI v2, 05/09/2026): conexiones
                # TCP abiertas ahora mismo contra el HTTP server
                # (ver HTTPServer.get_active_connections()) -- 0 si
                # el servidor está detenido, no un placeholder
                # inventado.
                "clients": self.app.http_server.get_active_connections(),
            },
            "team": state.team or [],
            "badges": badges,
            "graveyard_nicknames": graveyard_nicknames,
            "other_game_detected": other_game_label,
        })

        return fields

    def _connection_fields(self):
        state = self.app.state
        reader = self.app.reader

        process_name = reader.process_name
        title_id = getattr(reader, "title_id", None)

        region = None

        if title_id is not None:
            region = TITLE_ID_REGIONS.get(f"{title_id:016X}")

        return {
            "running": self.app.running,
            "runtime_running": self.app.runtime_running,
            "http_running": self.app.http_running,
            "connected": state.azahar_connected,
            "reader_active": state.reader_active,
            "process_name": process_name,
            "game_label": _GAME_LABELS.get(
                process_name, process_name
            ),
            "process_id": getattr(reader, "process_id", None),
            "region": region,
        }

    # -----------------------------------------------------------
    # Control independiente de Runtime/HTTPServer/Reader --
    # tarjetas READER, RUNTIME y HTTP SERVER del Dashboard
    # (01/09/2026). La tarjeta AZAHAR se queda sin botón a
    # propósito -- no hay ningún control real que tenga sentido
    # ahí, es solo estado de lo que reporta el emulador.
    # -----------------------------------------------------------

    def restart_reader(self):
        self.app.restart_reader()
        return True

    def start_runtime(self):
        self.app.start_runtime()
        return True

    def stop_runtime(self):
        self.app.stop_runtime()
        return True

    def start_http_server(self):
        self.app.start_http_server()
        return True

    def stop_http_server(self):
        self.app.stop_http_server()
        return True

    # -----------------------------------------------------------
    # Editor del Team Overlay (GUI v2, página Overlays,
    # 05/09/2026) -- lee/escribe directo sobre la instancia
    # compartida (self.app.team_overlay_settings), sin pasar por
    # HTTP, así el editor funciona aunque el HTTP server esté
    # detenido. El overlay real (corriendo en un navegador/OBS
    # aparte) solo tiene la vía HTTP
    # (GET/POST /api/team-overlay-settings, ver http_server.py).
    # -----------------------------------------------------------

    def get_team_overlay_settings(self):
        return self.app.team_overlay_settings.get()

    def save_team_overlay_settings(self, settings):
        return self.app.team_overlay_settings.update(settings)

    # -----------------------------------------------------------
    # Shell principal -- se completa en los próximos bloques
    # (Pokémon, Medallas, Nuzlocke, Overlays, Configuración,
    # Logs)
    # -----------------------------------------------------------

    def get_pokemon_page_data(self):
        """
        Página Pokémon (GUI v2, Bloque 3) -- a pedido del usuario,
        reemplaza la vista de lista simple del mockup por el
        detalle completo (boceto: sprite, sexo, especie, tipos,
        habilidad, stats con indicador de naturaleza,
        movimientos) directo en cada una de las 6 tarjetas, sin
        vista aparte.

        Combina, por slot:
        - Identidad básica (nickname/especie/nivel/HP/shiny) --
          `state.team`, la misma lectura que ya usa el Dashboard,
          sin memoria nueva.
        - Detalle vía PKHeX (tipos/habilidad/naturaleza/stats/
          movimientos) -- bajo demanda, releyendo memoria fresca
          para cada slot (ver
          AzaharReader.read_pokemon_raw_for_slot()) y resolviendo
          con PokemonDetailResolver (sin caché, ver su docstring).

        Un slot vacío devuelve solo `{"slot": n, "empty": True}` --
        el detalle ni se pide.

        Bug real (03/09/2026, confirmado con logs reales del
        usuario): con Azahar/el juego cerrado, esto seguía
        intentando releer memoria por cada uno de los 6 slots en
        CADA poll de 2s de la página (ver POKEMON_POLL_MS en
        app.js) -- inofensivo (ya no rompe nada gracias a los
        fixes anteriores en read_pokemon_raw_for_slot()), pero
        inundaba la consola con la misma línea de error una y otra
        vez mientras el juego siguiera cerrado, y golpeaba un
        socket que se sabe de antemano que va a fallar. Se chequea
        `state.azahar_connected` (ya lo mantiene al día
        Runtime.update() en cada ciclo, no hace falta otra
        consulta) ANTES de intentar leer -- sin conexión, se
        devuelve la identidad básica que ya se tenía (o "vacío" si
        ni eso), sin tocar el socket para nada.
        """

        team = self.app.state.team or []
        connected = self.app.state.azahar_connected
        pages = []

        for slot in range(1, 7):
            basic = next(
                (
                    entry
                    for entry in team
                    if entry.get("slot") == slot
                ),
                None,
            )

            if not basic or basic.get("empty"):
                pages.append({"slot": slot, "empty": True})
                continue

            if not connected:
                entry = dict(basic)
                entry["details"] = None
                pages.append(entry)
                continue

            pokemon = self.app.reader.read_pokemon_raw_for_slot(
                slot
            )

            if pokemon is None:
                # La party dice que hay algo acá pero la lectura
                # bajo demanda falló de forma transitoria -- se
                # muestra la identidad básica igual (ya la
                # tenemos de `state.team`) sin detalle, en vez de
                # ocultar la tarjeta entera.
                print(
                    f"[Api] get_pokemon_page_data: lectura fallida "
                    f"para el slot {slot} (READ_FAILED o vacío "
                    f"inesperado)."
                )
                entry = dict(basic)
                entry["details"] = None
                pages.append(entry)
                continue

            details = self.pokemon_detail_resolver.resolve(
                pokemon.raw_data[:232]
            )

            entry = dict(basic)
            entry["details"] = details
            pages.append(entry)

        return pages

    def get_boxes_overview(self):
        """
        Pestaña "General" de la página Pokémon (roadmap 08/09/2026,
        sección 5.1/5.2) -- equipo actual + las Cajas PC (BOX_COUNT,
        7 -- ver pointers.py), ambos con detalle MÍNIMO
        (sprite/nombre/nivel, sin golpear el bridge PKHeX) -- a
        diferencia de get_box_page_data() de más abajo, que sí
        resuelve detalle completo pero solo para UNA caja puntual
        (la que el usuario abre en la pestaña "Caja").

        Una sola lectura UDP para las BOX_COUNT cajas
        (AzaharReader.read_boxes_range(), ya usada para el matching
        del Nuzlocke Tracker) en vez de BOX_COUNT lecturas sueltas
        -- se pide bajo demanda, solo mientras la pestaña "General"
        está abierta (ver dexrelay:tabchange en app.js), no en el
        poll de fondo del Dashboard.

        DECISIÓN DE ALCANCE (09/09/2026, a pedido del usuario):
        BOX_COUNT quedó fijo en 7 (las cajas de fábrica), no en las
        31 que soporta el juego como máximo teórico -- un Nuzlocke
        real nunca necesita comprar más, las capturas están
        limitadas. Esto es exactamente la misma lectura que ya usa
        el Nuzlocke Tracker en producción desde antes (mismo
        BOX_COUNT, mismo read_boxes_range()), así que no hay
        incertidumbre de tamaño/latencia nueva acá -- ya está
        probado en vivo.

        Devuelve {"connected": bool, "team": [...] (mismo formato
        que ya usa el Dashboard), "boxes": [{"boxIndex", "pokemon":
        [...]}, ...]} -- una entrada por caja, 1 a BOX_COUNT, en
        orden, incluso las vacías (con "pokemon": []).
        """

        connected = self.app.state.azahar_connected
        team = self.app.state.team or []

        if not connected:
            return {
                "connected": False,
                "team": team,
                "boxes": [
                    {"boxIndex": box_index, "pokemon": []}
                    for box_index in range(1, BOX_COUNT + 1)
                ],
            }

        occupied = self.app.reader.read_boxes_range(
            1, BOX_COUNT
        )

        by_box_index = {}

        for entry in occupied:
            by_box_index.setdefault(
                entry.get("boxIndex"), []
            ).append({
                "slot": entry.get("slot"),
                "speciesId": entry.get("speciesId"),
                "species": entry.get("species"),
                "nickname": entry.get("nickname"),
                "level": entry.get("level"),
                "shiny": entry.get("shiny"),
                "isEgg": entry.get("isEgg"),
            })

        boxes = [
            {
                "boxIndex": box_index,
                "pokemon": by_box_index.get(box_index, []),
            }
            for box_index in range(1, BOX_COUNT + 1)
        ]

        return {
            "connected": True,
            "team": team,
            "boxes": boxes,
        }

    def get_box_page_data(self, box_index):
        """
        Pestaña "Caja" de la página Pokémon (roadmap 08/09/2026,
        sección 5.1/5.3) -- detalle COMPLETO (tipos/habilidad/
        naturaleza/stats/movimientos, vía PKHeX) para los Pokémon
        de UNA caja puntual, mismo criterio exacto que
        get_pokemon_page_data() ya usa para el equipo: identidad
        básica primero (read_box(), sin bridge), detalle vía
        PokemonDetailResolver bajo demanda después, solo para los
        slots ocupados.

        A diferencia de la party (siempre 6 slots fijos), acá se
        arma la lista completa de BOX_SLOT_COUNT (30) slots,
        marcando "empty": True los que no tengan Pokémon -- así el
        frontend puede mostrar la grilla completa de la caja igual
        que ya hace con los 6 slots del equipo.

        `box_index` es 1-based (Caja 1 = 1). Fuera de rango
        (1..BOX_COUNT) devuelve {"error": "..."} sin tocar memoria.
        """

        if not (1 <= box_index <= BOX_COUNT):
            return {"error": f"box_index fuera de rango: {box_index}"}

        connected = self.app.state.azahar_connected

        slots = [
            {"slot": slot, "boxIndex": box_index, "empty": True}
            for slot in range(1, BOX_SLOT_COUNT + 1)
        ]

        if not connected:
            return {
                "boxIndex": box_index,
                "boxCount": BOX_COUNT,
                "connected": False,
                "slots": slots,
            }

        occupied_by_slot = {
            entry["slot"]: entry
            for entry in self.app.reader.read_box(box_index)
        }

        for index, slot_number in enumerate(
            range(1, BOX_SLOT_COUNT + 1)
        ):

            basic = occupied_by_slot.get(slot_number)

            if not basic:
                continue

            raw_data = self.app.reader.read_box_slot_raw(
                box_index, slot_number
            )

            details = (
                self.pokemon_detail_resolver.resolve(raw_data)
                if raw_data is not None
                else None
            )

            entry = dict(basic)
            entry["details"] = details
            slots[index] = entry

        return {
            "boxIndex": box_index,
            "boxCount": BOX_COUNT,
            "connected": True,
            "slots": slots,
        }

    def get_move_modal_data(self, move_id):
        """
        Modal de movimiento (GUI v2, roadmap 07/09/2026, sección
        4.1) -- junta las 3 fuentes ya confirmadas en una sola
        respuesta: nombre/tipo/PP (bridge PKHeX,
        PKHeXBridge.move_details()), potencia/precisión/categoría
        (dataset estático, MoveDataCatalog/merge_move_details(), ya
        curado y verificado contra ORAS) y descripción en español
        (dataset estático, MoveDescriptionCatalog, ya curado desde
        move_flavor_text.csv).

        No necesita memoria del juego -- move_id ya lo tiene el
        frontend (viene en `details.moves[].id`, ver
        PokemonDetailResolver/HandlePokemonDetails() en Program.cs),
        así que esto se puede pedir independiente del ciclo de
        polling normal, solo cuando el usuario hace click en una
        fila de movimiento.

        Devuelve el dict combinado tal cual, o
        {"error": "..."} si el bridge falló -- el frontend decide
        cómo mostrar ese caso (no se inventa un valor de respaldo
        acá).
        """

        try:
            bridge_response = self.modal_bridge.move_details(
                move_id
            )
        except Exception as error:
            return {"error": str(error)}

        merged = merge_move_details(
            bridge_response, self.move_data_catalog
        )

        if "error" in merged:
            return merged

        description = self.move_description_catalog.get(move_id)

        merged["descriptionEs"] = description["descriptionEs"]
        merged["descriptionSource"] = description["source"]

        return merged

    def get_ability_modal_data(self, ability_id):
        """
        Modal de habilidad (GUI v2, roadmap 07/09/2026, sección
        4.1) -- a diferencia del de movimiento, no hace falta
        golpear el bridge de nuevo acá: el nombre de la habilidad
        ya lo tiene el frontend (viene en `details.abilityName`,
        resuelto por PokemonDetailResolver cuando se cargó la
        tarjeta), así que esto solo agrega la descripción en
        español (dataset estático, AbilityDescriptionCatalog).
        """

        description = self.ability_description_catalog.get(
            ability_id
        )

        return {
            "id": ability_id,
            "descriptionEs": description["descriptionEs"],
            "descriptionSource": description["source"],
        }

    def get_move_modal_data_by_name(self, name):
        """
        Mismo resultado que get_move_modal_data(), pero para
        lugares de la app que solo tienen el NOMBRE en inglés del
        movimiento, sin id -- hoy, la ventana de detalle de equipo
        de líder de gimnasio (leader_team_window.js), cuyos datos
        salen de data/gym_leaders.json (curado a mano, sin ids).

        Resuelve el id vía
        MoveDescriptionCatalog.get_id_by_name() y delega en
        get_move_modal_data() -- un solo lugar con la lógica real,
        no reimplementada aparte.
        """

        move_id = self.move_description_catalog.get_id_by_name(name)

        if move_id is None:
            return {
                "error": f"Movimiento no encontrado: {name!r}"
            }

        return self.get_move_modal_data(move_id)

    def get_ability_modal_data_by_name(self, name):
        """
        Mismo criterio que get_move_modal_data_by_name(), para
        habilidades.
        """

        ability_id = self.ability_description_catalog.get_id_by_name(
            name
        )

        if ability_id is None:
            return {
                "id": None,
                "descriptionEs": None,
                "descriptionSource": None,
            }

        return self.get_ability_modal_data(ability_id)

    def _resolve_evolution_transition(self, evolution):
        """
        Junta toda la info de CÓMO se da una evolución puntual
        (nivel/objeto/movimiento/compañero + descripción) a partir
        de un dict crudo {methodKey, level, argument} tal como lo
        devuelve species_details() del bridge. Reusado tanto por la
        lista plana de evoluciones como por _build_evolution_chain()
        (roadmap 4.2, 07/09/2026).
        """

        method_key = evolution.get("methodKey")
        level = evolution.get("level")
        argument = evolution.get("argument")

        item_id = None
        item_name = None

        if method_key in METHOD_KEYS_USING_ITEM_ARGUMENT:
            item_id = argument
            item_name = self.item_catalog.get_name(argument)

        move_name = None

        if method_key in METHOD_KEYS_USING_MOVE_ARGUMENT:
            try:
                move_result = self.modal_bridge.move_details(argument)
                if "error" not in move_result:
                    move_name = move_result.get("name")
            except Exception:
                move_name = None

        teammate_name = None

        if method_key in METHOD_KEYS_USING_TEAMMATE_ARGUMENT:
            teammate_name = self.species_catalog.get_name(argument)

        return {
            "level": level,
            "itemId": item_id,
            "itemName": item_name,
            "moveName": move_name,
            "teammateName": teammate_name,
            # Bug real corregido (08/09/2026, reportado por el
            # usuario: "Azurill evoluciona a Marill por amistad no
            # está saliendo eso") -- para los métodos sin nivel real
            # ni objeto/movimiento/compañero (amistad, intercambio
            # simple, belleza, etc. -- `level` viene en 0, que
            # JavaScript trata como "falso"), el frontend necesita
            # ALGO más que mostrar en el conector visual entre
            # etapas -- ver EVOLUTION_METHOD_COMPACT_LABELS.
            "conditionLabel": EVOLUTION_METHOD_COMPACT_LABELS.get(
                method_key
            ),
            "description": describe_evolution(
                method_key,
                level,
                argument,
                item_name=item_name,
                move_name=move_name,
                teammate_name=teammate_name,
            ),
        }

    def _build_forward_evolution_node(
        self, stage_id, stage_details, depth_remaining, seen_ids, current_species_id
    ):
        """
        Nodo de la cadena hacia adelante, con TODAS las ramas (no
        solo la primera) -- corrige el bug real reportado por el
        usuario el 08/09/2026: "Wurmple tiene dos ramas evolutivas
        (Silcoon/Cascoon -> Beautifly/Dustox) y la app solo
        mostraba una". Recursivo: cada nodo puede tener 0, 1 o
        varios hijos (uno por evolución posible), cada uno con su
        propia transición. `depth_remaining` limita cuántos saltos
        hacia adelante se siguen desde la especie actual (2, mismo
        tope que antes tenía el camino único) -- se aplica por
        rama, no en total, así que Wurmple (especie actual) -> 2
        ramas -> cada una 1 salto más alcanza sin problema dentro
        del límite de 2.
        """

        node = {
            "speciesId": stage_id,
            "name": stage_details.get("name") or f"#{stage_id}",
            "isCurrent": stage_id == current_species_id,
            "children": [],
        }

        if depth_remaining <= 0:
            return node

        for evolution in stage_details.get("evolutions", []):
            next_id = evolution.get("toSpeciesId")

            if not next_id or next_id in seen_ids:
                continue

            seen_ids.add(next_id)

            try:
                next_details = self.modal_bridge.species_details(next_id)
            except Exception:
                next_details = {}

            child_node = self._build_forward_evolution_node(
                next_id,
                next_details,
                depth_remaining - 1,
                seen_ids,
                current_species_id,
            )

            node["children"].append({
                "transition": self._resolve_evolution_transition(evolution),
                "node": child_node,
            })

        return node

    def _build_evolution_chain(self, species_id, original_details):
        """
        Cadena de evolución COMPLETA (07/09/2026, a pedido del
        usuario: "haz que en la evolución siempre salgan las tres
        etapas" -- antes solo se mostraba lo que species_details()
        de la especie actual traía directo: hacia adelante siempre,
        hacia atrás nunca, así que una especie de 3ra etapa
        mostraba solo 2 eslabones en vez de los 3).

        Actualizado 08/09/2026 para mostrar TODAS las ramas hacia
        adelante, no solo la primera (bug real: Wurmple solo
        mostraba Silcoon->Beautifly, nunca Cascoon->Dustox -- puede
        haber otros casos de ramificación en ORAS con el mismo
        problema, ej. Gloom->Vileplume/Bellossom, Poliwhirl->
        Poliwrath/Politoed, Slowpoke->Slowbro/Slowking, Snorunt->
        Glalie/Froslass, Kirlia->Gallade, más las 8 ramas de Eevee).

        Arma la cadena así:
        1. Sube por PreEvolutionCatalog desde `species_id` hasta la
           raíz (especie que no evoluciona de ninguna otra) -- esta
           parte SIGUE siendo un camino único hacia atrás (un
           Pokémon evoluciona siempre desde una sola pre-evolución
           en los juegos principales, no hay ramificación posible
           yendo hacia atrás).
        2. Desde `species_id`, arma un ÁRBOL con TODAS las
           evoluciones posibles, hasta 2 saltos más hacia adelante
           por rama.

        Devuelve {"ancestors": [{"speciesId","name",
        "transitionToNext"}, ...], "current": <nodo del árbol
        hacia adelante, ver _build_forward_evolution_node()>}.
        """

        # 1. Ancestros (de la raíz hacia `species_id`, sin incluirlo)
        ancestor_ids = []
        walker_id = species_id
        seen_ids = {species_id}

        while True:
            pre = self.pre_evolution_catalog.get(walker_id)
            if not pre or pre["speciesId"] in seen_ids:
                break
            ancestor_ids.append(pre["speciesId"])
            seen_ids.add(pre["speciesId"])
            walker_id = pre["speciesId"]

        ancestor_ids.reverse()

        # Detalle completo de cada ancestro -- hace falta su propio
        # species_details() para saber CÓMO evoluciona hacia el
        # siguiente eslabón (nivel/objeto/etc.), no solo su nombre.
        details_by_species_id = {species_id: original_details}

        for ancestor_id in ancestor_ids:
            try:
                details_by_species_id[ancestor_id] = (
                    self.modal_bridge.species_details(ancestor_id)
                )
            except Exception:
                details_by_species_id[ancestor_id] = {}

        ancestors = []
        ancestor_chain_ids = ancestor_ids + [species_id]

        for index, stage_id in enumerate(ancestor_ids):
            stage_details = details_by_species_id.get(stage_id, {})
            next_stage_id = ancestor_chain_ids[index + 1]

            evolution_entry = next(
                (
                    evolution
                    for evolution in stage_details.get("evolutions", [])
                    if evolution.get("toSpeciesId") == next_stage_id
                ),
                None,
            )

            ancestors.append({
                "speciesId": stage_id,
                "name": stage_details.get("name") or f"#{stage_id}",
                "transitionToNext": (
                    self._resolve_evolution_transition(evolution_entry)
                    if evolution_entry
                    else None
                ),
            })

        # 2. Árbol hacia adelante desde `species_id`, con todas las
        # ramas -- ver _build_forward_evolution_node().
        current_node = self._build_forward_evolution_node(
            species_id, original_details, 2, seen_ids, species_id
        )

        return {"ancestors": ancestors, "current": current_node}

    def get_species_modal_data(self, species_id):
        """
        Modal "Pokédex" de detalle de especie (GUI v2, roadmap
        07/09/2026, sección 4.2) -- junta las piezas ya confirmadas
        y curadas por separado:

        - Tipo/stats base/habilidades (bridge PKHeX,
          species_details(), ver Program.cs).
        - Cadena de evolución completa (pre-evolución + especie
          actual + evoluciones siguientes) -- ver
          _build_evolution_chain().
        - Resistencias/debilidades/inmunidades -- CÁLCULO LOCAL
          puro a partir del tipo (type_effectiveness.py +
          data/type_chart.json), no un dato para pedirle a nadie.
        - Altura/peso/categoría/descripción -- dataset estático
          curado (SpeciesExtraCatalog), no PKHeX (ver el docstring
          largo en build_species_extra.py para el porqué).

        No necesita memoria del juego -- species_id ya lo tiene el
        frontend (viene de `slot.speciesId`, ya presente en cada
        tarjeta de la página Pokémon desde antes).
        """

        try:
            details = self.modal_bridge.species_details(species_id)
        except Exception as error:
            return {"error": str(error)}

        if "error" in details:
            return details

        effectiveness = compute_effectiveness(
            details.get("type1Key", ""),
            details.get("type2Key", ""),
            self.type_chart_catalog,
        )

        categorized = categorize_effectiveness(effectiveness)

        details["evolutionChain"] = self._build_evolution_chain(
            species_id, details
        )
        details["weaknesses"] = categorized["weaknesses"]
        details["resistances"] = categorized["resistances"]
        details["immunities"] = categorized["immunities"]

        extra = self.species_extra_catalog.get(species_id)
        details["heightM"] = extra["heightM"]
        details["weightKg"] = extra["weightKg"]
        details["genus"] = extra["genus"]
        details["description"] = extra["description"]

        return details

    # -----------------------------------------------------------
    # Página Nuzlocke (GUI v2, 04/09/2026) -- reemplaza el
    # placeholder "Próximamente". A diferencia del panel de
    # siempre (panels/nuzlocke/, que sigue existiendo intacto para
    # quien lo abra directo en el navegador), esta página vive
    # dentro de la app con el mismo estilo visual del resto de la
    # GUI -- pedido explícito del usuario de no depender de un
    # panel aparte.
    #
    # Todo lo que lee esto viene de `self.app.nuzlocke_service`
    # directo (la MISMA instancia que usa Runtime cada 200ms y que
    # usaba HTTPServer para panels/nuzlocke/) -- no hay una copia
    # de datos aparte para la GUI, así que un cambio hecho acá se
    # refleja también si alguien tiene el panel viejo abierto al
    # mismo tiempo, y viceversa.
    # -----------------------------------------------------------

    def get_nuzlocke_page_data(self):
        """
        Todo lo que necesita la página Nuzlocke en una sola
        llamada: resumen, equipo actual (mismo dato que ya lee el
        Dashboard, sin memoria nueva), encuentros, pendientes,
        cementerio, reglas del run, y tiempo de juego real (ver
        PlaytimeService -- viene del archivo de guardado en disco,
        no de la memoria en vivo, así que puede tardar en
        reflejar una sesión larga sin guardar).

        El catálogo de especies/ubicaciones NO viaja acá (son
        ~700/~90 entradas, pesado para pedir en cada poll) -- se
        piden aparte, una sola vez, cuando se abre el modal de
        "Nuevo encuentro"/edición (ver get_species_catalog() /
        get_location_catalog()).
        """

        nuzlocke = self.app.state.nuzlocke or {}

        roster = nuzlocke.get("roster", [])
        graveyard = nuzlocke.get("graveyard", [])
        encounters = nuzlocke.get("encounters", [])
        pending = nuzlocke.get("pending_encounters", [])

        alive_count = len(roster)
        dead_count = len(graveyard)
        total_count = alive_count + dead_count

        unique_species = {
            entry.get("species")
            for entry in (roster + graveyard)
            if entry.get("species")
        }

        survival_rate = (
            round((alive_count / total_count) * 100, 1)
            if total_count > 0
            else 0
        )

        stats = {
            "alive": alive_count,
            "dead": dead_count,
            "encountersCount": len(encounters),
            "uniqueSpecies": len(unique_species),
            "captures": total_count,
            "survivalRate": survival_rate,
        }

        # Pestaña Líderes + tarjeta "líder siguiente" de Seguimiento
        # (Fase B, roadmap 3.1/3.2/3.3) -- ver
        # _gym_leaders_with_earned(), compartido con
        # get_leader_team_window_data() (misma cuenta, no
        # duplicada).
        gym_leaders = self._gym_leaders_with_earned()

        # None si ya se obtuvieron las 8 medallas -- el frontend lo
        # trata como "sin líder pendiente" en vez de romper.
        next_leader = next(
            (leader for leader in gym_leaders if not leader["earned"]),
            None,
        )

        return {
            "team": self.app.state.team or [],
            "roster": roster,
            "graveyard": graveyard,
            "encounters": encounters,
            "pendingEncounters": pending,
            "ruleset": self.app.nuzlocke_service.get_ruleset(),
            "playtime": self.playtime_service.get_playtime(
                self.app.reader.process_name
            ),
            "stats": stats,
            "gymLeaders": gym_leaders,
            "nextLeader": next_leader,
        }

    def _active_gym_leader_catalog(self):
        """
        Decide en el momento (leyendo config.json cada vez, no una
        sola vez al arrancar) si usar el catálogo vanilla o el del
        hackroom -- ver la corrección del 09/09/2026 junto a
        self.gym_leader_catalog en __init__ (el toggle de
        Configuración ahora surte efecto sin reiniciar DexRelay).
        """

        if self.app.config.get("hackroom", "enabled", default=False):
            return self.gym_leader_catalog_hackroom

        return self.gym_leader_catalog

    def _gym_leaders_with_earned(self):
        """
        Los 8 líderes del catálogo (`GymLeaderCatalog.list_all()`)
        con `earned` (bool) agregado, cruzando `leader.order`
        contra el bitfield de medallas actual. `badges` se
        normaliza con el mismo placeholder honesto que
        `get_dashboard_data()` -- todavía puede no haber ninguna
        lectura exitosa en esta sesión (recién conectando).

        Compartido entre `get_nuzlocke_page_data()` (pestaña
        Líderes + tarjeta "líder siguiente") y
        `get_leader_team_window_data()` (ventana nativa de detalle
        de equipo, Fase B 06/09/2026) -- un solo lugar calcula
        `earned`, nadie más lo recalcula por su cuenta.
        """

        badges = self.app.state.badges

        if not isinstance(badges, dict):
            badges = {"value": 0, "count": 0, "badges": [False] * 8}

        badge_flags = badges.get("badges") or [False] * 8

        gym_leaders = []

        for leader in self._active_gym_leader_catalog().list_all():
            index = (leader.get("order") or 0) - 1
            earned = 0 <= index < len(badge_flags) and bool(
                badge_flags[index]
            )
            gym_leaders.append({**leader, "earned": earned})

        return gym_leaders

    # -----------------------------------------------------------
    # Ventana nativa: detalle de equipo de un líder (Fase B,
    # 06/09/2026, a pedido del usuario -- reemplaza al modal
    # movible original). A diferencia de un modal HTML, esto abre
    # una ventana de sistema operativo real vía
    # `webview.create_window()`: se pueden abrir varias a la vez
    # (una por líder) y cada una se puede mover fuera de los
    # límites de la ventana principal. Vive en su propia página
    # standalone (`leader_team_window.html`/`leader_team_window.js`),
    # que NO comparte el bundle de `app.js` ni el poll de 2s de la
    # página Nuzlocke -- pide su dato una sola vez al abrir.
    # -----------------------------------------------------------

    def open_leader_team_window(self, order):
        """
        Crea la ventana nueva. El título ya viene resuelto acá
        (nombre en español del líder) para que la barra de tareas/
        título de la ventana sea legible desde el primer instante,
        en vez de mostrar un genérico "Cargando..." hasta que la
        página termine de pedir sus propios datos.
        """

        leader = self._resolve_leader_for_window(order)

        if leader:
            leader_name = leader.get("nameEs") or leader.get("name") or "líder"
        else:
            leader_name = "líder"

        title = "Equipo de " + leader_name

        window_path = (
            paths.base_dir() / "app" / "gui_web" / "web" / "leader_team_window.html"
        )

        webview.create_window(
            title,
            url=str(window_path) + "?order=" + str(order),
            js_api=self,
            width=880,
            height=640,
            min_size=(480, 360),
            background_color="#0a0e18",
        )

    def get_leader_team_window_data(self, order):
        """
        Datos para `leader_team_window.html` -- se pide una sola
        vez al abrir la ventana (ver docstring de la sección de
        arriba), no en un poll continuo como el resto de la GUI.
        """

        return self._resolve_leader_for_window(order)

    def _resolve_leader_for_window(self, order):
        try:
            order = int(order)
        except (TypeError, ValueError):
            return None

        for leader in self._gym_leaders_with_earned():
            if leader.get("order") == order:
                return leader

        return None

    def get_species_catalog(self):
        """Lista completa {id, name} -- se pide una sola vez, se cachea en JS."""

        return self.species_catalog.list_all()

    def get_location_catalog(self):
        """Lista completa {id, name} -- se pide una sola vez, se cachea en JS."""

        return self.location_catalog.list_all()

    def nuzlocke_save_encounter(
        self,
        location,
        nickname,
        species,
        status,
        origin=None,
        shiny=None,
    ):
        """
        "Nuevo encuentro" / editar una fila existente a mano.
        Delega entero en NuzlockeService.save_encounter() -- ver su
        docstring para el significado de cada campo. Devuelve la
        lista de encuentros actualizada, o {"error": str(e)} si la
        validación del servicio falla (estado/origen inválido) --
        el frontend lo muestra tal cual en vez de romper la
        página.
        """

        try:
            return self.app.nuzlocke_service.save_encounter(
                location,
                nickname,
                species,
                status,
                origin=origin,
                shiny=shiny,
            )
        except ValueError as error:
            return {"error": str(error)}

    def nuzlocke_delete_encounter(self, location):
        """
        Botón de borrar una fila. "Inicial" está protegida por el
        propio servicio (ValueError) -- se devuelve como
        {"error": ...} en vez de dejar que la excepción rompa el
        puente JS<->Python.
        """

        try:
            return self.app.nuzlocke_service.delete_encounter(
                location
            )
        except ValueError as error:
            return {"error": str(error)}

    def nuzlocke_discard_pending(self, nickname):
        try:
            return self.app.nuzlocke_service.discard_pending_encounter(
                nickname
            )
        except ValueError as error:
            return {"error": str(error)}

    def nuzlocke_assign_special(self, nickname, origin):
        """
        "¿Pokémon Especial?" -- asigna un origen a una captura
        pendiente (shiny/huevo/intercambio/evento/regalo/fosil/
        captura_extra, ver NuzlockeService.VALID_ORIGINS +
        assign_special_origin()). Devuelve
        {"encounters": [...], "pendingEncounters": [...]}
        actualizados.
        """

        try:
            result = self.app.nuzlocke_service.assign_special_origin(
                nickname, origin
            )
        except ValueError as error:
            return {"error": str(error)}

        return {
            "encounters": result["encounters"],
            "pendingEncounters": result["pending_encounters"],
        }

    def nuzlocke_reset_all(self):
        return self.app.nuzlocke_service.reset_all()

    def nuzlocke_get_ruleset(self):
        return self.app.nuzlocke_service.get_ruleset()

    def nuzlocke_save_ruleset(self, ruleset):
        try:
            return self.app.nuzlocke_service.save_ruleset(ruleset)
        except ValueError as error:
            return {"error": str(error)}

    def get_server_base_url(self):
        host = self.app.http_server.host
        port = self.app.http_server.port
        return f"http://{host}:{port}"

    def get_github_url(self):
        return GITHUB_URL

    def get_issues_url(self):
        return ISSUES_URL

    # -----------------------------------------------------------
    # Página Configuración (GUI v2, Bloque 5, 05/09/2026)
    #
    # Alcance decidido con el usuario: solo lo que hoy tiene un
    # dato o una acción real detrás -- conexión/servidor/refresco
    # (ya existían en config.json y se editaban a mano en la GUI
    # Tkinter vieja, app/gui/main_window.py, sección
    # "CONFIGURACIÓN"; acá es la misma validación, migrada), más
    # limpieza de caché real e información de la app. Todo lo demás
    # del mockup original (auto-inicio con Windows, buscador de
    # actualizaciones, exportar/importar config, idioma) queda
    # afuera a propósito -- no hay backend real detrás de ninguno
    # de esos hoy, y este proyecto no simula funcionalidad que no
    # existe (mismo criterio que "FPS del juego"/"Memoria base" del
    # Dashboard).
    # -----------------------------------------------------------

    def get_settings_page_data(self):
        config = self.app.config

        return {
            "server": {
                "host": config.get("server", "host", default="127.0.0.1"),
                "port": config.get("server", "port", default=8080),
            },
            "realtime": {
                "refresh_ms": config.get(
                    "realtime", "refresh_ms", default=200
                ),
            },
            "hackroom": {
                "enabled": config.get(
                    "hackroom", "enabled", default=False
                ),
            },
            "appVersion": resolve_app_version(),
            "githubUrl": GITHUB_URL,
            "issuesUrl": ISSUES_URL,
        }

    def save_connection_settings(self, host, port, refresh_ms):
        """
        Guarda host/puerto/refresco en config.json (mismas tres
        claves que ya editaba la GUI Tkinter vieja). Misma
        limitación de siempre: no hay hot-reload, `Application` ya
        arrancó con los valores anteriores -- el cambio recién se
        nota reiniciando DexRelay entero. Devuelve
        `{"success": True}` o `{"error": str}` sin guardar nada si
        la validación falla, igual que el resto de los métodos de
        este puente que pueden fallar por datos del usuario.
        """

        host = (host or "").strip()

        if not host:
            return {"error": "El host no puede estar vacío."}

        try:
            port = int(port)
        except (TypeError, ValueError):
            return {"error": "El puerto tiene que ser un número entero."}

        if not (1 <= port <= 65535):
            return {"error": "El puerto tiene que estar entre 1 y 65535."}

        try:
            refresh_ms = int(refresh_ms)
        except (TypeError, ValueError):
            return {
                "error": "El refresco tiene que ser un número entero de milisegundos."
            }

        if refresh_ms < 10:
            return {
                "error": "El refresco mínimo es 10 ms -- valores más bajos no dejan margen real entre lecturas."
            }

        config = self.app.config
        config.set("server", "host", value=host)
        config.set("server", "port", value=port)
        config.set("realtime", "refresh_ms", value=refresh_ms)
        config.save()

        return {"success": True}

    def save_hackroom_setting(self, enabled):
        """
        Toggle "Modo hack: Rising Ruby/Sinking Sapphire" (Fase E,
        09/09/2026, decisión del usuario -- ver el comentario junto
        a self.gym_leader_catalog en __init__).

        CORRECCIÓN (09/09/2026, a pedido del usuario): surte efecto
        de inmediato, sin reiniciar DexRelay -- _active_gym_leader_
        catalog() lee este valor de config.json en cada pedido, no
        una sola vez al arrancar. Los dos catálogos (vanilla y
        hackroom) ya están cargados en memoria de antes, así que no
        hay ningún retraso extra al tildar/destildar.
        """

        config = self.app.config
        config.set("hackroom", "enabled", value=bool(enabled))
        config.save()

        return {"success": True}

    def reset_connection_settings(self):
        """
        "Restablecer" de la página Configuración. Vuelve host/
        puerto/refresco a los mismos defaults que usa
        `Application.__init__()` -- no a algo inventado a mano acá
        por separado (ver DEFAULT_CONNECTION_SETTINGS). No toca
        `azahar.process_name` (no se expone en esta página, ver
        docstring de la sección).
        """

        config = self.app.config
        config.set(
            "server", "host", value=DEFAULT_CONNECTION_SETTINGS["host"]
        )
        config.set(
            "server", "port", value=DEFAULT_CONNECTION_SETTINGS["port"]
        )
        config.set(
            "realtime",
            "refresh_ms",
            value=DEFAULT_CONNECTION_SETTINGS["refresh_ms"],
        )
        config.save()

        return dict(DEFAULT_CONNECTION_SETTINGS)

    # Archivos de caché reales que existen hoy en data/ -- lista
    # explícita, no un glob sobre toda la carpeta, para no borrar
    # nunca por accidente algo que no sea caché regenerable
    # (badges.json, nuzlocke_*.json y team_overlay_settings.json
    # son progreso/preferencias reales del usuario, jamás entran
    # acá).
    _CLEARABLE_CACHE_FILES = (
        "species_cache.json",
        "location_cache.json",
    )

    def clear_data_cache(self):
        """
        Borra los archivos de caché en disco listados arriba --
        `SpeciesCatalog`/`LocationCatalog` los vuelven a generar
        solos pidiéndole la lista al bridge PKHeX la próxima vez
        que haga falta (ver sus docstrings). Devuelve la lista de
        archivos que efectivamente estaban y se borraron -- puede
        ser una lista vacía si ya no había caché en disco, eso no
        es un error.

        Limitación real, no oculta: las instancias de
        SpeciesCatalog/LocationCatalog que YA están corriendo en
        memoria (acá en Api, y las de HTTPServer) no se enteran
        solas de que el archivo desapareció -- si ya habían
        resuelto la lista una vez en esta sesión, la siguen
        sirviendo desde memoria hasta que DexRelay se reinicie.
        Borrar el archivo es útil sobre todo para forzar una
        relectura limpia en el PRÓXIMO arranque.
        """

        cleared = []

        for filename in self._CLEARABLE_CACHE_FILES:
            cache_path = paths.path("data", filename)

            try:
                cache_path.unlink()
                cleared.append(filename)
            except FileNotFoundError:
                continue

        return {"cleared": cleared}

    # -----------------------------------------------------------
    # Página Logs (GUI v2, Bloque 5, 06/09/2026)
    #
    # Alcance real, mismo criterio que Configuración: DexRelay no
    # tiene un módulo `logging`, solo `print()` (ver
    # app/core/log_capture.py para el detalle completo). Esta
    # página muestra el buffer real de stdout/stderr -- no hay
    # "Nivel"/"Fuente" por línea, ni gráfico de niveles, ni filtro
    # por fecha, porque ninguno de esos datos existe hoy detrás.
    # -----------------------------------------------------------

    def get_logs(self):
        """
        Devuelve el buffer completo actual (hasta
        `log_capture.MAX_LOG_LINES` líneas, las más recientes al
        final) -- se pide entero en cada poll de la página Logs
        (app.js decide qué hacer con las líneas nuevas respecto de
        la última vez, ver `pollLogsPage()`), no incremental por
        `id` -- 500 líneas de texto corto no justifican esa
        complejidad extra todavía.
        """

        return log_capture.buffer.get_all()

    def clear_logs(self):
        """
        Botón "Limpiar" de la página Logs. Vacía el buffer en
        memoria -- no borra nada de disco (no hay ningún archivo de
        log hoy, todo vive en RAM mientras DexRelay corre, ver
        `log_capture.LogBuffer`).
        """

        log_capture.buffer.clear()
        return True

    def open_external(self, url: str):
        """Abre una URL en el navegador del sistema, no en la ventana."""

        webbrowser.open(url)
        return True

    # -----------------------------------------------------------
    # Página Herramientas (07/09/2026) -- primera función de
    # ESCRITURA de memoria de DexRelay (todo lo demás en la app es
    # solo lectura). Ver Documento Maestro de esta sesión y
    # app/memory/pointers.py (sección "BOLSA DE ITEMS") para el
    # detalle completo de cómo se confirmó la dirección/estructura.
    # La lógica real vive en BagService, compartida con
    # tools/probes/memory/escribir_item_bolsa.py -- acá solo se
    # traduce el resultado a algo que el frontend pueda mostrar.
    # -----------------------------------------------------------

    def get_herramientas_page_data(self):
        """
        Estado inicial de la página: si Azahar está conectado (la
        página deshabilita el botón y muestra un aviso si no).
        Confirmada en vivo contra las dos versiones (Alpha Sapphire
        y Omega Ruby, 07/09/2026) -- no hace falta avisar sobre
        versión distinta como al principio.
        """

        state = self.app.state

        return {
            "connected": bool(state.azahar_connected),
        }

    def add_rare_candy(self, cantidad):
        """
        Agrega Caramelo Raro (item_id=50, confirmado contra la
        tabla oficial de índices de Bulbapedia para Generación VI)
        a la bolsa. Devuelve `{"ok": True, "new_quantity": N}` o
        `{"error": "mensaje"}` -- nunca lanza una excepción hacia
        el frontend, BagWriteError ya viene con un mensaje legible.
        """

        try:
            cantidad = int(cantidad)
        except (TypeError, ValueError):
            return {"error": "Cantidad inválida."}

        try:
            result = BagService(self.app.reader).add_medicine_item(
                RARE_CANDY_ITEM_ID, cantidad
            )
        except BagWriteError as error:
            return {"error": str(error)}

        return {"ok": True, "new_quantity": result["new_quantity"]}

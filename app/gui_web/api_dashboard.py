"""
Bienvenida, Espera/Conexión, Dashboard (control de Runtime/HTTP/Reader), assets
embebidos y editor del Team Overlay.

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations

import base64
import time

from app.core import paths
from app.core.version import get_app_version as resolve_app_version
from app.memory.pointers import (
    PROCESS_NAME_ALPHA_SAPPHIRE,
    PROCESS_NAME_OMEGA_RUBY,
)


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
        "avatar": "avatar_alpha_sapphire.jpg",
    },
    {
        "label": "Omega Ruby",
        "process_name": PROCESS_NAME_OMEGA_RUBY,
        "badge": "OR",
        "background": "bg_omega_ruby.jpg",
        "avatar": "avatar_omega_ruby.jpg",
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


class DashboardMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

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

    def get_game_avatars(self):
        """
        Bloque 7 (24/09/2026): foto de perfil del sidebar (arte del
        juego de la partida) -- recorte circular-friendly de 160x160
        de cada juego (assets/ui/avatar_*.jpg), como data URI por
        `process_name`. Un archivo faltante da `None` para ese juego
        (el frontend muestra un círculo neutro).
        """

        return {
            game["process_name"]: self._asset_data_uri(
                "ui", game["avatar"], mime="image/jpeg"
            )
            for game in GAME_VERSIONS
        }

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
            "ui", "dexrelay_logo.svg", mime="image/svg+xml"
        )

    def get_mark_data_uri(self):
        """
        Solo la marca (isotipo cuadrado, sin el texto) -- para el
        sidebar (34px / 28px colapsado), donde el logo completo
        apaisado no entra. Mismo criterio que get_logo_data_uri().
        """

        return self._asset_data_uri(
            "ui", "dexrelay_mark.svg", mime="image/svg+xml"
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

    def get_connection_diagnosis(self):
        """
        Bloque 6.2 (23/09/2026): pista sobre por qué la pantalla de
        Espera no conecta, a partir de lo que Azahar REALMENTE
        contesta (ver AzaharReader.diagnose_connection()). Lo
        consulta la GUI solo después de un rato esperando (no en
        cada poll de 400ms: cada llamada puede costar hasta 2s de
        timeout de socket).

        Devuelve {"state", "hint", "processes"?}. `hint` es texto
        listo para mostrar; `None` si el estado es "hay juego" (no
        hace falta ninguna pista, la conexión ya está por darse).
        No inventa causas: cuando dos casos no se pueden distinguir
        desde acá (Azahar cerrado vs. interfaz UDP deshabilitada),
        el texto nombra las dos.
        """

        reader = self.app.reader
        result = reader.diagnose_connection()
        state = result.get("state")

        if state == reader.DIAG_NO_LISTENER:
            hint = (
                "Nada responde en el puerto 45987. Comprueba que "
                "Azahar esté abierto y que su interfaz de "
                "depuración por UDP (servidor RPC) esté habilitada."
            )
        elif state == reader.DIAG_TIMEOUT:
            hint = (
                "Azahar no contestó a tiempo. Puede estar cargando; "
                "si sigue igual, ciérralo y ábrelo de nuevo."
            )
        elif state == reader.DIAG_NO_GAME:
            hint = (
                "Azahar responde, pero todavía no hay ningún juego "
                "compatible en ejecución. Carga Pokémon Omega Ruby o "
                "Alpha Sapphire y espera a estar dentro de la partida."
            )
        elif state == reader.DIAG_ERROR:
            hint = (
                "No se pudo hablar con Azahar: "
                f"{result.get('detail') or 'error desconocido'}."
            )
        else:
            hint = None

        return {
            "state": state,
            "hint": hint,
            "processes": result.get("processes"),
        }

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
            # Bloque 5 (24/09/2026): partida cargada ({"tid", "sid",
            # "ot"}) o None si todavía no se identificó.
            "trainer": state.trainer,
            # Bloque 9.1 (30/09/2026): salud del ciclo realtime.
            "runtime_health": self._runtime_health(),
            # Capturas sin ruta asignada: el frontend avisa con un
            # toast cuando aparece una nueva, esté en la página que
            # esté (Bloque 7.2).
            "pending_captures": [
                {
                    "nickname": pending.get("nickname"),
                    "species": pending.get("species"),
                }
                for pending in nuzlocke.get("pending_encounters", [])
                if isinstance(pending, dict)
            ],
        })

        return fields

    def _runtime_health(self):
        """
        Bloque 9.1 (30/09/2026): salud del ciclo realtime para
        Dashboard y Logs. Todo sale de datos reales que escribe
        `Application._run_one_cycle()` en `ApplicationState`;
        `last_cycle_ok_seconds_ago` se calcula acá (reloj de pared)
        para que el frontend no dependa de la hora de su propio
        reloj. None = todavía no hubo un ciclo exitoso.
        """

        state = self.app.state
        last_ok = state.last_cycle_ok_at
        last_error = state.last_error

        return {
            "last_cycle_ok_seconds_ago": (
                None if last_ok is None else max(0.0, time.time() - last_ok)
            ),
            "transient_errors": state.transient_error_count,
            "bug_errors": state.bug_error_count,
            "last_error": (
                None
                if last_error is None
                else {
                    "kind": last_error["kind"],
                    "type": last_error["type"],
                    "message": last_error["message"],
                    "seconds_ago": max(0.0, time.time() - last_error["at"]),
                }
            ),
        }

    def get_runtime_health(self):
        """Salud del ciclo realtime (ver `_runtime_health()`)."""

        return {
            "runtime_running": self.app.runtime_running,
            **self._runtime_health(),
        }

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

    def get_server_base_url(self):
        host = self.app.http_server.host
        port = self.app.http_server.port
        return f"http://{host}:{port}"

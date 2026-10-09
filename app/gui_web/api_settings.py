"""
Configuración, Logs y enlaces externos.

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations

import webbrowser
from datetime import datetime

import webview

from app.core import log_capture, paths
from app.core.version import get_app_version as resolve_app_version


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


class SettingsMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

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
                # Bloque 13: False si el juego conectado no lo soporta.
                "available": self._hackroom_available(),
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

    def save_logs_to_file(self, text: str):
        """
        Bloque 8.3 (30/09/2026): botón "Guardar como .txt" de la
        página Logs -- decisión del usuario: solo exportación
        manual, sin archivo rotativo en disco (`logs/dexrelay.log`
        queda descartado). Abre el selector nativo de "Guardar
        como" de pywebview y escribe el texto completo (ya armado
        en app.js a partir del buffer) tal cual, sin tocar nada de
        `log_capture`.
        """

        default_name = "dexrelay_logs_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"

        result = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=default_name,
            file_types=("Archivos de texto (*.txt)", "Todos los archivos (*.*)"),
        )

        if not result:
            return {"saved": False}

        # pywebview devuelve un string en algunas plataformas y una
        # tupla/lista de un elemento en otras -- normalizar acá en
        # vez de asumir un solo formato.
        path = result[0] if isinstance(result, (list, tuple)) else result

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

        return {"saved": True, "path": str(path)}

    def open_external(self, url: str):
        """Abre una URL en el navegador del sistema, no en la ventana."""

        webbrowser.open(url)
        return True

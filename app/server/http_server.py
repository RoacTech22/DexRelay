from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread

from app.core import paths
from app.core.state import ApplicationState
from app.services.location_catalog import LocationCatalog
from app.services.nuzlocke_service import NuzlockeService
from app.services.species_catalog import SpeciesCatalog


# Errores esperados cuando el navegador (o el Browser Source de
# OBS) cierra o recarga una conexión keep-alive a medio camino.
# No son un bug del servidor -- son tráfico normal de HTTP/1.1
# keep-alive. Sin filtrarlos, socketserver imprime un traceback
# completo por cada desconexión de este tipo, aunque el overlay
# siga funcionando bien.
_EXPECTED_DISCONNECT_ERRORS = (
    ConnectionAbortedError,
    ConnectionResetError,
    BrokenPipeError,
)


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    """
    ThreadingHTTPServer que no imprime traceback para
    desconexiones de cliente esperadas (ver
    _EXPECTED_DISCONNECT_ERRORS). handle_error() es un método del
    SERVIDOR (no del request handler) -- ThreadingMixIn.process_request_thread
    lo llama sobre self (el servidor) cuando finish_request()
    lanza una excepción. Cualquier otro error se reporta
    normalmente.
    """

    def handle_error(self, request, client_address):
        exception_type = sys.exc_info()[0]

        if exception_type in _EXPECTED_DISCONNECT_ERRORS:
            return

        super().handle_error(
            request,
            client_address,
        )


class HTTPServer:
    """Servidor HTTP de DexRelay."""

    def __init__(
        self,
        state: ApplicationState,
        host: str = "127.0.0.1",
        port: int = 8080,
        nuzlocke_service: NuzlockeService | None = None,
        species_catalog: SpeciesCatalog | None = None,
        location_catalog: LocationCatalog | None = None,
        team_overlay_settings: "TeamOverlaySettings | None" = None,
    ) -> None:
        self.state = state
        self.host = host
        self.port = port
        self.nuzlocke_service = nuzlocke_service
        self.species_catalog = species_catalog
        self.location_catalog = location_catalog
        self.team_overlay_settings = team_overlay_settings

        # Modo desarrollo: raíz del proyecto (igual que antes). En
        # un build empaquetado: la carpeta del .exe, donde
        # overlays/ y panels/ tienen que estar copiados al lado
        # (--add-data de PyInstaller) -- ver app/core/paths.py.
        project_root = paths.base_dir()

        # /overlay/* -- vistas para OBS (Browser Source):
        # transparentes, de solo lectura, pensadas para verse en
        # stream.
        self.overlay_directory = (
            project_root / "overlays"
        )

        # /panel/* -- páginas de control interactivas (ej. carga
        # manual de encuentros del Nuzlocke Tracker). No son para
        # OBS: son para que el usuario las abra en su propio
        # navegador mientras juega. Sirven como sustituto liviano
        # de la GUI hasta que exista (FASE 4).
        self.panel_directory = (
            project_root / "panels"
        )

        # Set completo de sprites (GUI v2, Bloque 3, página Pokémon
        # -- 03/09/2026, provisto por el usuario). Carpeta APARTE
        # de overlays/team/sprites/ a propósito -- ese set sigue
        # sirviendo al Team Overlay y al Dashboard tal cual, sin
        # tocarlo, para no arriesgar algo que ya funciona bien ahí.
        # Curado a partir de ~1300 sprites con variantes (Mega/
        # Gigantamax/regionales/etc.) -- se quedó solo con la forma
        # base de cada especie 1-721 (rango de ORAS/Gen 6, no hace
        # falta más) y se reescalaron a 200px máx (originales hasta
        # 1280x1280, pesaban 350MB en total -- no tiene sentido para
        # algo que se muestra a 96px).
        self.pokemon_sprites_directory = (
            project_root / "assets" / "pokemon_full"
        )

        # Retratos de los 8 líderes de gimnasio de Hoenn (GUI v2,
        # Bloque 3, página Medallas -- 04/09/2026, provistos por el
        # usuario). Nombrados 1.png-8.png en el mismo orden que el
        # bitfield de badges_service.py (1=Alana/Roxanne ...
        # 8=Plubio/Wallace) -- mismo criterio que
        # overlays/badges/sprites/. Versión ORAS (arte oficial más
        # reciente, no la de Ruby/Sapphire/Emerald) elegida por
        # sobre la alternativa que mandó el usuario para cada líder.
        self.gym_leaders_directory = (
            project_root / "assets" / "gym_leaders"
        )

        # Sprites estilo Pokémon Shuffle (05/09/2026, provistos por
        # el usuario) -- SOLO para la tabla "Encuentros por Ruta"
        # de la página Nuzlocke de la GUI, a pedido explícito
        # ("solo en esa sección"). Carpeta y ruta aparte de
        # assets/pokemon_full/ y overlays/team/sprites/ a
        # propósito, mismo criterio que esas dos: no tocar un set
        # que ya funciona bien en otro lado. Curado de un pack de
        # ~1300 con variantes (mega/regionales/etc.) a solo las
        # formas base (nombre "NNN.png", 3 dígitos, sin sufijo) --
        # 801 sprites, IDs 001-802.
        self.pokemon_shuffle_sprites_directory = (
            project_root / "assets" / "pokemon_shuffle"
        )

        # Íconos de ítem (07/09/2026, roadmap 4.2 -- modal de
        # evolución, varios de los 33 methodKey confirmados
        # necesitan mostrar el objeto puntual) -- descargados por
        # tools/data_curation/download_item_sprites.py desde el
        # repo PokeAPI/sprites (mismo ecosistema ya usado para
        # datos de movimientos/habilidades/ítems, licencia ISC).
        # Nombrados "{id}.png" por id numérico de PokéAPI.
        #
        # BUG REAL encontrado y corregido (09/09/2026, reportado
        # por el usuario: "Roca del Rey... me sale el sprite de
        # Pico Afilado"): el comentario de arriba decía "mismo id
        # que ya devuelve item_list() del bridge" -- ESO ERA FALSO.
        # El id de PokéAPI y el índice real del ítem en el juego
        # (el que usa item_list()/item_cache.json/RARE_CANDY_ITEM_ID)
        # son DOS numeraciones distintas que coinciden para muchos
        # ítems tempranos pero divergen para otros (confirmado:
        # índice real 221 = "Roca del Rey", pero sprite 221.png se
        # descargó como id de PokéAPI 221 = "sharp-beak"/Pico
        # Afilado). Ver item_sprite_id_map (cargado más abajo) y
        # tools/data_curation/build_item_sprite_id_map.py para el
        # mapeo real, construido desde item_game_indices.csv de
        # PokéAPI (la tabla que existe justamente para esta
        # traducción). Sin ese archivo generado, el mapeo queda
        # vacío y se sirve el id tal cual (comportamiento viejo,
        # con el bug).
        self.item_sprites_directory = (
            project_root / "assets" / "items"
        )
        self.item_sprite_id_map = self._load_item_sprite_id_map(
            project_root
        )
        # Artwork oficial de especie (07/09/2026, roadmap 4.2 --
        # modal Pokédex, a diferencia del ícono chico ya usado en
        # el resto de la app) -- descargado por
        # tools/data_curation/download_species_artwork.py desde
        # PokeAPI/sprites, carpeta "official-artwork". Nombrado
        # "{speciesId}.png", mismo criterio que item_sprites.
        self.species_artwork_directory = (
            project_root / "assets" / "species_artwork"
        )

        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

        # Contador de conexiones activas (GUI v2, página Overlays,
        # 05/09/2026) -- cada socket TCP abierto por un cliente
        # (Browser Source de OBS con un overlay, o el panel web
        # abierto a mano) incrementa este contador al conectar y lo
        # decrementa al cerrar, vía Handler.setup()/finish() más
        # abajo. Con HTTP/1.1 keep-alive (ver protocol_version en
        # el Handler), una pestaña de overlay abierta mantiene su
        # conexión viva entre polls en vez de abrir una nueva cada
        # vez, así que este número refleja clientes realmente
        # conectados ahora mismo, no peticiones por segundo. Lock
        # porque cada conexión corre en su propio hilo
        # (ThreadingHTTPServer).
        self._active_connections = 0
        self._active_connections_lock = Lock()

    def _increment_connections(self) -> None:
        with self._active_connections_lock:
            self._active_connections += 1

    def _decrement_connections(self) -> None:
        with self._active_connections_lock:
            self._active_connections = max(0, self._active_connections - 1)

    def get_active_connections(self) -> int:
        """Clientes con una conexión TCP abierta ahora mismo (0 si el servidor está detenido)."""

        if self._server is None:
            return 0

        with self._active_connections_lock:
            return self._active_connections

    def start(self) -> None:
        """Inicia el servidor HTTP en un hilo separado."""

        if self._server is not None:
            return

        # Reiniciar el contador: si el servidor se detuvo con
        # conexiones abiertas (finish() no llegó a correr para
        # todas, ej. cierre abrupto), no debe arrastrar un número
        # inflado a la sesión nueva.
        with self._active_connections_lock:
            self._active_connections = 0

        server = _QuietThreadingHTTPServer(
            (self.host, self.port),
            self._create_handler(),
        )

        # El backlog por defecto de socketserver es muy bajo (5).
        # Con varias imágenes + el polling de /api/team pidiendo
        # conexión casi al mismo tiempo, conviene dejar más margen
        # para que el sistema operativo no rechace/demore conexiones
        # entrantes mientras el servidor procesa las anteriores.
        server.request_queue_size = 32

        self._server = server

        self._thread = Thread(
            target=server.serve_forever,
            name="DexRelayHTTP",
            daemon=True,
        )

        self._thread.start()

        print(
            f"HTTP Server iniciado en "
            f"http://{self.host}:{self.port}"
        )

    def stop(self) -> None:
        """Detiene el servidor HTTP."""

        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()

        self._server = None
        self._thread = None

        print("HTTP Server detenido.")

    def _load_item_sprite_id_map(self, project_root):
        """
        Carga data/item_sprite_id_map.json ({indice_real_del_juego:
        id_de_pokeapi}, ver tools/data_curation/
        build_item_sprite_id_map.py) -- traduce el id que usa el
        resto de DexRelay (índice real del ítem en el juego) al id
        que realmente tienen los archivos de sprite en disco (id de
        PokéAPI), ver el comentario largo junto a
        self.item_sprites_directory para el bug real que esto
        corrige.

        Si el archivo no existe todavía (no se corrió el script de
        curación, requiere red) devuelve un dict vacío -- se sigue
        sirviendo el id tal cual, mismo comportamiento que antes de
        este fix, en vez de romper el server entero por un dataset
        opcional faltante.
        """

        map_path = project_root / "data" / "item_sprite_id_map.json"

        if not map_path.exists():
            return {}

        try:
            with open(map_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}

    def _create_handler(self):
        """Crea el handler HTTP."""

        state = self.state
        overlay_directory = self.overlay_directory
        panel_directory = self.panel_directory
        pokemon_sprites_directory = self.pokemon_sprites_directory
        gym_leaders_directory = self.gym_leaders_directory
        pokemon_shuffle_sprites_directory = self.pokemon_shuffle_sprites_directory
        item_sprites_directory = self.item_sprites_directory
        item_sprite_id_map = self.item_sprite_id_map
        species_artwork_directory = self.species_artwork_directory
        nuzlocke_service = self.nuzlocke_service
        species_catalog = self.species_catalog
        location_catalog = self.location_catalog
        team_overlay_settings = self.team_overlay_settings
        http_server_ref = self

        class Handler(BaseHTTPRequestHandler):

            # HTTP/1.1 habilita keep-alive: el navegador puede
            # reutilizar la misma conexión TCP para varias
            # peticiones seguidas, en vez de abrir una conexión
            # nueva por cada imagen/JSON. Sin esto, con HTTP/1.0
            # (el valor por defecto de BaseHTTPRequestHandler),
            # el límite de ~6 conexiones simultáneas por origen
            # que impone el navegador se agota rápido cuando hay
            # 6 sprites + el polling de /api/team compitiendo por
            # conexión al mismo tiempo, y las últimas peticiones
            # se quedan esperando un slot libre indefinidamente.
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                http_server_ref._increment_connections()

            def finish(self):
                # try/finally: si super().finish() lanza (mismo tipo
                # de desconexión de cliente a medio camino que ya
                # maneja _QuietThreadingHTTPServer.handle_error()),
                # el contador igual tiene que bajar -- si no, una
                # conexión cortada abruptamente queda contada para
                # siempre como "activa".
                try:
                    super().finish()
                finally:
                    http_server_ref._decrement_connections()

            def do_GET(self):
                if self.path == "/":
                    self._send_text(
                        "DexRelay HTTP Server",
                        200,
                    )
                    return

                if self._serve_overlay("team"):
                    return

                if self._serve_overlay("badges"):
                    return

                if self._serve_overlay("nuzlocke"):
                    return

                if self._serve_panel("nuzlocke"):
                    return

                if self._serve_pokemon_sprite():
                    return

                if self._serve_gym_leader_sprite():
                    return

                if self._serve_pokemon_shuffle_sprite():
                    return

                if self._serve_item_sprite():
                    return

                if self._serve_species_artwork():
                    return

                if self.path == "/api/status":
                    self._send_json(
                        {
                            "azahar_connected": (
                                state.azahar_connected
                            ),
                            "reader_active": (
                                state.reader_active
                            ),
                        },
                        200,
                    )
                    return

                if self.path == "/api/team":
                    self._send_json(
                        state.team,
                        200,
                    )
                    return

                if self.path == "/api/team-overlay-settings":
                    settings = (
                        team_overlay_settings.get()
                        if team_overlay_settings is not None
                        else {}
                    )
                    self._send_json(
                        settings,
                        200,
                    )
                    return

                if self.path == "/api/badges":
                    self._send_json(
                        state.badges,
                        200,
                    )
                    return

                if self.path == "/api/combat":
                    self._send_json(
                        {
                            "active": state.combat_active,
                            "hp": state.combat_hp,
                        },
                        200,
                    )
                    return

                if self.path == "/api/nuzlocke":
                    self._send_json(
                        state.nuzlocke,
                        200,
                    )
                    return

                if self.path == "/api/nuzlocke/encounters":

                    if nuzlocke_service is None:
                        self._send_json(
                            {"encounters": []},
                            200,
                        )
                        return

                    self._send_json(
                        {
                            "encounters": (
                                nuzlocke_service
                                .get_encounters()
                            )
                        },
                        200,
                    )
                    return

                if self.path == "/api/nuzlocke/pending-encounters":

                    if nuzlocke_service is None:
                        self._send_json(
                            {"pending_encounters": []},
                            200,
                        )
                        return

                    self._send_json(
                        {
                            "pending_encounters": (
                                nuzlocke_service
                                .get_pending_encounters()
                            )
                        },
                        200,
                    )
                    return

                if self.path == "/api/species":

                    if species_catalog is None:
                        self._send_json(
                            {"species": []},
                            200,
                        )
                        return

                    self._send_json(
                        {
                            "species": (
                                species_catalog
                                .list_all()
                            )
                        },
                        200,
                    )
                    return

                if self.path == "/api/locations":

                    if location_catalog is None:
                        self._send_json(
                            {"locations": []},
                            200,
                        )
                        return

                    self._send_json(
                        {
                            "locations": (
                                location_catalog
                                .list_all()
                            )
                        },
                        200,
                    )
                    return

                self._send_text(
                    "Not Found",
                    404,
                )

            def do_POST(self):

                if self.path == "/api/nuzlocke/encounters":
                    self._handle_save_encounter()
                    return

                if self.path == (
                    "/api/nuzlocke/encounters/assign"
                ):
                    self._handle_assign_encounter()
                    return

                if self.path == (
                    "/api/nuzlocke/pending-encounters/"
                    "assign-special"
                ):
                    self._handle_assign_special_origin()
                    return

                if self.path == (
                    "/api/nuzlocke/encounters/delete"
                ):
                    self._handle_delete_encounter()
                    return

                if self.path == (
                    "/api/nuzlocke/pending-encounters/discard"
                ):
                    self._handle_discard_pending()
                    return

                if self.path == "/api/nuzlocke/reset":
                    self._handle_reset_all()
                    return

                if self.path == "/api/team-overlay-settings":
                    self._handle_save_team_overlay_settings()
                    return

                self._send_text(
                    "Not Found",
                    404,
                )

            def _handle_save_team_overlay_settings(self):

                if team_overlay_settings is None:
                    self._send_json(
                        {
                            "error": (
                                "Servicio de preferencias del "
                                "overlay no disponible."
                            )
                        },
                        503,
                    )
                    return

                payload = self._read_json_body()

                if payload is None:
                    self._send_json(
                        {"error": "JSON inválido."},
                        400,
                    )
                    return

                data = team_overlay_settings.update(payload)

                self._send_json(data, 200)

            def _handle_reset_all(self):

                if nuzlocke_service is None:
                    self._send_json(
                        {
                            "error": (
                                "Nuzlocke service no "
                                "disponible."
                            )
                        },
                        503,
                    )
                    return

                data = nuzlocke_service.reset_all()

                self._send_json(data, 200)

            def _handle_discard_pending(self):

                if nuzlocke_service is None:
                    self._send_json(
                        {
                            "error": (
                                "Nuzlocke service no "
                                "disponible."
                            )
                        },
                        503,
                    )
                    return

                payload = self._read_json_body()

                if payload is None:
                    self._send_json(
                        {"error": "JSON inválido."},
                        400,
                    )
                    return

                nickname = str(
                    payload.get("nickname", "")
                ).strip()

                if not nickname:
                    self._send_json(
                        {
                            "error": (
                                "'nickname' es requerido."
                            )
                        },
                        400,
                    )
                    return

                try:
                    pending = (
                        nuzlocke_service
                        .discard_pending_encounter(
                            nickname
                        )
                    )

                except ValueError as error:
                    self._send_json(
                        {"error": str(error)},
                        404,
                    )
                    return

                self._send_json(
                    {"pending_encounters": pending},
                    200,
                )

            def _handle_delete_encounter(self):

                if nuzlocke_service is None:
                    self._send_json(
                        {
                            "error": (
                                "Nuzlocke service no "
                                "disponible."
                            )
                        },
                        503,
                    )
                    return

                payload = self._read_json_body()

                if payload is None:
                    self._send_json(
                        {"error": "JSON inválido."},
                        400,
                    )
                    return

                location = str(
                    payload.get("location", "")
                ).strip()

                if not location:
                    self._send_json(
                        {
                            "error": (
                                "'location' es requerido."
                            )
                        },
                        400,
                    )
                    return

                try:
                    encounters = (
                        nuzlocke_service.delete_encounter(
                            location
                        )
                    )

                except ValueError as error:
                    self._send_json(
                        {"error": str(error)},
                        404,
                    )
                    return

                self._send_json(
                    {"encounters": encounters},
                    200,
                )

            def _handle_assign_encounter(self):

                if nuzlocke_service is None:
                    self._send_json(
                        {
                            "error": (
                                "Nuzlocke service no "
                                "disponible."
                            )
                        },
                        503,
                    )
                    return

                payload = self._read_json_body()

                if payload is None:
                    self._send_json(
                        {"error": "JSON inválido."},
                        400,
                    )
                    return

                nickname = str(
                    payload.get("nickname", "")
                ).strip()

                location = str(
                    payload.get("location", "")
                ).strip()

                if not nickname or not location:
                    self._send_json(
                        {
                            "error": (
                                "'nickname' y 'location' "
                                "son requeridos."
                            )
                        },
                        400,
                    )
                    return

                try:
                    result = (
                        nuzlocke_service
                        .assign_encounter_location(
                            nickname,
                            location,
                        )
                    )

                except ValueError as error:
                    self._send_json(
                        {"error": str(error)},
                        404,
                    )
                    return

                self._send_json(
                    result,
                    200,
                )

            def _handle_assign_special_origin(self):

                if nuzlocke_service is None:
                    self._send_json(
                        {
                            "error": (
                                "Nuzlocke service no "
                                "disponible."
                            )
                        },
                        503,
                    )
                    return

                payload = self._read_json_body()

                if payload is None:
                    self._send_json(
                        {"error": "JSON inválido."},
                        400,
                    )
                    return

                nickname = str(
                    payload.get("nickname", "")
                ).strip()

                origin = str(
                    payload.get("origin", "")
                ).strip()

                if not nickname or not origin:
                    self._send_json(
                        {
                            "error": (
                                "'nickname' y 'origin' "
                                "son requeridos."
                            )
                        },
                        400,
                    )
                    return

                try:
                    result = (
                        nuzlocke_service
                        .assign_special_origin(
                            nickname,
                            origin,
                        )
                    )

                except ValueError as error:
                    self._send_json(
                        {"error": str(error)},
                        404,
                    )
                    return

                self._send_json(
                    result,
                    200,
                )

            def _handle_save_encounter(self):

                if nuzlocke_service is None:
                    self._send_json(
                        {
                            "error": (
                                "Nuzlocke service no "
                                "disponible."
                            )
                        },
                        503,
                    )
                    return

                payload = self._read_json_body()

                if payload is None:
                    self._send_json(
                        {"error": "JSON inválido."},
                        400,
                    )
                    return

                location = str(
                    payload.get("location", "")
                ).strip()

                nickname = str(
                    payload.get("nickname", "")
                ).strip()

                species = str(
                    payload.get("species", "")
                ).strip()

                status = str(
                    payload.get(
                        "status",
                        "sin_intentar",
                    )
                ).strip()

                # Opcional -- el select de estado de la tabla
                # principal no tiene forma de elegir origen inline
                # (eso vive en la tarjeta de "¿Pokémon Especial?"),
                # así que normalmente no viaja acá. Si el registro
                # editado YA era "especial" antes, save_encounter()
                # conserva el origen que tenía en vez de exigir que
                # se vuelva a elegir (ver su docstring).
                origin = payload.get("origin")

                if not location:
                    self._send_json(
                        {
                            "error": (
                                "'location' es requerido."
                            )
                        },
                        400,
                    )
                    return

                try:
                    encounters = (
                        nuzlocke_service.save_encounter(
                            location,
                            nickname,
                            species,
                            status,
                            origin=origin,
                        )
                    )

                except ValueError as error:
                    self._send_json(
                        {"error": str(error)},
                        400,
                    )
                    return

                self._send_json(
                    {"encounters": encounters},
                    200,
                )

            def _read_json_body(self):
                """
                Lee y parsea el body JSON de la petición.
                Devuelve None si no se pudo parsear.
                """

                try:
                    content_length = int(
                        self.headers.get(
                            "Content-Length",
                            0,
                        )
                    )

                except (TypeError, ValueError):
                    return None

                if content_length <= 0:
                    return {}

                raw_body = self.rfile.read(
                    content_length
                )

                try:
                    return json.loads(
                        raw_body.decode("utf-8")
                    )

                except (
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                ):
                    return None

            def _serve_overlay(
                self,
                overlay_name: str,
            ) -> bool:
                """
                Sirve un overlay (team/badges/nuzlocke) desde
                overlays/{overlay_name}/, bajo /overlay/{overlay_name}.
                """

                return self._serve_static_page(
                    url_base=f"/overlay/{overlay_name}",
                    root_directory=overlay_directory,
                    relative_root=overlay_name,
                )

            def _serve_pokemon_sprite(self) -> bool:
                """
                Sirve /sprites/pokemon/{speciesId}.png -- set
                completo de sprites (GUI v2, Bloque 3, página
                Pokémon). Ruta simple de archivo directo, sin
                index.html -- no reutiliza _serve_static_page()
                porque acá no hace falta esa lógica de redirect,
                solo servir un PNG puntual (404 si no existe, ver
                _send_file()).
                """

                prefix = "/sprites/pokemon/"

                if not self.path.startswith(prefix):
                    return False

                relative_path = self.path[len(prefix):]

                self._send_file(
                    pokemon_sprites_directory,
                    relative_path,
                    self._content_type(relative_path),
                )
                return True

            def _serve_gym_leader_sprite(self) -> bool:
                """
                Sirve /sprites/gym_leaders/{n}.png (n=1-8) -- mismo
                patrón que _serve_pokemon_sprite().
                """

                prefix = "/sprites/gym_leaders/"

                if not self.path.startswith(prefix):
                    return False

                relative_path = self.path[len(prefix):]

                self._send_file(
                    gym_leaders_directory,
                    relative_path,
                    self._content_type(relative_path),
                )
                return True

            def _serve_pokemon_shuffle_sprite(self) -> bool:
                """
                Sirve /sprites/pokemon_shuffle/{NNN}.png -- mismo
                patrón que _serve_pokemon_sprite(), pero para el set
                estilo Shuffle usado SOLO en la tabla "Encuentros
                por Ruta" del Nuzlocke Tracker (05/09/2026). El
                nombre de archivo va con 3 dígitos con cero a la
                izquierda (ej. "025.png") -- el frontend arma la URL
                así, no hace falta normalizar acá.
                """

                prefix = "/sprites/pokemon_shuffle/"

                if not self.path.startswith(prefix):
                    return False

                relative_path = self.path[len(prefix):]

                self._send_file(
                    pokemon_shuffle_sprites_directory,
                    relative_path,
                    self._content_type(relative_path),
                )
                return True

            def _serve_item_sprite(self) -> bool:
                """
                Sirve /sprites/items/{id}.png (07/09/2026, roadmap
                4.2) -- mismo patrón que _serve_pokemon_sprite(),
                sin padding de ceros (ver comentario en
                self.item_sprites_directory). 404 normal si el ítem
                puntual no tuvo sprite en el repo fuente (ver
                download_item_sprites.py) -- no todos los ~2223
                ítems de PokéAPI tienen ícono descargado, solo hace
                falta que _send_file() devuelva 404 con gracia, no
                que rompa nada.

                CORRECCIÓN (09/09/2026, ver el comentario largo
                junto a self.item_sprites_directory en __init__):
                el `{id}` que llega en la URL es el índice REAL del
                ítem en el juego, no el id de PokéAPI que en
                realidad tienen los archivos en disco -- se traduce
                acá vía item_sprite_id_map antes de buscar el
                archivo. Si el índice no está en el mapa (los dos
                ids coinciden, o no se corrió el script de
                curación todavía), se sirve tal cual -- mismo
                comportamiento de siempre.
                """

                prefix = "/sprites/items/"

                if not self.path.startswith(prefix):
                    return False

                relative_path = self.path[len(prefix):]

                stem = relative_path[:-len(".png")] if relative_path.endswith(".png") else relative_path

                mapped_id = item_sprite_id_map.get(stem)

                if mapped_id is not None:
                    relative_path = f"{mapped_id}.png"

                self._send_file(
                    item_sprites_directory,
                    relative_path,
                    self._content_type(relative_path),
                )
                return True

            def _serve_species_artwork(self) -> bool:
                """
                Sirve /sprites/species_artwork/{speciesId}.png
                (07/09/2026, roadmap 4.2 -- modal Pokédex) -- mismo
                patrón que _serve_item_sprite().
                """

                prefix = "/sprites/species_artwork/"

                if not self.path.startswith(prefix):
                    return False

                relative_path = self.path[len(prefix):]

                self._send_file(
                    species_artwork_directory,
                    relative_path,
                    self._content_type(relative_path),
                )
                return True

            def _serve_panel(
                self,
                panel_name: str,
            ) -> bool:
                """
                Sirve un panel de control (ej. carga manual de
                encuentros del Nuzlocke Tracker) desde
                panels/{panel_name}/, bajo /panel/{panel_name}.
                """

                return self._serve_static_page(
                    url_base=f"/panel/{panel_name}",
                    root_directory=panel_directory,
                    relative_root=panel_name,
                )

            def _serve_static_page(
                self,
                url_base: str,
                root_directory: Path,
                relative_root: str,
            ) -> bool:
                """
                Sirve el index.html de una página estática y los
                archivos dentro de su carpeta. Devuelve True si la
                petición era para esta página (ya se respondió,
                con éxito o 404), False si no tiene nada que ver.

                Redirige a la versión con "/" al final cuando
                falta: sin esa barra, el navegador resuelve los
                <link>/<script> relativos (style.css, app.js)
                contra el directorio PADRE de la URL en vez del
                propio, y el CSS/JS no cargan.
                """

                if self.path == url_base:
                    self._send_redirect(
                        f"{url_base}/"
                    )
                    return True

                if self.path == f"{url_base}/":
                    self._send_file(
                        root_directory,
                        f"{relative_root}/index.html",
                        "text/html; charset=utf-8",
                    )
                    return True

                prefix = f"{url_base}/"

                if self.path.startswith(prefix):
                    relative_path = self.path[
                        len(prefix):
                    ]

                    self._send_file(
                        root_directory,
                        f"{relative_root}/{relative_path}",
                        self._content_type(
                            relative_path
                        ),
                    )
                    return True

                return False

            def _send_redirect(
                self,
                location: str,
            ):
                self.send_response(301)
                self.send_header(
                    "Location",
                    location,
                )
                self.send_header(
                    "Content-Length",
                    "0",
                )
                self.end_headers()

            def _send_file(
                self,
                root_directory: Path,
                relative_path: str,
                content_type: str,
            ):
                file_path = (
                    root_directory
                    / relative_path
                )

                if not file_path.is_file():
                    self._send_text(
                        "Not Found",
                        404,
                    )
                    return

                body = file_path.read_bytes()

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    content_type,
                )
                self.send_header(
                    "Content-Length",
                    str(len(body)),
                )
                self.end_headers()

                self.wfile.write(body)

            def _content_type(
                self,
                path: str,
            ) -> str:
                suffix = Path(
                    path
                ).suffix.lower()

                content_types = {
                    ".html": (
                        "text/html; charset=utf-8"
                    ),
                    ".css": (
                        "text/css; charset=utf-8"
                    ),
                    ".js": (
                        "application/javascript; "
                        "charset=utf-8"
                    ),
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                }

                return content_types.get(
                    suffix,
                    "application/octet-stream",
                )

            def _send_json(
                self,
                data,
                status_code: int,
            ):
                body = json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8")

                self.send_response(status_code)
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(body)),
                )
                self.end_headers()

                self.wfile.write(body)

            def _send_text(
                self,
                text: str,
                status_code: int,
            ):
                body = text.encode("utf-8")

                self.send_response(status_code)
                self.send_header(
                    "Content-Type",
                    "text/plain; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(body)),
                )
                self.end_headers()

                self.wfile.write(body)

            def log_message(
                self,
                format,
                *args,
            ):
                return

        return Handler

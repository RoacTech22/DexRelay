from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from app.core.state import ApplicationState
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
    ) -> None:
        self.state = state
        self.host = host
        self.port = port
        self.nuzlocke_service = nuzlocke_service
        self.species_catalog = species_catalog

        project_root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

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

        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        """Inicia el servidor HTTP en un hilo separado."""

        if self._server is not None:
            return

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

    def _create_handler(self):
        """Crea el handler HTTP."""

        state = self.state
        overlay_directory = self.overlay_directory
        panel_directory = self.panel_directory
        nuzlocke_service = self.nuzlocke_service
        species_catalog = self.species_catalog

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

                self._send_text(
                    "Not Found",
                    404,
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

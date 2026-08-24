from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from app.core.state import ApplicationState


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
    ) -> None:
        self.state = state
        self.host = host
        self.port = port

        self.overlay_directory = (
            Path(__file__)
            .resolve()
            .parents[2]
            / "overlays"
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

                if self.path.rstrip("/") == "/overlay/team":
                    self._send_file(
                        "team/index.html",
                        "text/html; charset=utf-8",
                    )
                    return

                if self.path.startswith(
                    "/overlay/team/"
                ):
                    relative_path = self.path[
                        len("/overlay/team/"):
                    ]

                    self._send_file(
                        f"team/{relative_path}",
                        self._content_type(
                            relative_path
                        ),
                    )
                    return

                if self.path.rstrip("/") == "/overlay/badges":
                    self._send_file(
                        "badges/index.html",
                        "text/html; charset=utf-8",
                    )
                    return

                if self.path.startswith(
                    "/overlay/badges/"
                ):
                    relative_path = self.path[
                        len("/overlay/badges/"):
                    ]

                    self._send_file(
                        f"badges/{relative_path}",
                        self._content_type(
                            relative_path
                        ),
                    )
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

                self._send_text(
                    "Not Found",
                    404,
                )

            def _send_file(
                self,
                relative_path: str,
                content_type: str,
            ):
                file_path = (
                    overlay_directory
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

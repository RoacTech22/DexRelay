from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from app.core.state import ApplicationState


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

        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        """Inicia el servidor HTTP en un hilo separado."""

        if self._server is not None:
            return

        server = ThreadingHTTPServer(
            (self.host, self.port),
            self._create_handler(),
        )

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

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    self._send_text(
                        "DexRelay HTTP Server",
                        200,
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

                self._send_text(
                    "Not Found",
                    404,
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

            def log_message(self, format, *args):
                return

        return Handler

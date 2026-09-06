"""
Captura de logs en memoria para la página Logs de la GUI v2
(Bloque 5, 06/09/2026).

DexRelay no tiene un módulo `logging` -- todo el estado se reporta
con `print()` (19 llamadas reales hoy, repartidas entre
Application, HTTPServer, AzaharReader y Api). La GUI Tkinter vieja
(`app/gui/main_window.py`, `_StreamToLogWidget`) ya resolvía esto
redirigiendo `sys.stdout`/`sys.stderr` enteros a un widget, con un
tope de 500 líneas (`MAX_LOG_LINES`) -- este módulo es el MISMO
criterio, migrado para que la GUI v2 (que no tiene un widget nativo
al que escribirle directo) pueda pedirle el buffer al bridge
`Api` en vez de eso.

Lo que este módulo NO hace, a propósito (mismo criterio que
"FPS del juego"/"Memoria base" del Dashboard, o el mockup completo
de Configuración): no clasifica cada línea en niveles
INFO/WARN/ERROR/DEBUG ni en "fuentes" (Runtime/Reader/Azahar/HTTP
Server/...) -- de los 19 `print()` reales de hoy, solo algunos
traen un prefijo tipo "[AzaharReader]" y la mayoría no sigue ningún
formato fijo, así que inventar esas columnas sería mostrar un dato
que no existe. Lo único que SÍ es un dato real y barato de
distinguir es el STREAM de origen (`stdout` vs `stderr`) -- en la
práctica, en este proyecto, `stderr` son excepciones no capturadas
(tracebacks de Python) y `stdout` son los `print()` deliberados de
estado, así que la GUI lo muestra como una distinción visual
simple (línea de error vs línea normal), no como un "Nivel"
inventado con más categorías de las que hay datos para sostener.
"""

from __future__ import annotations

import sys
import threading
import time
from collections import deque

MAX_LOG_LINES = 500


class LogBuffer:
    """
    Buffer circular thread-safe con las últimas `MAX_LOG_LINES`
    líneas de stdout/stderr. Los `print()` reales de DexRelay
    pueden venir del hilo principal, del hilo del Runtime
    (`DexRelayRuntime`) o del hilo del HTTPServer -- de ahí el
    lock, mismo motivo que documenta `_StreamToLogWidget` en la
    GUI Tkinter vieja para marshalear al hilo principal (acá no
    hace falta marshalear a ningún hilo de UI porque no hay un
    widget nativo del lado de Python -- la GUI v2 solo LEE este
    buffer por polling desde `Api.get_logs()`).
    """

    def __init__(self, max_lines: int = MAX_LOG_LINES) -> None:
        self._lines = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._next_id = 1

    def append(self, text: str, stream: str) -> None:
        with self._lock:
            self._lines.append(
                {
                    "id": self._next_id,
                    "time": time.strftime("%H:%M:%S"),
                    "stream": stream,
                    "text": text,
                }
            )
            self._next_id += 1

    def get_all(self):
        with self._lock:
            return list(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()


# Instancia única, a nivel de módulo -- la redirección de
# stdout/stderr (ver install() más abajo) se instala UNA vez al
# arrancar el proceso (app/main.py), antes de que exista
# `Application`; `Api.get_logs()`/`clear_logs()` importan este
# mismo objeto directo, no hace falta pasarlo por Application.
buffer = LogBuffer()


class _TeeStream:
    """
    Wrapper file-like: escribe en el stream original (la terminal
    sigue funcionando igual que hoy) Y además manda cada línea no
    vacía al `LogBuffer` compartido, etiquetada con qué stream era.

    `if text.strip()` (mismo chequeo que `_StreamToLogWidget` de la
    GUI vieja): `print()` hace dos `write()` separados -- el
    contenido y el `end="\\n"` aparte -- así que sin este chequeo
    cada `print()` real dejaría una línea vacía extra en el buffer.
    """

    def __init__(self, original_stream, stream_name: str) -> None:
        self._original = original_stream
        self._stream_name = stream_name

    def write(self, text: str) -> None:
        if self._original is not None:
            self._original.write(text)

        if text.strip():
            buffer.append(text.rstrip("\n"), self._stream_name)

    def flush(self) -> None:
        if self._original is not None:
            self._original.flush()

    # pywebview/otras libs a veces chequean esto antes de escribir
    # (por ejemplo, para decidir si hay una consola real) -- se
    # delega al stream original si existe, o se asume `False` (sin
    # consola real) si no, en vez de romper con AttributeError.
    def isatty(self) -> bool:
        if self._original is not None and hasattr(self._original, "isatty"):
            return self._original.isatty()

        return False


def install() -> None:
    """
    Reemplaza `sys.stdout`/`sys.stderr` por versiones que además
    alimentan `buffer`. Se llama UNA sola vez, desde `app/main.py`,
    después del guard de `sys.stdout is None` (build empaquetado
    con `--windowed`, ver comentario en `app/main.py`) -- acá
    `sys.stdout`/`sys.stderr` ya son streams reales (aunque sea el
    sumidero `os.devnull`), nunca `None`, así que `_TeeStream` los
    puede envolver sin chequeos extra.
    """

    sys.stdout = _TeeStream(sys.stdout, "stdout")
    sys.stderr = _TeeStream(sys.stderr, "stderr")

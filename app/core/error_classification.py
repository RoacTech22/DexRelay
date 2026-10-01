"""
Clasificación de excepciones del ciclo realtime (Bloque 9.1,
30/09/2026, guía siguiente versión).

Antes, el `except Exception` de `Application._run_realtime_loop()`
trataba igual una desconexión esperada de Azahar que un `TypeError`
real por un cambio mal hecho: ambos terminaban en una línea de una
sola fila en los logs, indistinguibles. Acá se separan:

- TRANSITORIO: fallo de red/socket esperable al hablar UDP con
  Azahar (timeout, conexión rechazada/cortada, Azahar cerrándose).
  Se cuenta y se informa en una línea corta, sin traceback.
- BUG: cualquier otra cosa (TypeError, KeyError, AttributeError,
  RuntimeError, ...). Se registra como ERROR con traceback completo
  -- es un error de programación hasta que se demuestre lo
  contrario. Conservador a propósito: ante la duda se reporta de
  más, nunca se esconde un bug como si fuera ruido de red.

OSError es la clase base de TimeoutError, ConnectionError y
socket.timeout/socket.error, que son lo que realmente lanzan las
lecturas UDP (regla 6 del Documento Maestro: "excepción
`OSError` y derivados").
"""

from __future__ import annotations

import traceback


def is_transient_error(error: BaseException) -> bool:
    """True si `error` es un fallo de red/socket esperable."""

    return isinstance(error, OSError)


def error_signature(error: BaseException) -> tuple:
    """
    Firma estable de un error para deduplicar el log: tipo, mensaje
    y la última línea del traceback (archivo + número). Un mismo bug
    que se repite cada ciclo de 200ms tiene siempre la misma firma.
    """

    frames = traceback.extract_tb(error.__traceback__)
    where = (
        (frames[-1].filename, frames[-1].lineno) if frames else (None, None)
    )

    return (type(error).__name__, str(error), where)


def format_error_traceback(error: BaseException) -> str:
    """Traceback completo como texto (para el buffer de Logs)."""

    return "".join(
        traceback.format_exception(
            type(error), error, error.__traceback__
        )
    ).rstrip()

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomic(path: str | Path, data: Any, *, indent: int = 2) -> None:
    """
    Escribe `data` como JSON en `path` de forma atómica (Bloque
    4.1, guía siguiente versión, 23/09/2026).

    Antes, nuzlocke_storage.py y badges_storage.py hacían
    `path.open("w")` + `json.dump()` directo sobre el archivo
    final -- un corte a mitad de escritura (crash, corte de luz,
    cierre forzado de la app mientras Runtime está guardando)
    dejaba el archivo con JSON truncado, es decir corrupto e
    ilegible en el próximo arranque. Con `badges.json`/
    `nuzlocke_*.json` siendo progreso real de partida que nunca se
    versiona ni se regenera solo (regla 10 del Documento Maestro),
    perderlo así no tiene vuelta atrás.

    Se escribe primero a un archivo temporal en el MISMO
    directorio que `path` (tiene que ser el mismo directorio: un
    os.replace() entre sistemas de archivos distintos no es
    atómico) y recién al final se reemplaza el destino real de una
    sola operación con `os.replace()` -- en cualquier sistema
    operativo, esa operación deja el archivo destino en su
    contenido viejo completo o en el nuevo completo, nunca a
    medias. Si algo falla mientras se escribe el temporal, el
    archivo original queda intacto y el temporal se borra -- nunca
    se llega a tocar el archivo real.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, indent=indent, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

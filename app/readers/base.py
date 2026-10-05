"""
Contrato del transporte con el emulador (Bloque 12, ruta multijuego).

Corrige el boceto original: el Protocol de 4 métodos que proponía para
"EmulatorReader" describe en realidad al TRANSPORTE (hablarle al
proceso emulado), no al reader de dominio (leer party, cajas, etc.), que
es lo que usa Runtime. Hoy el único transporte es `Citra`
(app/readers/citra.py, protocolo UDP de Azahar); el día que exista otro
emulador (DS/GBA) tendrá que cumplir esto, y AzaharReader seguirá
leyendo con el mismo mapa de memoria del perfil.

No se crean jerarquías nuevas antes de necesitarlas (regla 6 del
Documento Maestro): esto solo hace explícito lo que AzaharReader ya
exige de `Citra`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmulatorTransport(Protocol):
    def is_connected(self) -> bool: ...

    def process_list(self) -> dict[int, tuple[int, str]]:
        """{pid: (title_id, process_name)} de los procesos del emulador."""
        ...

    def get_process(self): ...

    def set_process(self, process_id: int) -> None: ...

    def read_memory(self, read_address: int, read_size: int) -> bytes | None: ...

    def write_memory(self, write_address: int, write_contents: bytes): ...

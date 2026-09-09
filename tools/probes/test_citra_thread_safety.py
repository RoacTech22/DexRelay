"""
Valida el arreglo real de concurrencia en app/readers/citra.py
(07/09/2026, reportado por el usuario: "lectura fallida" en varios
slots + "Expected 1 byte for badges, received None" justo al entrar
a la página Pokémon -- ver el comentario largo en Citra.__init__()
para el diagnóstico completo).

Prueba la exclusión mutua DIRECTO (un hilo sostiene el Lock a
propósito, y se mide que read_memory() desde otro hilo se queda
esperando hasta que se libera) en vez de intentar reproducir la
carrera real por timing -- un intento anterior de este test
armaba la carrera con sleeps artificiales, pero resultó
probabilístico (no siempre se reproducía, dependiente de cuán
rápido corriera la máquina) -- este enfoque es determinístico:
si el Lock funciona, el tiempo medido NUNCA puede ser menor a
lo que el otro hilo lo sostuvo, sin importar la velocidad de la
máquina.

    python -m tools.probes.test_citra_thread_safety
"""

import struct
import threading
import time

from app.readers.citra import Citra, RequestType


class FakeSocket:
    """
    Socket falso mínimo -- alcanza con responder algo con la forma
    correcta (mismo request_id/type/tamaño) para que
    _read_and_validate_header() lo acepte. No hace falta simular
    latencia acá, ver el docstring del módulo para el porqué del
    cambio de enfoque.
    """

    def settimeout(self, value):
        pass

    def sendto(self, data, address):
        version, request_id, request_type, data_size = (
            struct.unpack("IIII", data[:16])
        )
        self._last_request_id = request_id
        self._last_request_type = request_type

    def recv(self, size):
        payload = b"\x00"
        return struct.pack(
            "IIII",
            1,
            self._last_request_id,
            self._last_request_type,
            len(payload),
        ) + payload


def test_lock_serializa_el_acceso_al_socket():
    """
    Un hilo sostiene `citra._lock` a propósito durante
    `hold_seconds`. Mientras tanto, se llama a `read_memory()`
    desde el hilo principal -- si el Lock funciona de verdad, esa
    llamada tiene que esperar a que el otro hilo lo suelte antes de
    poder mandar su propio pedido, así que el tiempo medido no
    puede ser menor a `hold_seconds` (con un margen chico por el
    overhead normal de hilos).
    """

    citra = Citra()
    citra.socket = FakeSocket()

    hold_seconds = 0.2
    lock_acquired_by_holder = threading.Event()

    def hold_lock():
        with citra._lock:
            lock_acquired_by_holder.set()
            time.sleep(hold_seconds)

    holder = threading.Thread(target=hold_lock)
    holder.start()

    # Esperar la confirmación de que el otro hilo YA tiene el
    # Lock (no un sleep a ciegas) antes de medir -- así el tiempo
    # medido abajo es exclusivamente el tiempo de espera real por
    # el Lock, sin ruido de cuándo arrancó el hilo.
    lock_acquired_by_holder.wait(timeout=2.0)

    start = time.monotonic()
    result = citra.read_memory(0x1000, 1)
    elapsed = time.monotonic() - start

    holder.join()

    assert result is not None, (
        "read_memory() debería completarse bien una vez liberado "
        "el Lock, no dar None."
    )

    # Margen de 0.05s para el overhead normal de scheduling de
    # hilos -- no hace falta que sea exacto, solo que sea
    # claramente mayor a "casi nada" (que es lo que daría si el
    # Lock no estuviera funcionando de verdad).
    assert elapsed >= (hold_seconds - 0.05), (
        f"read_memory() tardó {elapsed:.3f}s, pero el otro hilo "
        f"sostuvo el Lock por {hold_seconds:.3f}s -- si el tiempo "
        f"medido es mucho menor, el Lock no está bloqueando de "
        f"verdad el acceso al socket."
    )

    print(
        f"OK - read_memory() esperó {elapsed:.3f}s a que se "
        f"liberara el Lock (sostenido {hold_seconds:.3f}s) -- "
        f"exclusión mutua real, no solo declarada"
    )


if __name__ == "__main__":
    test_lock_serializa_el_acceso_al_socket()

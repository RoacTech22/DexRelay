"""
Bloque 6.2 (guía siguiente versión, 23/09/2026): AzaharReader.
diagnose_connection() distingue las causas reales de "no conecta"
según lo que Azahar contesta (o no) por UDP, sin inventar ninguna.
"""

import socket

from app.readers.azahar_reader import AzaharReader


class FakeCitra:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def process_list(self):
        if self._error is not None:
            raise self._error

        return self._result


def _reader(citra):
    return AzaharReader(citra=citra, process_name=None)


def test_puerto_sin_escucha_se_distingue_de_un_timeout():
    reset = _reader(FakeCitra(error=ConnectionResetError())).diagnose_connection()
    refused = _reader(FakeCitra(error=ConnectionRefusedError())).diagnose_connection()
    timeout = _reader(FakeCitra(error=socket.timeout())).diagnose_connection()

    assert reset["state"] == AzaharReader.DIAG_NO_LISTENER
    assert refused["state"] == AzaharReader.DIAG_NO_LISTENER
    assert timeout["state"] == AzaharReader.DIAG_TIMEOUT


def test_otro_error_de_red_conserva_el_detalle_real():
    result = _reader(FakeCitra(error=OSError("boom"))).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_ERROR
    assert "boom" in result["detail"]


def test_azahar_responde_sin_juego_lista_los_procesos_reales():
    processes = {1: (0x0004013000001A02, "ac"), 2: (0x0004013000002F02, "nwm")}

    result = _reader(FakeCitra(result=processes)).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_NO_GAME
    assert result["processes"] == ["ac", "nwm"]


def test_azahar_responde_con_lista_vacia():
    result = _reader(FakeCitra(result={})).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_NO_GAME
    assert result["processes"] == []


def test_juego_conocido_presente():
    processes = {7: (0x000400000011C500, "sango-2")}

    result = _reader(FakeCitra(result=processes)).diagnose_connection()

    assert result["state"] == AzaharReader.DIAG_GAME_FOUND
    assert result["process_name"] == "sango-2"

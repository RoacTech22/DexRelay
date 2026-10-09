"""
Pruebas de la lógica pura de tiempo_juego_xy.py (sin bridge ni Azahar).
"""

import tiempo_juego_xy as probe


class _Servicio:
    def __init__(self, respuestas):
        self.respuestas = respuestas

    def get_playtime(self, clave):
        return self.respuestas[clave]


def test_formatear_tiempo_disponible_y_no_disponible():
    assert (
        probe.formatear_tiempo(
            {"available": True, "hours": 12, "minutes": 5, "seconds": 9}
        )
        == "12 h 05 min 09 s"
    )
    assert "NO disponible" in probe.formatear_tiempo(
        {"available": False, "reason": "No se encontró"}
    )
    assert "NO disponible" in probe.formatear_tiempo(None)


def test_titulos_presentes_lista_los_title_id(tmp_path):
    base = tmp_path / "sdmc" / "Nintendo 3DS" / "id0" / "id1" / "title" / "00040000"
    (base / "00055D00").mkdir(parents=True)
    (base / "0011c500").mkdir(parents=True)
    (base / "archivo.txt").write_text("x")

    resultado = probe.titulos_presentes([tmp_path / "sdmc", tmp_path / "otra"])

    assert resultado == {str(tmp_path / "sdmc"): ["00055d00", "0011c500"]}


def test_analizar_juego_encontrado(tmp_path):
    archivo = tmp_path / "main"
    archivo.write_bytes(b"\0" * 10)
    tiempo = {"available": True, "hours": 1, "minutes": 2, "seconds": 3}

    informe = probe.analizar_juego(
        "kujira-1", "Pokémon X", lambda c: archivo, _Servicio({"kujira-1": tiempo})
    )

    assert informe["encontrado"] is True
    assert informe["archivo"]["bytes"] == 10
    assert informe["tiempo"] == tiempo


def test_analizar_juego_no_encontrado():
    tiempo = {"available": False, "reason": "No se encontró"}

    informe = probe.analizar_juego(
        "kujira-2", "Pokémon Y", lambda c: None, _Servicio({"kujira-2": tiempo})
    )

    assert informe["encontrado"] is False
    assert informe["archivo"] is None


def test_informe_incluye_diagnostico_si_falta_un_guardado():
    informes = [
        {
            "clave": "kujira-1",
            "juego": "Pokémon X",
            "encontrado": False,
            "archivo": None,
            "tiempo": {"available": False, "reason": "x"},
        }
    ]

    texto = probe.formatear(informes, {"C:/Azahar/sdmc": ["00055d00"]})

    assert "NO encontrado" in texto
    assert "00055d00" in texto

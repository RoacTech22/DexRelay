"""
Pruebas de la lógica pura de recolectar_zonas_xy.py (sin Azahar):
interpretación de lo que escribe Ronald, tabla zona->lugar y persistencia.
"""

import recolectar_zonas_xy as probe

CATALOGO = {
    6: "Pueblo Boceto",
    8: "Ruta 1",
    10: "Pueblo Acuarela",
    50: "Ruta 10",
    54: "Ruta 11",
    56: "Cueva Reflejos",
    66: "Ruta 13",
    104: "Calle Victoria",
    106: "Liga Pokémon",
    132: "Cueva Brillante",
}


def test_normalize_quita_tildes_y_espacios():
    assert probe.normalize("  Liga   Pokémon ") == "liga pokemon"
    assert probe.normalize(None) == ""


def test_numero_solo_es_numero_de_ruta_no_id():
    # "10" es la Ruta 10 (id 50), NO el lugar con id 10.
    assert probe.buscar_lugar("10", CATALOGO) == ("ok", [50])
    assert probe.buscar_lugar("ruta 10", CATALOGO) == ("ok", [50])
    assert probe.buscar_lugar("Ruta10", CATALOGO) == ("ok", [50])
    assert probe.buscar_lugar("1", CATALOGO) == ("ok", [8])


def test_id_explicito():
    assert probe.buscar_lugar("id:56", CATALOGO) == ("ok", [56])
    assert probe.buscar_lugar("ID : 10", CATALOGO) == ("ok", [10])
    assert probe.buscar_lugar("id:999", CATALOGO) == ("nada", [])


def test_nombre_exacto_parcial_y_ambiguo():
    assert probe.buscar_lugar("cueva reflejos", CATALOGO) == ("ok", [56])
    assert probe.buscar_lugar("reflejos", CATALOGO) == ("ok", [56])
    assert probe.buscar_lugar("liga", CATALOGO) == ("ok", [106])
    estado, ids = probe.buscar_lugar("cueva", CATALOGO)
    assert estado == "varios" and ids == [56, 132]
    assert probe.buscar_lugar("xyz", CATALOGO) == ("nada", [])
    assert probe.buscar_lugar("", CATALOGO) == ("nada", [])
    # Ruta 1 no se confunde con Ruta 10 / 11 / 13 al escribir "ruta 1".
    assert probe.buscar_lugar("ruta 1", CATALOGO) == ("ok", [8])


def test_registrar_nuevo_igual_y_conflicto_sin_pisar():
    tabla = probe.Tabla()

    assert tabla.registrar(268, 50, "captura") == "nuevo"
    assert tabla.registrar(268, 50, "manual") == "igual"
    assert tabla.registrar(268, 54, "captura") == "conflicto"
    assert tabla.zonas[268] == {"lugar": 50, "fuente": "captura"}


def test_descartar_y_conocida():
    tabla = probe.Tabla()

    assert not tabla.conocida(21)
    tabla.descartar(21)
    assert tabla.conocida(21)
    # Si luego se le asigna un lugar, deja de estar descartada.
    tabla.registrar(21, 6, "manual")
    assert 21 not in tabla.descartadas and tabla.conocida(21)


def test_guardar_y_cargar_ida_y_vuelta(tmp_path):
    tabla = probe.Tabla()
    tabla.registrar(268, 50, "captura")
    tabla.registrar(305, 56, "manual")
    tabla.descartar(188)

    path = tmp_path / "sub" / "zonas.json"
    probe.guardar(tabla, CATALOGO, path)
    cargada = probe.cargar(path)

    assert cargada.zonas == tabla.zonas
    assert cargada.descartadas == {188}

    texto = path.read_text(encoding="utf-8")
    assert '"nombre": "Ruta 10"' in texto
    assert not (tmp_path / "sub" / "zonas.tmp").exists()


def test_cargar_archivo_inexistente_o_roto(tmp_path):
    assert probe.cargar(tmp_path / "no_existe.json").zonas == {}

    roto = tmp_path / "roto.json"
    roto.write_text("{ no es json", encoding="utf-8")
    assert probe.cargar(roto).zonas == {}


def _responder(*respuestas):
    cola = list(respuestas)

    return lambda _prompt: cola.pop(0)


def test_preguntar_lugar_saltar_no_y_salir():
    assert probe.preguntar(305, CATALOGO, None, _responder("reflejos")) == (
        "lugar", 56,
    )
    assert probe.preguntar(305, CATALOGO, None, _responder("")) == ("saltar", None)
    assert probe.preguntar(305, CATALOGO, None, _responder("No")) == ("no", None)
    assert probe.preguntar(305, CATALOGO, None, _responder("SALIR")) == (
        "salir", None,
    )


def test_preguntar_repite_si_no_entiende_o_es_ambiguo():
    # "cueva" es ambiguo, "zzz" no existe, y recién "id:132" resuelve.
    respuesta = probe.preguntar(
        305, CATALOGO, 433, _responder("cueva", "zzz", "id:132")
    )

    assert respuesta == ("lugar", 132)

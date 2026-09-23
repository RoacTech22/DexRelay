"""
Bloque 4.1 (guía siguiente versión, 23/09/2026): write_json_atomic()
-- nuzlocke_storage.py y badges_storage.py guardan progreso real de
partida (regla 10 del Documento Maestro: nunca se versiona ni se
regenera solo), así que un corte a mitad de escritura no puede
dejarlos corruptos. Antes escribían con open("w") + json.dump()
directo sobre el archivo final.
"""

import json
import os

from app.core.atomic_write import write_json_atomic


def test_escribe_y_relee_el_json(tmp_path):
    path = tmp_path / "data.json"

    write_json_atomic(path, {"a": 1})

    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}


def test_sobreescritura_no_deja_temporales_huerfanos(tmp_path):
    path = tmp_path / "data.json"

    write_json_atomic(path, {"a": 1})
    write_json_atomic(path, {"a": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2}
    assert os.listdir(tmp_path) == ["data.json"]


def test_crea_el_directorio_si_no_existe():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as base:
        path = Path(base) / "subdir" / "data.json"

        write_json_atomic(path, {"a": 1})

        assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}


def test_un_fallo_a_mitad_de_camino_no_toca_el_archivo_original(tmp_path):
    """
    Reproduce un corte a mitad de escritura: algo que json.dump()
    no puede serializar explota DESPUÉS de haber abierto el
    temporal. El archivo real (con el valor bueno anterior) tiene
    que quedar intacto, y no puede sobrevivir ningún .tmp suelto.
    """

    path = tmp_path / "data.json"
    write_json_atomic(path, {"a": "valor bueno"})

    class NoSerializable:
        pass

    try:
        write_json_atomic(path, {"a": NoSerializable()})
        assert False, "tenía que lanzar TypeError"
    except TypeError:
        pass

    assert json.loads(path.read_text(encoding="utf-8")) == {"a": "valor bueno"}
    assert os.listdir(tmp_path) == ["data.json"]


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as base:
        base_path = Path(base)
        test_escribe_y_relee_el_json(base_path / "t1" / "x")
    with tempfile.TemporaryDirectory() as base:
        base_path = Path(base)
        (base_path).mkdir(exist_ok=True)
        test_sobreescritura_no_deja_temporales_huerfanos(base_path)
    test_crea_el_directorio_si_no_existe()
    with tempfile.TemporaryDirectory() as base:
        test_un_fallo_a_mitad_de_camino_no_toca_el_archivo_original(Path(base))
    print("OK - todos los tests de atomic_write pasaron")

"""
Bloque 4.2 (guía siguiente versión, 23/09/2026): NuzlockeStorage.backup()
-- respaldo automático antes de una operación destructiva (borrar
un encuentro, "Reiniciar todo"). Contra la clase real, con un
directorio temporal como data/ -- no contra un fake, porque la
lógica interesante (nombre de archivo con timestamp, poda de los
más viejos, restaurar) vive en NuzlockeStorage misma.
"""

import json
import time

from app.services.nuzlocke_storage import NuzlockeStorage


def test_no_hace_nada_si_el_archivo_todavia_no_existe(tmp_path):
    storage = NuzlockeStorage(tmp_path / "nuzlocke_omega_ruby.json")

    result = storage.backup()

    assert result is None
    assert not (tmp_path / "backups").exists()


def test_copia_el_archivo_actual_a_backups(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)
    storage.save({"roster": ["Boti"]})

    backup_path = storage.backup()

    assert backup_path is not None
    assert backup_path.parent == tmp_path / "backups"
    assert json.loads(backup_path.read_text(encoding="utf-8")) == {"roster": ["Boti"]}

    # El archivo original no se toca -- backup() solo copia, no
    # borra ni modifica nada del lado del archivo real.
    assert json.loads(path.read_text(encoding="utf-8")) == {"roster": ["Boti"]}


def test_dos_backups_en_el_mismo_segundo_no_se_pisan(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)

    storage.save({"roster": ["Uno"]})
    backup_1 = storage.backup()

    storage.save({"roster": ["Dos"]})
    backup_2 = storage.backup()

    assert backup_1 != backup_2
    assert json.loads(backup_1.read_text(encoding="utf-8")) == {"roster": ["Uno"]}
    assert json.loads(backup_2.read_text(encoding="utf-8")) == {"roster": ["Dos"]}


def test_solo_conserva_los_ultimos_backup_keep_count(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)
    storage.BACKUP_KEEP_COUNT = 3

    for i in range(5):
        storage.save({"roster": [f"Pokemon{i}"]})
        storage.backup()
        # Nombre de archivo con resolución de 1 segundo -- separar
        # las llamadas para que cada una tenga timestamp distinto y
        # el orden de poda sea determinístico, no dependiente del
        # sufijo de desempate.
        time.sleep(1.01)

    remaining = storage.list_backups()

    assert len(remaining) == 3

    # Se conservan los 3 ÚLTIMOS (Pokemon2, Pokemon3, Pokemon4), no
    # los 3 primeros.
    contents = [
        json.loads(backup_path.read_text(encoding="utf-8"))["roster"][0]
        for backup_path in remaining
    ]
    assert set(contents) == {"Pokemon2", "Pokemon3", "Pokemon4"}


def test_list_backups_devuelve_del_mas_reciente_al_mas_viejo(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)

    storage.save({"roster": ["Uno"]})
    storage.backup()
    time.sleep(1.01)
    storage.save({"roster": ["Dos"]})
    storage.backup()

    backups = storage.list_backups()

    assert len(backups) == 2
    assert json.loads(backups[0].read_text(encoding="utf-8")) == {"roster": ["Dos"]}
    assert json.loads(backups[1].read_text(encoding="utf-8")) == {"roster": ["Uno"]}


def test_restore_latest_backup_reemplaza_el_archivo_actual(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)

    storage.save({"roster": ["Bueno"]})
    storage.backup()
    storage.save({"roster": []})  # "Reiniciar todo", por ejemplo

    restored = storage.restore_latest_backup()

    assert restored is True
    assert json.loads(path.read_text(encoding="utf-8")) == {"roster": ["Bueno"]}


def test_restore_latest_backup_sin_ningun_backup_no_hace_nada(tmp_path):
    path = tmp_path / "nuzlocke_omega_ruby.json"
    storage = NuzlockeStorage(path)
    storage.save({"roster": ["Actual"]})

    restored = storage.restore_latest_backup()

    assert restored is False
    assert json.loads(path.read_text(encoding="utf-8")) == {"roster": ["Actual"]}


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    tests = [
        test_no_hace_nada_si_el_archivo_todavia_no_existe,
        test_copia_el_archivo_actual_a_backups,
        test_dos_backups_en_el_mismo_segundo_no_se_pisan,
        test_solo_conserva_los_ultimos_backup_keep_count,
        test_list_backups_devuelve_del_mas_reciente_al_mas_viejo,
        test_restore_latest_backup_reemplaza_el_archivo_actual,
        test_restore_latest_backup_sin_ningun_backup_no_hace_nada,
    ]

    for test_fn in tests:
        with tempfile.TemporaryDirectory() as base:
            test_fn(Path(base))

    print("OK - todos los tests de NuzlockeStorage.backup() pasaron")

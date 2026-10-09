"""Lógica pura de combate_vivo_xy.py (segmentación y resumen)."""

import combate_vivo_xy as probe


def _s(t, cell1, ff7, label=None, ultimo=None):
    return {
        "t": t,
        "cell1": cell1,
        "flags": {0xFEE: 0, 0xFF7: ff7},
        "label": label,
        "ultimo": ultimo,
    }


def test_segmenta_combates_por_la_celda():
    samples = [
        _s(0.0, 0, None),
        _s(0.1, 0x100, 0),
        _s(0.2, 0x100, 0x80),
        _s(0.3, 0, None),
        _s(0.4, 0x200, 0),
        _s(0.5, 0x200, 0),
    ]

    battles = probe.segment_battles(samples)

    assert [len(b) for b in battles] == [2, 2]


def test_resumen_muestra_el_cambio_de_bandera_con_su_tiempo():
    battle = [
        _s(1.0, 0x100, 0, "SALVAJE"),
        _s(1.1, 0x100, 0, "SALVAJE"),
        _s(1.5, 0x100, 0x80, "SALVAJE"),
    ]

    summary = probe.summarize_battle(battle)

    assert summary["label"] == "SALVAJE"
    assert summary["ff7_first"] == 0 and summary["ff7_last"] == 0x80
    assert summary["ff7_changes"] == [(0.0, 0), (0.5, 0x80)]
    assert summary["cells"] == [0x100]
    assert "0@0.0s -> 128@0.5s" in probe.format_summary(1, summary)


def test_etiqueta_tardia_se_asocia_al_combate():
    battle = [_s(0, 0x100, 0), _s(1, 0x100, 0, "ENTRENADOR")]

    assert probe.battle_label(battle) == "ENTRENADOR"
    assert probe.battle_label([_s(0, 0x100, 0)]) is None


def test_valores_de_banderas_de_la_ventana():
    window = bytes(range(32))

    assert probe.flag_values(window) == {0xFEE: 0x0E, 0xFF7: 0x17}
    assert probe.flag_values(None) == {0xFEE: None, 0xFF7: None}


def test_cruza_celda_con_la_senal_del_ultimo_rival():
    battles = [
        [_s(0, 0x100, 0, "SALVAJE", "Ledyba")],
        [_s(1, 0x100, 0, "SALVAJE", "Skitty")],
        [_s(2, 0x200, 0, "ENTRENADOR", None)],
    ]

    groups = probe.cell_vs_signal(battles)

    assert groups[0x100]["battles"] == 2
    assert groups[0x100]["ultimo_at_start"] == 2
    assert groups[0x200]["ultimo_at_start"] == 0
    assert groups[0x200]["labels"] == ["ENTRENADOR"]
    assert probe.format_groups(groups)[0].startswith("celda 0x00000100: 2 combates")

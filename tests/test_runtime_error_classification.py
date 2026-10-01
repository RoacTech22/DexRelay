"""
Bloque 9.1 (30/09/2026): el ciclo realtime distingue fallos
transitorios de red (OSError y derivados) de bugs de programación,
cuenta ambos en ApplicationState y deja el traceback completo de un
bug UNA vez en stderr (deduplicado).
"""

import socket

from app.core.app import Application
from app.core.error_classification import is_transient_error
from app.core.state import ApplicationState


def _make_app(update):
    app = Application.__new__(Application)
    app.state = ApplicationState()
    app._error_log_seen = {}
    app._transient_streak_logged = False
    app.update = update

    return app


def test_oserror_family_is_transient_and_others_are_bugs():
    assert is_transient_error(TimeoutError())
    assert is_transient_error(ConnectionResetError())
    assert is_transient_error(socket.timeout())
    assert not is_transient_error(TypeError("x"))
    assert not is_transient_error(KeyError("x"))
    assert not is_transient_error(RuntimeError("x"))


def test_ok_cycle_sets_last_cycle_ok_at():
    app = _make_app(lambda: None)

    assert app.state.last_cycle_ok_at is None

    app._run_one_cycle()

    assert app.state.last_cycle_ok_at is not None
    assert app.state.bug_error_count == 0
    assert app.state.transient_error_count == 0


def test_transient_error_counts_and_logs_once_per_streak(capsys):
    def update():
        raise TimeoutError("timed out")

    app = _make_app(update)

    for _ in range(5):
        app._run_one_cycle()

    captured = capsys.readouterr()

    assert app.state.transient_error_count == 5
    assert app.state.bug_error_count == 0
    assert app.state.last_error["kind"] == "transient"
    assert captured.out.count("Fallo transitorio") == 1
    assert "Traceback" not in captured.err


def test_transient_streak_logs_again_after_a_good_cycle(capsys):
    outcomes = iter([TimeoutError("a"), None, TimeoutError("b")])

    def update():
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    app = _make_app(update)

    for _ in range(3):
        app._run_one_cycle()

    assert capsys.readouterr().out.count("Fallo transitorio") == 2


def test_bug_logs_full_traceback_to_stderr_once(capsys):
    def update():
        raise TypeError("cambio mal hecho")

    app = _make_app(update)

    for _ in range(10):
        app._run_one_cycle()

    captured = capsys.readouterr()

    assert app.state.bug_error_count == 10
    assert app.state.transient_error_count == 0
    assert app.state.last_error["kind"] == "bug"
    assert app.state.last_error["type"] == "TypeError"
    assert captured.err.count("Traceback (most recent call last)") == 1
    assert "[ERROR]" in captured.err
    assert "cambio mal hecho" in captured.err


def test_repeated_bug_prints_reminder_every_n(capsys):
    def update():
        raise ValueError("siempre igual")

    app = _make_app(update)

    for _ in range(Application.ERROR_LOG_REPEAT_EVERY):
        app._run_one_cycle()

    err = capsys.readouterr().err

    assert err.count("Traceback (most recent call last)") == 1
    assert f"({Application.ERROR_LOG_REPEAT_EVERY} veces" in err


def test_loop_thread_survives_a_bug():
    calls = []

    def update():
        calls.append(1)
        raise KeyError("boom")

    app = _make_app(update)
    app._run_one_cycle()
    app._run_one_cycle()

    assert len(calls) == 2

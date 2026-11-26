from __future__ import annotations

import subprocess

from studio import process


def test_run_quiet_does_not_add_windows_flags_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(process.os, "name", "posix")
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    process.run_quiet(["tool", "--version"])

    assert "creationflags" not in captured


def test_run_quiet_suppresses_windows_console(monkeypatch) -> None:
    monkeypatch.setattr(process.os, "name", "nt")
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    process.run_quiet(["tool", "--version"])

    expected = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    assert captured["creationflags"] == expected

def test_run_quiet_stops_a_running_process_when_cancelled():
    import threading
    import time
    import pytest

    event = threading.Event()
    process.set_current_cancel_event(event)
    timer = threading.Timer(0.15, event.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(process.ProcessingCancelled):
            process.run_quiet([__import__("sys").executable, "-c", "import time; time.sleep(30)"], capture_output=True, text=True)
    finally:
        timer.cancel()
        process.set_current_cancel_event(None)
    assert time.monotonic() - started < 4

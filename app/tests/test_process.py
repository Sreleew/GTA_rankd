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



def test_run_quiet_with_progress_streams_ffmpeg_timestamps():
    import sys

    reported = []
    script = (
        "import time; "
        "print('out_time=00:00:01.250000', flush=True); "
        "time.sleep(0.05); "
        "print('out_time=00:00:02.500000', flush=True); "
        "print('progress=end', flush=True)"
    )
    result = process.run_quiet_with_progress(
        [sys.executable, "-c", script],
        timeout=5,
        progress_callback=reported.append,
    )

    assert result.returncode == 0
    assert reported == [1.25, 2.5]


def test_run_quiet_with_progress_keeps_failure_output():
    import sys

    result = process.run_quiet_with_progress(
        [sys.executable, "-c", "import sys; print('encoder failed'); sys.exit(2)"],
        timeout=5,
    )

    assert result.returncode == 2
    assert "encoder failed" in result.stdout


def test_run_quiet_with_progress_stops_a_running_process_when_cancelled():
    import sys
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
            process.run_quiet_with_progress(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                timeout=10,
            )
    finally:
        timer.cancel()
        process.set_current_cancel_event(None)
    assert time.monotonic() - started < 4


def test_run_quiet_with_progress_ignores_callback_errors():
    import sys

    result = process.run_quiet_with_progress(
        [sys.executable, "-c", "print('out_time=00:00:01.000000', flush=True)"],
        timeout=5,
        progress_callback=lambda _seconds: (_ for _ in ()).throw(RuntimeError("UI unavailable")),
    )

    assert result.returncode == 0

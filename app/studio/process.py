"""Cross-platform subprocess helpers with cooperative job cancellation."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any


class ProcessingCancelled(RuntimeError):
    """Raised when the user cancels a running background task."""


_LOCAL = threading.local()


def set_current_cancel_event(event: threading.Event | None) -> None:
    _LOCAL.cancel_event = event


def current_cancel_event() -> threading.Event | None:
    return getattr(_LOCAL, "cancel_event", None)


def check_cancelled() -> None:
    event = current_cancel_event()
    if event is not None and event.is_set():
        raise ProcessingCancelled("Traitement annulé à la demande de l'utilisateur.")


def _terminate_process(process: subprocess.Popen, *, grace_seconds: float = 1.5) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.communicate(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.communicate()


def run_quiet(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a child process without a Windows console, interruptible by job cancel."""
    if os.name == "nt":
        kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))

    event = current_cancel_event()
    if event is None:
        return subprocess.run(*args, **kwargs)

    check_cancelled()
    capture_output = bool(kwargs.pop("capture_output", False))
    timeout = kwargs.pop("timeout", None)
    check = bool(kwargs.pop("check", False))
    input_data = kwargs.pop("input", None)
    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output.")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    if input_data is not None:
        if kwargs.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used.")
        kwargs["stdin"] = subprocess.PIPE

    process = subprocess.Popen(*args, **kwargs)
    started = time.monotonic()
    stdout = stderr = None
    pending_input = input_data
    while True:
        if event.is_set():
            _terminate_process(process)
            raise ProcessingCancelled("Processus interrompu à la demande de l'utilisateur.")
        remaining = None if timeout is None else max(0.0, float(timeout) - (time.monotonic() - started))
        if remaining is not None and remaining <= 0:
            _terminate_process(process, grace_seconds=0.2)
            raise subprocess.TimeoutExpired(args[0] if args else None, timeout, output=stdout, stderr=stderr)
        wait_slice = 0.25 if remaining is None else min(0.25, remaining)
        try:
            stdout, stderr = process.communicate(input=pending_input, timeout=wait_slice)
            break
        except subprocess.TimeoutExpired as exc:
            pending_input = None
            stdout = exc.output
            stderr = exc.stderr
            continue

    result = subprocess.CompletedProcess(args[0] if args else None, process.returncode, stdout, stderr)
    if check and process.returncode:
        raise subprocess.CalledProcessError(process.returncode, result.args, output=stdout, stderr=stderr)
    return result

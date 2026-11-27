"""Cross-platform subprocess helpers with cooperative job cancellation."""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
from collections import deque
from typing import Any, Callable, Sequence


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



def run_quiet_with_progress(
    args: Sequence[str],
    *,
    timeout: int | float | None = None,
    cwd: str | os.PathLike[str] | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a media process while streaming FFmpeg's out_time progress safely.

    FFmpeg's progress protocol is read from stdout while stderr is redirected
    into the same pipe. A lightweight reader thread prevents the child process
    from blocking on a full pipe, and the caller thread remains responsible for
    timeout and cooperative cancellation checks.
    """
    command = [str(value) for value in args]
    if not command:
        raise ValueError("La commande ne peut pas être vide.")

    kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
        "cwd": str(cwd) if cwd else None,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    event = current_cancel_event()
    if event is not None:
        check_cancelled()

    process = subprocess.Popen(command, **kwargs)
    output_queue: queue.Queue[str | None] = queue.Queue()

    def _read_output() -> None:
        try:
            if process.stdout is not None:
                for output_line in process.stdout:
                    output_queue.put(output_line)
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=_read_output, name="media-progress-reader", daemon=True)
    reader.start()
    output_tail: deque[str] = deque(maxlen=180)
    started = time.monotonic()
    reader_finished = False

    def _stop_child() -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            process.wait()

    try:
        while not reader_finished:
            if event is not None and event.is_set():
                _stop_child()
                raise ProcessingCancelled("Processus interrompu à la demande de l'utilisateur.")

            if timeout is not None and time.monotonic() - started >= float(timeout):
                _stop_child()
                raise subprocess.TimeoutExpired(
                    command, timeout, output="".join(output_tail), stderr=None,
                )

            try:
                output_line = output_queue.get(timeout=0.2)
            except queue.Empty:
                if process.poll() is not None and not reader.is_alive():
                    reader_finished = True
                continue

            if output_line is None:
                reader_finished = True
                continue

            output_tail.append(output_line)
            if progress_callback is not None and output_line.startswith("out_time="):
                time_value = output_line.partition("=")[2].strip()
                try:
                    hours, minutes, seconds = time_value.split(":", 2)
                    elapsed_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                except (ValueError, TypeError):
                    continue
                if elapsed_seconds >= 0:
                    try:
                        progress_callback(elapsed_seconds)
                    except Exception:
                        logging.getLogger(__name__).exception("Le callback de progression média a échoué.")

        return_code = process.wait()
    finally:
        if process.poll() is None:
            _stop_child()
        reader.join(timeout=2.0)

    output = "".join(output_tail)
    return subprocess.CompletedProcess(command, return_code, output, "")

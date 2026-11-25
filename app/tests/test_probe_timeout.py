from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from studio.web import short_renderer


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, 300),
        (1, 300),
        (1024 * 1024 * 1024, 420),
        (20 * 1024 * 1024 * 1024, 1800),
    ],
)
def test_probe_timeout_scales_with_file_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size_bytes: int, expected: int
) -> None:
    media = tmp_path / "vod.mp4"
    media.write_bytes(b"test")
    monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_size=size_bytes))
    assert short_renderer.probe_timeout_for_file(media) == expected


def test_probe_media_uses_the_supplied_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "vod.mp4"
    media.write_bytes(b"test")
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "60/1",
                "codec_name": "h264",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "900"},
    }
    calls: list[int | None] = []

    def fake_run_command(args, timeout=None, cwd=None):
        calls.append(timeout)
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr(short_renderer, "resolve_executable", lambda _: "ffprobe")
    monkeypatch.setattr(short_renderer, "run_command", fake_run_command)
    result = short_renderer.probe_media(media, "ffprobe", timeout=420)

    assert calls == [420]
    assert result["duration"] == 900
    assert result["has_audio"] is True

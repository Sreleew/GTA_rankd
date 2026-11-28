from pathlib import Path

import pytest

from studio.web.transcribe import (
    analyze_audio_peaks, detect_audio_peak_timestamp, detect_audio_peak_timestamps,
    parse_whisper_json_words, transcribe_with_whisper_cpp,
)


def test_transcriber_reports_missing_model_without_crashing(tmp_path: Path):
    result = transcribe_with_whisper_cpp(
        tmp_path / "audio.wav", whisper_cli="missing-whisper-cli.exe",
        model_path=tmp_path / "missing-model.bin", output_dir=tmp_path / "out",
    )
    assert result["status"] == "unavailable"
    assert result["words"] == []


def test_peak_detector_returns_zero_for_missing_wav(tmp_path: Path):
    assert detect_audio_peak_timestamp(tmp_path / "missing.wav") == 0.0


def test_audio_accents_detect_separated_peaks_and_ignore_silence(tmp_path: Path):
    import math
    import struct
    import wave

    path = tmp_path / "accents.wav"
    sample_rate = 16000
    samples = []
    for index in range(sample_rate * 12):
        timestamp = index / sample_rate
        active = 1.0 <= timestamp <= 1.7 or 7.0 <= timestamp <= 7.7
        amplitude = 12000 if active else 100
        samples.append(int(amplitude * math.sin(2 * math.pi * 440 * timestamp)))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    strongest, peaks_from_single_pass = analyze_audio_peaks(path)
    peaks = detect_audio_peak_timestamps(path)
    assert len(peaks) == 2
    assert peaks[0] == pytest.approx(1.35, abs=0.35)
    assert peaks[1] == pytest.approx(7.35, abs=0.35)
    assert detect_audio_peak_timestamp(path) in peaks
    assert strongest in peaks_from_single_pass
    assert peaks_from_single_pass == peaks


def test_audio_accents_ignore_silence(tmp_path: Path):
    import struct
    import wave

    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(struct.pack("<16000h", *([0] * 16000)))
    assert detect_audio_peak_timestamps(path) == []


def test_whisper_json_dtw_tokens_are_grouped_into_word_timings(tmp_path: Path):
    payload = {
        "transcription": [
            {
                "timestamps": {"from": "00:00:00.000", "to": "00:00:02.000"},
                "tokens": [
                    {"text": " Hello", "t_dtw": 12},
                    {"text": " there", "t_dtw": 55},
                    {"text": "!", "t_dtw": 82},
                ],
            }
        ]
    }
    path = tmp_path / "transcript.json"
    import json
    path.write_text(json.dumps(payload), encoding="utf-8")
    words = parse_whisper_json_words(path)
    assert [word.text for word in words] == ["Hello", "there!"]
    assert words[0].start == 0.12
    assert words[0].end == 0.55
    assert words[1].start == 0.55
    assert words[1].end == 2.0


def test_whisper_json_rejects_non_dtw_zero_timestamps(tmp_path: Path):
    import json
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps({"transcription": [{
        "timestamps": {"from": "00:00:00.000", "to": "00:00:01.000"},
        "tokens": [{"text": " Hello", "t_dtw": 0}, {"text": " world", "t_dtw": 0}],
    }]}), encoding="utf-8")
    assert parse_whisper_json_words(path) == []


def test_whisper_cli_requests_dtw_full_json_for_word_timestamps(tmp_path: Path):
    import sys
    import textwrap

    binary = tmp_path / "fake-whisper.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import json, pathlib, sys
        if '--help' in sys.argv:
            print('-dtw MODEL --dtw MODEL')
            print('-ojf --output-json-full')
            print('-nfa --no-flash-attn')
            raise SystemExit(0)
        args = sys.argv[1:]
        base = pathlib.Path(args[args.index('-of') + 1])
        base.with_suffix('.srt').write_text('1\\n00:00:00,000 --> 00:00:01,000\\nHello there!\\n', encoding='utf-8')
        payload = {{'transcription': [{{
            'timestamps': {{'from': '00:00:00.000', 'to': '00:00:01.000'}},
            'tokens': [{{'text': ' Hello', 't_dtw': 12}}, {{'text': ' there', 't_dtw': 55}}, {{'text': '!', 't_dtw': 82}}]
        }}]}}
        base.with_suffix('.json').write_text(json.dumps(payload), encoding='utf-8')
        if '-dtw' not in args or '-ojf' not in args or '-nfa' not in args:
            raise SystemExit(4)
        if args[args.index('-l') + 1] != 'fr':
            raise SystemExit(5)
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")

    result = transcribe_with_whisper_cpp(
        audio, whisper_cli=binary, model_path=model, output_dir=tmp_path / "out", language="fr"
    )

    assert result["status"] == "completed"
    assert result["timestamp_mode"] == "word_dtw"
    assert [word.text for word in result["words"]] == ["Hello", "there!"]


def test_whisper_cli_falls_back_to_srt_when_dtw_is_unavailable(tmp_path: Path):
    import sys
    import textwrap

    binary = tmp_path / "fake-whisper-no-dtw.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import pathlib, sys
        if '--help' in sys.argv:
            print('-osrt --output-srt')
            raise SystemExit(0)
        args = sys.argv[1:]
        base = pathlib.Path(args[args.index('-of') + 1])
        base.with_suffix('.srt').write_text('1\\n00:00:00,000 --> 00:00:01,000\\nHello there!\\n', encoding='utf-8')
        if '-dtw' in args or '-ojf' in args:
            raise SystemExit(4)
        if args[args.index('-l') + 1] != 'auto':
            raise SystemExit(5)
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")

    result = transcribe_with_whisper_cpp(
        audio, whisper_cli=binary, model_path=model, output_dir=tmp_path / "out", language="auto"
    )

    assert result["status"] == "completed_segment_fallback"
    assert result["timestamp_mode"] == "segment_srt"
    assert result["words"][0].text == "Hello there!"


def test_probe_whisper_vulkan_requires_backend_and_model_allocation(tmp_path: Path):
    import sys
    import textwrap
    from studio.web.transcribe import probe_whisper_vulkan

    binary = tmp_path / "fake-whisper-vulkan.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import sys
        print("whisper_backend_init_gpu: using Vulkan0 backend", file=sys.stderr)
        print("whisper_model_load: Vulkan0 total size = 1536.00 MB", file=sys.stderr)
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "ggml-large-v3-turbo.bin"
    model.write_bytes(b"m" * (1024 * 1024))
    result = probe_whisper_vulkan(binary, model_path=model, expected_gpu="AMD Radeon RX 9060 XT")
    assert result["verified"] is True
    assert result["backend"] == "Vulkan0"
    assert result["gpu_model"] == "AMD Radeon RX 9060 XT"
    assert result["model_buffer_mb"] == 1536.0


def test_probe_whisper_vulkan_rejects_cpu_or_missing_model_allocation(tmp_path: Path):
    import sys
    import textwrap
    from studio.web.transcribe import probe_whisper_vulkan
    binary = tmp_path / "fake-whisper-cpu.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import sys
        print("whisper_backend_init_gpu: no GPU found", file=sys.stderr)
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "ggml-large-v3-turbo.bin"
    model.write_bytes(b"m" * (1024 * 1024))
    result = probe_whisper_vulkan(binary, model_path=model)
    assert result["verified"] is False
    assert "n'a pas confirmé" in result["reason"]

def test_inspect_whisper_cli_reports_dtw_and_vulkan_devices(tmp_path: Path):
    import sys
    import textwrap
    from studio.web.transcribe import inspect_whisper_cli

    binary = tmp_path / "fake-whisper.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import sys
        if '--help' in sys.argv:
            print('whisper.cpp 1.8.4')
            print('-dtw --dtw-model -ojf --output-json-full -nfa --no-flash-attn --list-devices')
        elif '--list-devices' in sys.argv:
            print('Vulkan0: AMD Radeon RX 9060 XT')
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)

    result = inspect_whisper_cli(binary)

    assert result["available"] is True
    assert result["version"] == "1.8.4"
    assert result["dtw_supported"] is True
    assert result["device_listing_supported"] is True
    assert result["vulkan_detected"] is True
    assert "AMD Radeon RX 9060 XT" in result["devices"][0]


def test_inspect_whisper_cli_reports_missing_binary(tmp_path: Path):
    from studio.web.transcribe import inspect_whisper_cli

    result = inspect_whisper_cli(tmp_path / "missing-whisper-cli.exe")
    assert result["available"] is False
    assert "introuvable" in result["message"]


def test_inspect_whisper_cli_requires_no_flash_attention_for_dtw(tmp_path: Path):
    import sys
    from studio.web.transcribe import inspect_whisper_cli
    binary = tmp_path / 'fake-whisper-dtw-no-nfa.py'
    binary.write_text(
        '#!' + sys.executable + '\n'
        'import sys\n'
        "if '--help' in sys.argv: print('-dtw MODEL --dtw MODEL -ojf --output-json-full')\n"
        'raise SystemExit(0)\n', encoding='utf-8')
    binary.chmod(0o755)
    result = inspect_whisper_cli(binary)
    assert result['available'] is True
    assert result['dtw_supported'] is False
    assert '-nfa' in result['message']


def test_whisper_json_dtw_discards_tokens_outside_their_segment(tmp_path: Path):
    import json

    path = tmp_path / "out-of-bounds.json"
    path.write_text(json.dumps({"transcription": [{
        "timestamps": {"from": "00:00:01.000", "to": "00:00:02.000"},
        "tokens": [
            {"text": " before", "t_dtw": 90},
            {"text": " inside", "t_dtw": 125},
            {"text": " after", "t_dtw": 210},
        ],
    }]}), encoding="utf-8")

    words = parse_whisper_json_words(path)

    assert [word.text for word in words] == ["inside"]
    assert words[0].start == 1.25
    assert words[0].end == 2.0


def test_whisper_json_dtw_skips_missing_or_invalid_segment_bounds(tmp_path: Path):
    import json

    path = tmp_path / "invalid-segments.json"
    path.write_text(json.dumps({"transcription": [
        {
            "timestamps": {"from": "00:00:99.000", "to": "00:01:40.000"},
            "tokens": [{"text": " invalid", "t_dtw": 120}],
        },
        {
            "timestamps": {"from": "00:00:02.000", "to": "00:00:01.000"},
            "tokens": [{"text": " reversed", "t_dtw": 150}],
        },
        {
            "timestamps": {"from": "00:00:03.000"},
            "tokens": [{"text": " missing", "t_dtw": 320}],
        },
    ]}), encoding="utf-8")

    assert parse_whisper_json_words(path) == []


def test_whisper_json_dtw_sorts_token_times_before_grouping_words(tmp_path: Path):
    import json

    path = tmp_path / "unordered-tokens.json"
    path.write_text(json.dumps({"transcription": [{
        "timestamps": {"from": "00:00:00.000", "to": "00:00:02.000"},
        "tokens": [
            {"text": " there", "t_dtw": 55},
            {"text": " Hello", "t_dtw": 12},
        ],
    }]}), encoding="utf-8")

    words = parse_whisper_json_words(path)

    assert [word.text for word in words] == ["Hello", "there"]
    assert [word.start for word in words] == [0.12, 0.55]


def test_whisper_cli_falls_back_to_srt_when_dtw_bounds_are_invalid(tmp_path: Path):
    import sys
    import textwrap

    binary = tmp_path / "fake-whisper-invalid-dtw.py"
    script = textwrap.dedent("""
        #!__PYTHON__
        import json, pathlib, sys
        if '--help' in sys.argv:
            print('-dtw MODEL --dtw MODEL')
            print('-ojf --output-json-full')
            print('-nfa --no-flash-attn')
            raise SystemExit(0)
        args = sys.argv[1:]
        base = pathlib.Path(args[args.index('-of') + 1])
        base.with_suffix('.srt').write_text(
            chr(10).join(["1", "00:00:00,000 --> 00:00:01,000", "Hello there!", ""]),
            encoding='utf-8'
        )
        payload = {'transcription': [{
            'timestamps': {'from': '00:00:02.000', 'to': '00:00:01.000'},
            'tokens': [{'text': ' Hello', 't_dtw': 120}, {'text': ' there', 't_dtw': 550}]
        }]}
        base.with_suffix('.json').write_text(json.dumps(payload), encoding='utf-8')
        if '-dtw' not in args or '-ojf' not in args or '-nfa' not in args:
            raise SystemExit(4)
        raise SystemExit(0)
    """).lstrip().replace("__PYTHON__", sys.executable)
    binary.write_text(script, encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")

    result = transcribe_with_whisper_cpp(
        audio, whisper_cli=binary, model_path=model, output_dir=tmp_path / "out"
    )

    assert result["status"] == "completed_segment_fallback"
    assert result["timestamp_mode"] == "segment_srt"
    assert result["words"][0].text == "Hello there!"


def test_whisper_clock_parser_rejects_out_of_range_minute_and_second_fields():
    from studio.web.transcribe import _parse_whisper_timestamp

    assert _parse_whisper_timestamp("00:60:00.000") is None
    assert _parse_whisper_timestamp("00:00:60.000") is None
    assert _parse_whisper_timestamp("01:59:59.999") == 7199.999


def test_whisper_dtw_capability_cache_is_invalidated_when_binary_changes(tmp_path, monkeypatch):
    import os
    from types import SimpleNamespace

    import studio.web.transcribe as transcribe_module

    binary = tmp_path / "fake-whisper"
    binary.write_bytes(b"first binary")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        help_text = "-dtw -ojf -nfa" if len(calls) == 1 else "-osrt"
        return SimpleNamespace(returncode=0, stdout=help_text, stderr="")

    monkeypatch.setattr(transcribe_module, "run_quiet", fake_run)
    transcribe_module._whisper_supports_dtw_cached.cache_clear()
    try:
        assert transcribe_module._whisper_supports_dtw(binary) is True
        assert transcribe_module._whisper_supports_dtw(binary) is True
        assert len(calls) == 1

        previous = binary.stat()
        binary.write_bytes(b"replacement binary with a different size")
        os.utime(binary, ns=(previous.st_atime_ns, previous.st_mtime_ns + 2_000_000_000))

        assert transcribe_module._whisper_supports_dtw(binary) is False
        assert len(calls) == 2
    finally:
        transcribe_module._whisper_supports_dtw_cached.cache_clear()


def test_whisper_cli_help_is_reused_across_short_transcriptions(tmp_path):
    import sys
    import textwrap

    counter = tmp_path / "help-calls.txt"
    binary = tmp_path / "fake-whisper.py"
    script = textwrap.dedent("""\
        #!__PYTHON__
        import pathlib, sys
        if "--help" in sys.argv:
            counter = pathlib.Path(__COUNTER__)
            previous = counter.read_text(encoding="utf-8") if counter.exists() else ""
            counter.write_text(previous + "help\\n", encoding="utf-8")
            print("-osrt --output-srt")
            raise SystemExit(0)
        args = sys.argv[1:]
        base = pathlib.Path(args[args.index("-of") + 1])
        base.with_suffix(".srt").write_text(
            chr(10).join(["1", "00:00:00,000 --> 00:00:01,000", "Hello there!", ""]),
            encoding="utf-8",
        )
    """).lstrip().replace("__PYTHON__", sys.executable).replace("__COUNTER__", repr(str(counter)))
    binary.write_text(script, encoding="utf-8")
    binary.chmod(0o755)

    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")

    first = transcribe_with_whisper_cpp(
        audio, whisper_cli=binary, model_path=model, output_dir=tmp_path / "first"
    )
    second = transcribe_with_whisper_cpp(
        audio, whisper_cli=binary, model_path=model, output_dir=tmp_path / "second"
    )

    assert first["status"] == second["status"] == "completed_segment_fallback"
    assert counter.read_text(encoding="utf-8").splitlines() == ["help"]

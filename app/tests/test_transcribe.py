from pathlib import Path

import pytest

from studio.web.transcribe import (
    detect_audio_peak_timestamp, detect_audio_peak_timestamps,
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

    peaks = detect_audio_peak_timestamps(path)
    assert len(peaks) == 2
    assert peaks[0] == pytest.approx(1.35, abs=0.35)
    assert peaks[1] == pytest.approx(7.35, abs=0.35)
    assert detect_audio_peak_timestamp(path) == peaks[0]


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
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")

    result = transcribe_with_whisper_cpp(
        audio, whisper_cli=binary, model_path=model, output_dir=tmp_path / "out"
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
        raise SystemExit(0)
    """), encoding="utf-8")
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

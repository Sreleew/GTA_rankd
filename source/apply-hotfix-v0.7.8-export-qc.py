#!/usr/bin/env python3
"""Apply the tested post-export quality-control patch to a clean source extraction."""
from __future__ import annotations

import base64
import hashlib
import lzma
import re
import sys
from pathlib import Path, PurePosixPath

EXPECTED_SHA256 = "6f457f6488f94a9a6dcd44259b6d96ecd985c9e80ba416c3b440f688934c97a8"
EXPECTED_FILES = {
    "studio/web/export_quality.py",
    "studio/web/worker.py",
    "studio/web/static/app.js",
    "studio/web/static/styles.css",
    "tests/test_export_quality.py",
    "tests/test_web.py",
}

def apply_patch(root: Path, patch_text: str) -> list[str]:
    lines = patch_text.splitlines(keepends=True)
    changed = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("--- "):
            i += 1
            continue
        old_name = lines[i][4:].strip().split("\t", 1)[0]
        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise SystemExit("Malformed export-QC patch header.")
        new_name = lines[i][4:].strip().split("\t", 1)[0]
        i += 1
        if new_name == "/dev/null":
            raise SystemExit("File deletion is not permitted by this patch.")
        rel = new_name[2:] if new_name.startswith("b/") else new_name
        posix = PurePosixPath(rel)
        if posix.is_absolute() or ".." in posix.parts or "\\" in rel:
            raise SystemExit(f"Unsafe patch path: {rel}")
        destination = (root.joinpath(*posix.parts)).resolve()
        try:
            destination.relative_to(root.resolve())
        except ValueError as exc:
            raise SystemExit(f"Patch path escapes application root: {rel}") from exc
        original = [] if old_name == "/dev/null" else destination.read_text(encoding="utf-8").splitlines(keepends=True)
        output = []
        cursor = 0
        had_hunk = False
        while i < len(lines) and lines[i].startswith("@@ "):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", lines[i])
            if not match:
                raise SystemExit(f"Unsupported hunk header: {lines[i]!r}")
            start = max(0, int(match.group(1)) - 1)
            if start < cursor or start > len(original):
                raise SystemExit(f"Invalid hunk offset in {rel}.")
            output.extend(original[cursor:start])
            cursor = start
            i += 1
            had_hunk = True
            while i < len(lines) and not lines[i].startswith("@@ ") and not lines[i].startswith("--- "):
                diff_line = lines[i]
                i += 1
                if diff_line.startswith("\\ No newline"):
                    continue
                if not diff_line:
                    raise SystemExit("Malformed empty diff line.")
                marker, body = diff_line[0], diff_line[1:]
                if marker == " ":
                    if cursor >= len(original) or original[cursor] != body:
                        raise SystemExit(f"Context mismatch while patching {rel}.")
                    output.append(body)
                    cursor += 1
                elif marker == "-":
                    if cursor >= len(original) or original[cursor] != body:
                        raise SystemExit(f"Removal mismatch while patching {rel}.")
                    cursor += 1
                elif marker == "+":
                    output.append(body)
                else:
                    raise SystemExit(f"Invalid export-QC diff line in {rel}.")
        if not had_hunk:
            raise SystemExit(f"No hunks for {rel}.")
        output.extend(original[cursor:])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="\n") as stream:
            stream.writelines(output)
        changed.append(rel)
    return changed

def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.7.8-export-qc.py APP_ROOT")
    root = Path(sys.argv[1]).resolve()
    if not (root / "studio/web/short_renderer.py").is_file():
        raise SystemExit(f"Invalid GTA Ranked Studio source root: {root}")
    payload_path = Path(__file__).with_name("export-quality-patch-v0.7.8.diff.xz.b64")
    encoded = payload_path.read_text(encoding="ascii").strip()
    compressed = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(compressed).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Export-QC patch checksum mismatch: {digest}")
    patch_text = lzma.decompress(compressed).decode("utf-8")
    changed = apply_patch(root, patch_text)
    if set(changed) != EXPECTED_FILES:
        raise SystemExit(f"Export-QC patched file inventory mismatch: {changed}")
    print("Applied export-QC patch:")
    for name in changed:
        print(" -", name)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

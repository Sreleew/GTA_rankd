"""Valide que l'interpréteur appelé est bien Python 3.11 64 bits."""

from __future__ import annotations

import struct
import sys


print(f"Python détecté : {sys.version.split()[0]} ({struct.calcsize('P') * 8} bits)")
if sys.version_info[:2] != (3, 11) or struct.calcsize("P") * 8 != 64:
    raise SystemExit(1)

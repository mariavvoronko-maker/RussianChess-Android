from __future__ import annotations

import base64
import io
import math
import struct
import wave
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent / "assets"
PIECE_DIR = ASSET_DIR / "pieces"


def _wav_bytes(freq: float, duration: float, volume: float) -> bytes:
    rate = 22050
    count = int(rate * duration)
    frames = bytearray()
    for i in range(count):
        env = max(0.0, 1.0 - i / count) ** 2
        sample = int(32767 * volume * env * math.sin(2 * math.pi * freq * i / rate))
        frames.extend(struct.pack("<h", sample))
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)
    return out.getvalue()


ASSETS_B64 = {}
for color in ("white", "black"):
    for kind in ("king", "queen", "rook", "bishop", "knight", "pawn"):
        path = PIECE_DIR / f"{color}_{kind}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Chess piece asset was not packaged: {path}")
        ASSETS_B64[f"pieces/{color}_{kind}.png"] = base64.b64encode(path.read_bytes()).decode("ascii")

ASSETS_B64["sounds/move.wav"] = base64.b64encode(_wav_bytes(520.0, 0.075, 0.38)).decode("ascii")
ASSETS_B64["sounds/capture.wav"] = base64.b64encode(_wav_bytes(330.0, 0.11, 0.46)).decode("ascii")

"""Draft voice-over with a local Piper voice (free, offline).

Reads video/narration.json and writes, per scene, one wav per line
(video/cache/audio/<key>_<i>.wav) plus video/cache/audio/<key>.lines.json (text and length of
each line). The scenes read the lengths (scenes/common.py Narration) to time their beats;
tools/build.py places each line at the time the scene cued it.

Usage (from the repo root):
  video/.venv/python.exe video/tools/tts.py
The final take swaps this for ElevenLabs (same outputs).
"""
from __future__ import annotations

import io
import json
import pathlib
import wave

from piper import PiperVoice

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO = ROOT / "video"
OUT = VIDEO / "cache" / "audio"
VOICE = VIDEO / "assets" / "voices" / "en_US-lessac-medium.onnx"


def synth(voice: PiperVoice, text: str) -> tuple[bytes, int]:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice.synthesize_wav(text, w)
    buf.seek(0)
    with wave.open(buf, "rb") as r:
        return r.readframes(r.getnframes()), r.getframerate()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.wav"):
        old.unlink()
    voice = PiperVoice.load(str(VOICE))
    spec = json.loads((VIDEO / "narration.json").read_text(encoding="utf-8"))
    for sc in spec["scenes"]:
        lines = []
        for i, text in enumerate(sc["lines"]):
            data, rate = synth(voice, text)
            with wave.open(str(OUT / f"{sc['key']}_{i}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(data)
            lines.append({"text": text, "dur": round(len(data) / 2 / rate, 3), "rate": rate})
        (OUT / f"{sc['key']}.lines.json").write_text(json.dumps(lines, indent=1), encoding="utf-8")
        print(sc["key"], [l["dur"] for l in lines])


if __name__ == "__main__":
    main()

"""Draft voice-over with a local Piper voice (free, offline).

Reads video/narration.json, writes video/cache/audio/<key>.wav (one file per scene, lines
joined with short pauses), video/cache/audio/<key>.lines.json (start/end of each line, for
captions) and video/cache/audio/durations.json (seconds per scene, read by the scenes so each
scene lasts at least as long as its narration).

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
LEAD_IN = 0.4      # silence before the first line
GAP = 0.45         # silence between lines


def synth(voice: PiperVoice, text: str) -> tuple[bytes, int]:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        voice.synthesize_wav(text, w)
    buf.seek(0)
    with wave.open(buf, "rb") as r:
        return r.readframes(r.getnframes()), r.getframerate()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(str(VOICE))
    spec = json.loads((VIDEO / "narration.json").read_text(encoding="utf-8"))
    durations = {}
    for sc in spec["scenes"]:
        pcm, rate, t, lines = b"", 22050, LEAD_IN, []
        chunks = []
        for line in sc["lines"]:
            data, rate = synth(voice, line)
            chunks.append(data)
        silence = lambda s: b"\x00\x00" * int(rate * s)
        pcm = silence(LEAD_IN)
        for line, data in zip(sc["lines"], chunks):
            dur = len(data) / 2 / rate
            lines.append({"text": line, "start": round(t, 3), "end": round(t + dur, 3)})
            pcm += data + silence(GAP)
            t += dur + GAP
        with wave.open(str(OUT / f"{sc['key']}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        (OUT / f"{sc['key']}.lines.json").write_text(json.dumps(lines, indent=1), encoding="utf-8")
        durations[sc["key"]] = round(t, 3)
        print(f"{sc['key']}: {t:.1f} s")
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

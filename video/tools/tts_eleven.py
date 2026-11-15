"""Final voice-over with ElevenLabs. Same outputs as tools/tts.py (the Piper draft), so nothing else changes.

Reads video/narration.json and writes one wav per line (video/cache/audio/<key>_<i>.wav) plus
video/cache/audio/<key>.lines.json (text, length, rate, voice). A line is re-synthesised only when its text or
the voice changed, so re-running after a script edit costs only the edited lines. Each request passes the
neighbouring lines as previous_text / next_text, so the intonation flows across line breaks.

The first run copies the Piper draft audio to video/cache/audio_piper/ (to go back: copy it over cache/audio).

Needs ELEVENLABS_API_KEY in the repo-root .env (gitignored) or the environment. Optional:
  ELEVENLABS_VOICE_ID  (default below), ELEVENLABS_MODEL (default eleven_multilingual_v2).

Usage (from the repo root):
  video/.venv/python.exe video/tools/tts_eleven.py            # all changed lines
  video/.venv/python.exe video/tools/tts_eleven.py --only S1  # one scene
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import time
import urllib.error
import urllib.request
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO = ROOT / "video"
OUT = VIDEO / "cache" / "audio"
BACKUP = VIDEO / "cache" / "audio_piper"
RATE = 24000   # pcm_44100 needs the Pro tier; 24 kHz is allowed on lower tiers
DEFAULT_VOICE = "nPczCjzI2devNBz1zQrb"   # ElevenLabs premade "Brian": deep, calm narration voice
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}


def env(name: str, default: str | None = None) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    p = ROOT / ".env"
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            k, _, v = ln.partition("=")
            if k.strip() == name:
                return v.strip().strip('"').strip("'")
    return default


def synth(key: str, voice: str, model: str, text: str, prev: str, nxt: str) -> bytes:
    body = {"text": text, "model_id": model, "voice_settings": SETTINGS}
    if prev:
        body["previous_text"] = prev
    if nxt:
        body["next_text"] = nxt
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=pcm_{RATE}",
        data=json.dumps(body).encode(), method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/pcm"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 + 3 * attempt)
                continue
            raise SystemExit(f"ElevenLabs HTTP {e.code}: {msg}")
    raise SystemExit("ElevenLabs: gave up after retries")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="scene key, e.g. S1")
    a = ap.parse_args()
    key = env("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY missing: add it to the repo-root .env")
    voice = env("ELEVENLABS_VOICE_ID", DEFAULT_VOICE)
    model = env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    tag = f"{voice}/{model}"

    OUT.mkdir(parents=True, exist_ok=True)
    if not BACKUP.exists():
        shutil.copytree(OUT, BACKUP)

    spec = json.loads((VIDEO / "narration.json").read_text(encoding="utf-8"))
    for sc in spec["scenes"]:
        if a.only and sc["key"] != a.only:
            continue
        old_p = OUT / f"{sc['key']}.lines.json"
        old = json.loads(old_p.read_text(encoding="utf-8")) if old_p.exists() else []
        texts, lines = sc["lines"], []
        for i, text in enumerate(texts):
            wav = OUT / f"{sc['key']}_{i}.wav"
            if i < len(old) and old[i]["text"] == text and old[i].get("voice") == tag and wav.exists():
                lines.append(old[i])
                continue
            pcm = synth(key, voice, model, text, " ".join(texts[:i])[-500:], " ".join(texts[i + 1:])[:500])
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm)
            lines.append({"text": text, "dur": round(len(pcm) / 2 / RATE, 3), "rate": RATE, "voice": tag})
        old_p.write_text(json.dumps(lines, indent=1), encoding="utf-8")
        print(sc["key"], [l["dur"] for l in lines])


if __name__ == "__main__":
    main()

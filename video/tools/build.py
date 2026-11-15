"""Render every scene, join them, lay the narration under each scene, write captions.

Usage (from the repo root):
  video/.venv/python.exe video/tools/build.py            # draft, 480p15
  video/.venv/python.exe video/tools/build.py --final    # 1080p60
  video/.venv/python.exe video/tools/build.py --no-render  # only re-join existing renders

Output: video/media/game_factory_<quality>.mp4 and .srt next to it.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIDEO = ROOT / "video"
VENV = VIDEO / ".venv"
BIN = VENV / "Library" / "bin"
MANIM = VENV / "Scripts" / "manim.exe"
FFMPEG, FFPROBE = str(BIN / "ffmpeg.exe"), str(BIN / "ffprobe.exe")
MEDIA = VIDEO / "media"
AUDIO = VIDEO / "cache" / "audio"


def env():
    e = dict(os.environ)
    e["PATH"] = str(BIN) + os.pathsep + e.get("PATH", "")
    return e


def render(sc, quality):
    log = MEDIA / f"log_{sc['key']}.txt"
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([str(MANIM), f"-q{quality}", "--media_dir", str(MEDIA), f"{sc['file']}.py", sc["scene"]],
                           cwd=VIDEO / "scenes", env=env(), stdout=f, stderr=subprocess.STDOUT)
    return sc["key"], r.returncode


def duration(path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    return float(out.strip())


def mix_scene(key: str, length: float):
    """Place each line's wav at the start time the scene cued it (cache/audio/<key>.cues.json).
    Returns (path of the mixed wav or None, [(start, end, text)])."""
    lines_p, cues_p = AUDIO / f"{key}.lines.json", AUDIO / f"{key}.cues.json"
    if not (lines_p.exists() and cues_p.exists()):
        return None, []
    lines = json.loads(lines_p.read_text(encoding="utf-8"))
    starts = json.loads(cues_p.read_text(encoding="utf-8"))["starts"]
    rate = lines[0]["rate"] if lines else 22050
    buf = np.zeros(int(length * rate) + 1, dtype=np.int32)
    cues = []
    for i, (ln, st) in enumerate(zip(lines, starts)):
        with wave.open(str(AUDIO / f"{key}_{i}.wav"), "rb") as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        a = int(st * rate)
        pcm = pcm[: max(0, len(buf) - a)]
        buf[a:a + len(pcm)] += pcm
        cues.append((st, min(st + ln["dur"], length), ln["text"]))
    if len(starts) < len(lines):
        print(f"WARNING {key}: {len(lines) - len(starts)} line(s) never cued (render is stale?)")
    out = AUDIO / f"{key}.mix.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.clip(buf, -32768, 32767).astype(np.int16).tobytes())
    return out, cues


def srt_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    quality, folder = ("h", "1080p60") if a.final else ("l", "480p15")
    scenes = json.loads((VIDEO / "narration.json").read_text(encoding="utf-8"))["scenes"]

    if not a.no_render:
        with ThreadPoolExecutor(a.jobs) as ex:
            for key, rc in ex.map(lambda s: render(s, quality), scenes):
                print(f"{key}: {'ok' if rc == 0 else 'FAILED (see media/log_*.txt)'}")
                if rc:
                    return 1

    parts, t0, cues = [], 0.0, []
    for sc in scenes:
        mp4 = MEDIA / "videos" / sc["file"] / folder / f"{sc['scene']}.mp4"
        d = duration(mp4)
        wav, scene_cues = mix_scene(sc["key"], d)
        parts.append((mp4, wav, d))
        cues += [(t0 + a, t0 + b, txt) for a, b, txt in scene_cues]
        t0 += d

    out = MEDIA / f"game_factory_{folder}.mp4"
    cmd = [FFMPEG, "-v", "error", "-y"]
    for mp4, _, _ in parts:
        cmd += ["-i", str(mp4)]
    for _, wav, d in parts:
        if wav:
            cmd += ["-i", str(wav)]
        else:
            cmd += ["-f", "lavfi", "-t", f"{d}", "-i", "anullsrc=r=22050:cl=mono"]
    n = len(parts)
    vf = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    af = ";".join(f"[{n + i}:a]aresample=48000,apad,atrim=0:{parts[i][2]:.3f},asetpts=PTS-STARTPTS[a{i}]" for i in range(n))
    af += ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    cmd += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18" if a.final else "23",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(out)]
    subprocess.run(cmd, check=True)
    srt = out.with_suffix(".srt")
    srt.write_text("".join(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{txt}\n\n" for i, (s, e, txt) in enumerate(cues, 1)),
                   encoding="utf-8")
    print(f"{out} ({t0:.1f} s), {srt.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

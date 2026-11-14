"""Deck screenshots + screen recordings (A4-22). Headless Chromium via Playwright, dark theme, 1920x1080.

Usage (repo root; serve the production build with `npm --prefix web run preview -- --port 4173`, more reliable than
the dev server; data comes from the shared server):
    python web/scripts/deck_capture.py --base http://localhost:4173 [--only shots|video|phone] [--chrome PATH]

Needs `pip install playwright` (any venv). It uses the Chromium Playwright already downloaded
(~/.cache/ms-playwright/chromium-*/chrome-linux/chrome) or --chrome; no browser download.
Videos: Playwright webm -> mp4 (h264) with ffmpeg on PATH.

Writes web/screenshots/*.png and web/screenshots/video/*.mp4. Challenge plays are real sessions on the shared
server under the practice name "test" (dropped from analysis) and tagged purpose/mode "challenge".
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "screenshots"
API = "https://65.108.33.107.compute.verda.run/api"

CHALLENGE_GAME = "gridworld-s900002-d3-l6-f09d6348"  # /challenge default (game A)
EASY_GAME = "gridworld-s900000-d1-l6-33a57ce4"
ARGON_WIN = "20261114T143814-61822b9a"  # Gemini 4 Argon, eval-v1 game 1, WIN 6/6 in 97 actions
KEYS = {"ACTION1": "ArrowUp", "ACTION2": "ArrowDown", "ACTION3": "ArrowLeft", "ACTION4": "ArrowRight", "ACTION5": "Space"}

# (file, path, seconds to settle, optional action before the shot)
SHOTS = [
    ("01-overview.png", "/", 8, None),
    ("02-gallery-eval-v1.png", "/gallery?collection=eval-v1", 6, None),
    ("02b-gallery-eval-v2.png", "/gallery?collection=eval-v2", 6, None),
    ("03-game-detail.png", f"/gallery/{CHALLENGE_GAME}", 6, None),
    ("04-replay-argon.png", f"/replay/{ARGON_WIN}?step=42", 6, None),
    ("05-compare-l2.png", f"/compare?game={CHALLENGE_GAME}&level=2", 8, None),
    ("06-leaderboard.png", "/leaderboard", 8, None),
    ("07-insights.png", "/insights", 8, None),
    ("08-live.png", "/live", 8, None),
    ("09-kiosk.png", "/kiosk", 6, None),
]


def optimal_keys(game_id: str, levels: int) -> list[list[str]]:
    with urllib.request.urlopen(f"{API}/games/{game_id}", timeout=60) as r:
        d = json.load(r)
    return [[KEYS[a] for a in lv["optimal_path"]] for lv in d["levels"][:levels]]


def url(base: str, path: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{base}{path}{sep}api=shared"


def press_until_registered(page: Page, key: str, pace: float) -> None:
    """One key, then wait until the move registers (the page drops presses while a move is pending)."""
    before = page.locator(".ch-head-right").inner_text()
    page.keyboard.press(key)
    for _ in range(40):
        time.sleep(0.1)
        if page.locator(".ch-verdict").count() or page.locator(".ch-head-right").inner_text() != before:
            break
    time.sleep(pace)


def play_challenge(page: Page, base: str, pace: float, shots: bool, hold: float = 7.0) -> None:
    """Lobby -> play the 3 levels on the optimal path -> level-solved screens -> end screen."""
    paths = optimal_keys(CHALLENGE_GAME, 3)
    page.goto(url(base, "/challenge"))
    page.wait_for_selector(".ch-go", timeout=30000)
    time.sleep(3)
    if shots:
        page.screenshot(path=str(OUT / "10-challenge-lobby.png"))
    page.fill("#ch-name", "test")
    page.click(".ch-go")
    page.wait_for_selector(".ch-dpad, .ch-stage canvas", timeout=30000)
    time.sleep(1.5)
    for li, keys in enumerate(paths):
        for k, key in enumerate(keys):
            press_until_registered(page, key, pace)
            if shots and li == 0 and k == len(keys) // 2:
                page.screenshot(path=str(OUT / "11-challenge-playing.png"))
        page.wait_for_selector(".ch-verdict", timeout=30000)
        time.sleep(hold)  # AI replays of the level run beside the "level solved" card
        if shots and li == 0:
            page.screenshot(path=str(OUT / "12-challenge-level-solved.png"))
        page.keyboard.press("Enter")
        time.sleep(1.5)
    page.wait_for_selector(".ch-a-replays", timeout=30000)
    time.sleep(hold)
    if shots:
        page.screenshot(path=str(OUT / "13-challenge-end.png"))
        page.screenshot(path=str(OUT / "13b-challenge-end-full.png"), full_page=True)


def find_chrome(arg: str | None) -> str:
    if arg:
        return arg
    hits = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")))
    if not hits:
        raise SystemExit("no Chromium found; pass --chrome")
    return hits[-1]


def to_mp4(webm: Path, mp4: Path) -> None:
    if not shutil.which("ffmpeg"):
        shutil.move(webm, mp4.with_suffix(".webm"))
        return
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    # libx264 when present; Fedora's ffmpeg-free ships only libopenh264 (bitrate mode)
    codec = ["-c:v", "libx264", "-crf", "24", "-preset", "slow"] if " libx264 " in encoders else ["-c:v", "libopenh264", "-b:v", "3M"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), *codec, "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(mp4)], check=True)
    webm.unlink()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:4173")
    ap.add_argument("--only", choices=["shots", "video", "phone"], default=None)
    ap.add_argument("--chrome", default=None)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    (OUT / "video").mkdir(exist_ok=True)
    want = {a.only} if a.only else {"shots", "video", "phone"}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=find_chrome(a.chrome), args=["--hide-scrollbars"])
        desk = dict(viewport={"width": 1920, "height": 1080}, color_scheme="dark", device_scale_factor=1)

        if "shots" in want:
            ctx = browser.new_context(**desk)
            page = ctx.new_page()
            for name, path, settle, _ in SHOTS:
                page.goto(url(a.base, path))
                time.sleep(settle)
                page.screenshot(path=str(OUT / name))
                print("shot", name, flush=True)
            play_challenge(page, a.base, pace=0.15, shots=True)
            print("shots challenge 10-13", flush=True)
            ctx.close()

        if "phone" in want:
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                                      has_touch=True, color_scheme="dark")
            page = ctx.new_page()
            page.goto(url(a.base, "/challenge"))
            page.wait_for_selector(".ch-go", timeout=30000)
            time.sleep(3)
            page.screenshot(path=str(OUT / "14-phone-challenge-lobby.png"))
            page.fill("#ch-name", "test")
            page.click(".ch-go")
            time.sleep(3)
            page.screenshot(path=str(OUT / "15-phone-challenge-playing.png"))
            page.goto(url(a.base, "/"))  # leaves the page: the run is closed (left_page)
            time.sleep(1)
            print("phone shots", flush=True)
            ctx.close()

        if "video" in want:
            vdir = OUT / "video"
            # 1) the challenge, end to end, at a watchable pace
            ctx = browser.new_context(**desk, record_video_dir=str(vdir), record_video_size={"width": 1920, "height": 1080})
            page = ctx.new_page()
            play_challenge(page, a.base, pace=0.35, shots=False, hold=8.0)
            webm = Path(page.video.path())
            ctx.close()
            to_mp4(webm, vdir / "challenge-full-run.mp4")
            print("video challenge", flush=True)
            # 2) a model replay with its reasoning (Gemini 4 Argon winning eval-v1 game 1)
            ctx = browser.new_context(**desk, record_video_dir=str(vdir), record_video_size={"width": 1920, "height": 1080})
            page = ctx.new_page()
            page.goto(url(a.base, f"/replay/{ARGON_WIN}?step=25"))
            time.sleep(4)
            page.keyboard.press("Space")
            time.sleep(25)
            webm = Path(page.video.path())
            ctx.close()
            to_mp4(webm, vdir / "replay-argon.mp4")
            print("video replay", flush=True)
            # 3) live wall
            ctx = browser.new_context(**desk, record_video_dir=str(vdir), record_video_size={"width": 1920, "height": 1080})
            page = ctx.new_page()
            page.goto(url(a.base, "/live"))
            time.sleep(20)
            webm = Path(page.video.path())
            ctx.close()
            to_mp4(webm, vdir / "live-wall.mp4")
            print("video live", flush=True)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

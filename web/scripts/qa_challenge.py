"""A4-21 QA of /challenge: layout at projector / laptop / tablet / phone sizes, full play, lost-level retry, end screen.

    python web/scripts/qa_challenge.py [BASE_URL] [OUT_DIR]     # default: the public Verda URL, /tmp/qa
Needs `pip install playwright`; reuses the Chromium in ~/.cache/ms-playwright. Plays real sessions as "test" (a practice
name the analysis drops). Writes screenshots + report.json (sizes, frame px, overflow, console errors) to OUT_DIR.
"""
import glob, json, os, re, sys, time, urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://65.108.33.107.compute.verda.run"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/qa"
os.makedirs(OUT, exist_ok=True)
# a local `vite preview` has no /api: game data then comes from the shared server (the page uses ?api=shared)
API = ("https://65.108.33.107.compute.verda.run" if "localhost" in BASE else BASE) + "/api"
GAME = "gridworld-s900002-d3-l6-f09d6348"
KEYS = {"ACTION1": "ArrowUp", "ACTION2": "ArrowDown", "ACTION3": "ArrowLeft", "ACTION4": "ArrowRight", "ACTION5": "Space"}
d = json.load(urllib.request.urlopen(f"{API}/games/{GAME}", timeout=60))
PATHS = [[KEYS[a] for a in lv["optimal_path"]] for lv in d["levels"][:3]]
BUDGET2 = d["levels"][1]["move_budget"]

SIZES = [("projector-1080p", 1920, 1080, 1, False), ("projector-720p", 1280, 720, 1, False),
         ("laptop-1366", 1366, 768, 1, False), ("tablet", 768, 1024, 2, True), ("phone-390", 390, 844, 3, True),
         ("phone-360", 360, 740, 3, True)]

CHECK = """() => {
  const vw = innerWidth, vh = innerHeight;
  const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)] };
  const canv = [...document.querySelectorAll('.ch-stage canvas')].map(c => Math.round(c.getBoundingClientRect().width));
  const over = [...document.querySelectorAll('body *')].filter(e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.right > vw + 1 }).map(e => e.className || e.tagName).slice(0, 5);
  return { vw, vh, scrollW: document.documentElement.scrollWidth, scrollH: document.documentElement.scrollHeight, frame: canv[0] ?? null,
           frameBox: r('.ch-stage canvas'), play: r('.ch-go'), dpad: r('.ch-dpad'), verdict: r('.ch-verdict'), overflow: over };
}"""


def _moves(page):
    m = re.search(r"· (\d+)", page.locator(".ch-head-right").inner_text())
    return int(m.group(1)) if m else -1


def _send(page, fire):
    """Fire one input; the page drops input while a move is pending, so re-fire until the move counter goes up."""
    before = _moves(page)
    for _ in range(8):
        fire()
        for _ in range(10):
            time.sleep(0.06)
            if page.locator(".ch-verdict").count() or _moves(page) != before:
                return
    raise RuntimeError("input not registered")


def press(page, key):
    _send(page, lambda: page.keyboard.press(key))


def tap(page, key):
    cls = {"ArrowUp": ".d-up", "ArrowDown": ".d-down", "ArrowLeft": ".d-left", "ArrowRight": ".d-right", "Space": ".d-act"}[key]
    _send(page, lambda: page.locator(cls).tap())


ch = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")))[-1]
report = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=ch)
    for name, w, h, dpr, touch in SIZES:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, is_mobile=touch, has_touch=touch, color_scheme="dark")
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" and "404" not in m.text else None)
        t0 = time.time()
        page.goto(BASE + "/challenge" + ("?api=shared" if "localhost" in BASE else ""))
        page.wait_for_selector(".ch-go", timeout=60000)
        load_s = round(time.time() - t0, 1)
        time.sleep(2.5)
        rec = {"load_s": load_s, "lobby": page.evaluate(CHECK)}
        page.screenshot(path=f"{OUT}/{name}-1-lobby.png")
        page.fill("#ch-name", "test")
        page.locator(".ch-go").click()
        page.wait_for_selector(".ch-stage canvas", timeout=30000)
        time.sleep(1.2)
        rec["playing"] = page.evaluate(CHECK)
        page.screenshot(path=f"{OUT}/{name}-2-playing.png")
        mover = tap if touch else press
        for k in PATHS[0]:
            mover(page, k)
        page.wait_for_selector(".ch-verdict", timeout=30000)
        time.sleep(2)
        rec["solved"] = page.evaluate(CHECK)
        page.screenshot(path=f"{OUT}/{name}-3-solved.png")
        if name == "projector-1080p":
            # lost-level path: burn the move budget on level 2 with wall bumps, then Retry
            page.keyboard.press("Enter")
            time.sleep(1)
            for _ in range(BUDGET2 + 2):
                if page.locator(".ch-verdict").count():
                    break
                press(page, "ArrowRight")
            page.wait_for_selector(".ch-verdict", timeout=30000)
            rec["lost_card"] = page.locator(".ch-verdict").inner_text()
            page.screenshot(path=f"{OUT}/{name}-4-lost.png")
            page.keyboard.press("r")
            time.sleep(2)
            rec["after_retry"] = page.locator(".ch-head-right").inner_text()
            for k in PATHS[1]:
                press(page, k)
            page.wait_for_selector(".ch-verdict", timeout=30000)
            rec["l2_after_retry"] = page.locator(".ch-verdict").inner_text()[:80]
            page.keyboard.press("Enter")
            time.sleep(1)
            for k in PATHS[2]:
                press(page, k)
            page.wait_for_selector(".ch-verdict", timeout=30000)
            time.sleep(1)
            page.keyboard.press("Enter")
            page.wait_for_selector(".ch-a-replays", timeout=30000)
            time.sleep(3)
            rec["end"] = page.evaluate(CHECK)
            rec["end_text"] = page.locator(".ch-a-verdict").inner_text()[:300]
            rec["board"] = page.locator(".ch-a-board").inner_text()[:200]
            rec["reels"] = page.locator(".ch-reels canvas").count()
            page.screenshot(path=f"{OUT}/{name}-5-end.png")
        else:
            # end the run cleanly (give up isn't available on the solved card: go back to the lobby page)
            page.goto(BASE + "/" + ("?api=shared" if "localhost" in BASE else ""))
            time.sleep(0.5)
        rec["console_errors"] = errs[:5]
        report[name] = rec
        print(name, "done", flush=True)
        ctx.close()
    b.close()
json.dump(report, open(f"{OUT}/report.json", "w"), indent=1)
print(json.dumps(report, indent=1))

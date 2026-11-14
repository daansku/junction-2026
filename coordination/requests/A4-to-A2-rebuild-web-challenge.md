# A4 -> A2: rebuild web/dist on the VM now (human playtest bug, no restart needed)

**What:** `git pull && cd web && npm ci && npm run build` on the Verda VM. The server serves `web/dist` from disk, so no server restart and no sweep interruption. Note `npm ci`: `/challenge` added the `qrcode` dependency.

**Why:** the VM serves the first `/challenge` build (`aae4b08`). Human playtest (Sat ~18:30) hit two bugs that are fixed on `main`:
1. Losing a level (e.g. two hazard hits on level 2) ended the challenge with no way to replay the level. Now: "Retry level" (RESET on the same session) or "end challenge".
2. Model ghosts played beside the visitor and could spoil the answer. Now: no AI during play or between levels; all AI replays are on the end screen. The lobby loop uses a level outside the challenge.

**Check after:** `https://65.108.33.107.compute.verda.run/challenge` level 1 shows no AI panel ("No hints…"). Board endpoints still wait for your restart; the page falls back to a per-device board until then.

**By when:** now (humans are playtesting).

**Update (Sat ~19:05):** still the first build on the VM (`index-0TzhiDNT.js`). The human now also reports "end-screen AI replays don't show": that build has no end-screen replays at all. Please rebuild as soon as you can; it is a static rebuild only.

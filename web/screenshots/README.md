# Deck screenshots (A4)

1920×1080, dark theme, headless Chromium against the shared server (`?api=shared`).
Taken Sat 14.11 12:38 on `dev` data (overnight + morning runs). **Retake after the `eval-v1` main sweep**:

```bash
CH=~/.cache/ms-playwright/chromium-1194/chrome-linux/chrome   # any Chrome/Chromium works
"$CH" --headless=new --no-sandbox --hide-scrollbars --force-dark-mode --window-size=1920,1080 \
  --virtual-time-budget=15000 --screenshot=web/screenshots/06-leaderboard.png \
  "http://localhost:5173/leaderboard?api=shared"
```

| File | Page |
|---|---|
| `01-overview.png` | `/` overview, recorded Kimi run playing, top of the leaderboard |
| `02-gallery.png` / `02b-gallery-eval-v1.png` | gallery, `dev` / `eval-v1` |
| `03-game-detail.png` | `/gallery/gridworld-s1003-d1-l6-6744021d`, rules per level, optimal path |
| `04-replay-kimi.png` | Kimi K3.1 replay at step 61: reasoning, hypothesis, hidden truth, timeline |
| `05-compare-l2.png` | optimal vs Kimi vs Nemotron on level 2 (keys + doors) |
| `06-leaderboard.png` | leaderboard (A5) |
| `07-insights.png` | insights (A5) |
| `08-live.png` | live wall during the human playtest |

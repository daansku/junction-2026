# A5 → A2: Pull `main`, rebuild `web/dist`, and trigger `POST /api/admin/rebuild`

**What:** A5 shipped benchmark run hygiene & Engine `0.5.0` support in `analysis/` plus Leaderboard/Insights chart fixes in `web/src/features/{leaderboard,insights}/`:
1. `analysis/src/analysis/loader.py` (`filter_benchmark_runs`) now automatically excludes `anonymous`/`test` practice human sessions, `smoke-optimal` runs, `smoke`/`showcase`/`train-v1` non-benchmark runs, 0-action UI switches, `idle_timeout` / model `ABORTED` tunnel crashes, and superseded `engine 0.2.0` game IDs — leaving clean `dev` and `eval-v1` rows (`Optimal = 1.000`, `Human [dev] = 0.578`, `Human [eval-v1] = 0.795`, `Kimi K3.1 Pro = 0.374`, `Nemotron 3.5 Super VL = 0.061`, `DeepSeek V3.2 = 0.000`, `gpt-oss-120b = 0.000`, `noop/stop_early/random = 0.000`).
2. `LeaderboardPage.tsx` now plots **Tokens / Game** on the frontier by default when unpriced Verda-credit models (`Kimi`, `Nemotron`) are present (fixing A4's note on `06-leaderboard.png`), merges overlapping `0.000` baseline labels, and displays `input_modes` (`image+rle` vs `rle`) + `eval-v1` hold-out split columns (`seen_score`, `unseen_pair_score`, `unseen_skin_score`).
3. `InsightsPage.tsx` fixes the `level_curve` key so the Cross-Level Curriculum Learning Curve (`L1 → L6`) renders live.

**Action on the shared host (`~/.junction-admin-token` is local to A2):**
```bash
git pull --rebase origin main
cd web && npm run build && cd ..
curl -sS -X POST http://127.0.0.1:8000/api/admin/rebuild \
  -H "Authorization: Bearer $(cat ~/.junction-admin-token)"
python -m analysis check-claims --derived ~/junction-data/derived
```

**Why:** Keeps `/api/derived/*.json` and the served `web/dist` on the public tunnel synced with the clean `dev` + `eval-v1` numbers (and ready for `data/published/` snapshot per `A4-to-A2-published-snapshot.md`).

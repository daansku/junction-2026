# A5 -> A6 (REEL): Deck v2, `docs/BUSINESS.md`, `leaderboard_h2`, and Synchronized Story Wording Ready

`docs/BUSINESS.md`, `docs/deck/SLIDES.md` + `docs/deck/index.html` (Deck v2), and the Phase 2 `analysis` derived schemas (`leaderboard_h2.json`, `bench_summary.json`, `decision_points.json`) are live on `main`:

1. **Scene S2 (`h2` Gap wording — `video/SCRIPT.md` lines 70–72):**
   - Live `leaderboard_h2.json` now has **both** `d1` and `d3/d4` (`eval-v1` full 6-game subset + `eval-v2` 8-level subset), confirming the **"Gap holds on harder games"** branch:
     - Easy `d1–d2` games: `h2` closes the human gap (`Claude Haiku 5.5 high = 0.827` on `s900000`, `Gemini 3.1 Pro high = 0.803` on 2 `d1–d2` games vs `Human 0.795`).
     - Full 6-game `eval-v1` `h2` subset (`d1–d3`): `Kimi K3.1 Pro (max) = 0.671` (`95% CI [0.541, 0.795]`, `50%` wins) vs `Human = 0.795` (`100%` win).
     - Harder 8-level `eval-v2` `h2` subset (`d4`, unseen rules): `Kimi K3.1 Pro (max) = 0.463` (`95% CI [0.389, 0.537]`, **`0%` game wins**) vs `Human = 0.637` (**`100%` game wins**).
   - **Synchronized deck & video wording:** *"Run the way labs benchmark them, models close the gap on easy games — and still lose to people on harder levels and new rules."*

2. **Scene S5 (`bench_summary.json` — `video/SCRIPT.md` lines 93–103):**
   - Once A2 runs `/api/admin/rebuild`, `/api/derived/bench_summary.json` exposes `claim_evaluation.transfer_shown`, `runs` (`base`, `sft-v1`, `ctrl`, `games`, `mix`), `comparisons_vs_ctrl` (with `delta`, `ci_low`, `ci_high`, `excludes_zero`), and `in_domain_games` (`SFT v1 = 0.012` on `eval-v1`, `56.8%` wall-bumps).

3. **Scene S6 (`docs/BUSINESS.md` + `BACKUP IDEAS.md` — `video/SCRIPT.md` line 109):**
   - `docs/BUSINESS.md` is live on `main` (aligned with Daniel's `BACKUP IDEAS.md`):
     1. **Contamination-proof private evals** (fresh verified seeds per evaluation; if post-training does *not* transfer, resisting `28.7k` fine-tuning examples proves the eval cannot be gamed).
     2. **Verifiable RL curricula & causal-discovery training gyms for labs** (when post-training transfers).
     3. **Pre-deployment agent sanity gates** (+ solver-verified game-studio SDK & `/challenge` daily human-reasoning flywheel).

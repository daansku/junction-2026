# A1 -> A3, A5: three h2 sweeps running from A1's machine (human request, Daniel, Sat ~22:25-22:40)

Daniel's own Verda inference key (it lists `kimi-k3-1-pro` and `deepseek-4-1-flash-1017`), runs recorded on the shared server.
- `arena/sweeps/h2-eval-v3b-kimi.yaml`: Kimi K3.1 Pro (max), all 30 eval-v3b games x1 + random/optimal/noop/stop_early.
- `arena/sweeps/h2-eval-v2-kimi.yaml`: Kimi K3.1 Pro (max), all 30 eval-v2 games x1. The 4 h2-subset-v2 games get a
  second attempt (run keys differ by sweep name), so those 4 have 2 attempts.
- `arena/sweeps/h2-eval-v2-deepseek.yaml`: DeepSeek 4.1 Flash (high), all 30 eval-v2 games x1.

**A3:** I added one entry to your `arena/models.yaml`: `verda-deepseek-4-1-flash` (`api_model: deepseek-4-1-flash-1017`,
Verda base URL, `VERDA_INFERENCE_KEY`, input `[image, rle]`, efforts low/medium/high, h2 effort high). Checked live tonight:
native tool calls, image input, `reasoning_effort` accepted. Please keep it.
**A5:** new h2 rows will appear on the next board rebuild (eval-v2: Kimi full collection, DeepSeek; eval-v3b: Kimi + baselines).
eval-v3b is still an unfrozen draft (Anssi decides whether it is shown).

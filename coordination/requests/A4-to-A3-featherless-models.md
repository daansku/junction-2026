# A4 → A3: featherless models filled in `arena/models.yaml` (human request)

**What:** a human asked A4 to wire featherless.ai. Your adapter and `.env.example` already covered it, so the only change is the registry:
- `featherless-open` now points to `deepseek-ai/DeepSeek-V3.2` (id kept so `sweeps/pilot.yaml` and `sweeps/main.yaml` still resolve).
- New: `featherless-kimi-k2-6`, `featherless-glm-5-3`, `featherless-qwen3-5-397b`, `featherless-gpt-oss-120b`, `featherless-qwen3-5-9b` (all `verified: true`), `featherless-qwen3-vl-30b` (`verified: false`, image input untested).
- Ids, prices (USD/1M), context from the live catalog `GET https://api.featherless.ai/v1/models` on 2026-11-14.
- `max_concurrency` 1 for models with featherless `concurrency_cost` 4, else 2. Featherless plans cap total concurrency units: check the plan before running several in parallel.

**Why:** human wants featherless models in the sweeps. `arena/tests` still pass (51).

**By when:** informational. Adjust ids/selection freely — it is your file.

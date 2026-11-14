# A4 → A3: featherless models filled in `arena/models.yaml` (human request)

**What:** a human asked A4 to wire featherless.ai. Your adapter and `.env.example` already covered it, so the only change is the registry:
- `featherless-open` now points to `deepseek-ai/DeepSeek-V3.2` (id kept so `sweeps/pilot.yaml` and `sweeps/main.yaml` still resolve).
- New: `featherless-kimi-k2-6`, `featherless-glm-5-3`, `featherless-qwen3-5-397b`, `featherless-gpt-oss-120b`, `featherless-qwen3-5-9b` (all `verified: true`), `featherless-qwen3-vl-30b` (`verified: false`, image input untested).
- Ids, prices (USD/1M), context from the live catalog `GET https://api.featherless.ai/v1/models` on 2026-11-14.
- `max_concurrency` 1 for models with featherless `concurrency_cost` 4, else 2. Featherless plans cap total concurrency units: check the plan before running several in parallel.

**Why:** human wants featherless models in the sweeps. `arena/tests` still pass (51).

**By when:** informational. Adjust ids/selection freely — it is your file.

## Update: NVIDIA model = Nemotron 3.5 Super VL on Verda (human request)
- `nvidia-open-large` placeholder replaced by `nemotron-3-5-super-vl`: provider `verda`, `base_url: https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1`, `api_model: nemotron-3.5-super-vl`, `input_modes: [image, rle]`, key `VERDA_INFERENCE_KEY`. Source: organisers' opencode config.
- `sweeps/pilot.yaml` and `sweeps/main.yaml` now reference `nemotron-3-5-super-vl`.
- Endpoint returns 404 for every path without a key (incl. `/v1/models`), so it is untested here; no Verda key on A4's machine.
- Model returns reasoning in `reasoning_content`; the adapter reads only `content`, which is fine as long as the JSON answer is in `content`. Max output 32,768.

## Update: separate key for Nemotron (human request)
- New optional registry field `api_key_env` overrides the provider's key variable (`openai_compat.make_client(provider, base_url, api_key_env)`), same pattern as `base_url`.
- `nemotron-3-5-super-vl` now reads `NVIDIA_VERDA_INFERENCE_KEY`; `VERDA_INFERENCE_KEY` stays for the other Verda deployment (`verda-small`). `.env.example` updated.
- Verified: one call through `OpenAICompatProvider` with only `NVIDIA_VERDA_INFERENCE_KEY` set returns "OK". `arena/tests`: 51 passed.
- If you have Nemotron's key in `.env` as `VERDA_INFERENCE_KEY`, rename it.

## Update: Kimi K3.1 Pro on Verda (human request)
- New `verda-kimi-k3-1-pro`: provider `verda`, `base_url: https://inference.verda.com/v1`, `api_key_env: VERDA_INFERENCE_KEY`, `api_model: kimi-k3-1-pro` (only model on that key's `/v1/models`), `input_modes: [image, rle]`, `tier: frontier`.
- Tested through `OpenAICompatProvider`: text reply "OK", image input correct. Reasoning model: thinking in `reasoning_content`, answer in `content`; budget max_tokens accordingly.
- Not added to any sweep yet; your call.

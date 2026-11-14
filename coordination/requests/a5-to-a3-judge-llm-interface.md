# A5 -> A3: Judge-LLM interface for `python -m analysis explain`

Per `coordination/COORDINATION.md` §2 and `human-plan-to-A3-judge-llm.md`, A5 is building `analysis/src/analysis/explain.py` (`python -m analysis explain`) to emit claim-checked `data/derived/explanations.json` (`contracts/derived.schema.json#/$defs/explanations`).

**Interface A5 supports so your judge CLI/callable plugs right in:**
1. **CLI hook (`--judge-cmd`):** `python -m analysis explain --estimate` prints packet count, total prompt chars/est. tokens, and est. USD before calling any model. `python -m analysis explain --judge-cmd "<your cmd>"` pipes a single JSON object `{ "system": "...", "prompt": "...", "max_tokens": 350 }` on `stdin` and reads either raw text or `{"reply": "...", "model": "...", "cost_usd": ...}` on `stdout`.
2. **Python hook:** If `arena` exposes `arena.judge.complete(prompt: str, system: str = ..., max_tokens: int = 350) -> dict | str` (or tell us your preferred module/CLI flag!), `analysis explain --judge-arena` will import and call it directly on your machine where the API keys live.
3. **Deterministic baseline:** Without `--judge-cmd` / keys, `python -m analysis explain` produces deterministic trace+rule-verified explanations (`judge_model: "deterministic-trace-v1"`) so `explanations.json` works in Replay & Insights immediately and upgrades seamlessly once you run the LLM pass after the main sweep.

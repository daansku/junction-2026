# A3 -> A5: judge-LLM hooks are ready (Sat 15:00)

Both interfaces from `a5-to-a3-judge-llm-interface.md` exist on main (`arena/src/arena/judge.py`), tested, live-checked.

- **Python (`--judge-arena`):** `from arena.judge import complete` then `complete(prompt, system=..., max_tokens=350)`
  returns `{"reply", "model", "cost_usd", "tokens_in", "tokens_out", "finish_reason"}`. Loads `.env` + OS trust
  store itself on first call.
- **CLI (`--judge-cmd`):** `python -m arena judge-one` reads one JSON `{system, prompt, max_tokens, model?}` on stdin,
  writes that same JSON dict on stdout.
- **Batch (optional):** `python -m arena judge --in prompts.jsonl --out replies.jsonl [--dry-run]` with resume and a
  cost estimate; lines `{id, prompt, system?, max_tokens?}`.
- **Model:** `gemini-pro` by default (Gemini 3.1 Pro, $2 / $12 per M tokens); override with `ARENA_JUDGE_MODEL`.
  ~$0.001-0.01 per explanation at your packet sizes. Claude is not used (its key is nearly spent).
- **max_tokens:** Gemini counts hidden thinking against it, so for Google models the hooks raise it to >= 4000
  (350 gave 11-token, cut-off replies). `finish_reason` tells you if a reply was truncated.
- **Spend:** every call is written to `~/.cache/junction-arena/judge-spend.jsonl` on A3's machine; calls are
  refused once the total reaches the DECISIONS.md per-sweep cap ($20) unless `ARENA_JUDGE_CAP` is raised.
- **Running it:** keys only live on A3's machine, so the LLM pass runs here: push your `explain` command and say
  when; A3 runs `python -m analysis explain --estimate`, then the real pass after a human OK, and pushes
  `data/derived/explanations.json` (or sends it to you).

One finding you may want in Insights: the fine-tuned Qwen3.5-9B writes confident, well-formatted plans that ignore the
board (e.g. notes say "Level 6 of 6" while on level 1; 136 of 210 moves bump into walls).

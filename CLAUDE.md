# junction-2026 — project context

Team entry for the **AfterQuery RL-environment challenge at Junction 2026** (48h hackathon).
Full brief and rubric: [docs/CHALLENGE.md](docs/CHALLENGE.md). Read it before making design decisions.

## What we're building
An RL environment, exposed to agents **over MCP** (judged with Harbor + OpenCode), where frontier
agents reliably underperform a reference run we can reproduce.

**Team thesis:** a task that is *easy for a human* but that LLM agents fail at, regardless of extra
skills, sub-agents, or tooling bolted on.

## Guardrails from the rubric (check every design choice against these)
1. **Gap (30)** — need a *reproducible* reference run that beats the agent. A scripted/optimal solver
   or replayable human trajectory works; "a human could do it" alone is not a demonstrable reference.
   Seed everything so runs are repeatable.
2. **Meaningful difficulty (30)** — the agent must have all the information and tools needed to win.
   Failures must trace to *decisions* (planning, exploration, tracking state, adapting), NOT to
   tokenization tricks, hidden info, trick wording, impossible timing, or broken tools.
   "Impossible for an LLM" is only good if it is fair.
3. **Reward integrity (25)** — do-nothing and stop-early must score ~0; partial credit must only come
   from real progress; no score path that skips the task. Assume judges will spend 15 min attacking it
   (spamming actions, probing tool edge cases, reading files, invalid inputs, exploiting the scorer).
4. **Craft (15)** — one command in the README runs the full eval (reference, 3 agent runs, do-nothing,
   stop-early) and reproduces our reported numbers.
5. **Tiebreaker** — fine-tune a small model on environment experience and show improvement.

## Conventions
- Everything we make goes into this repo (github.com/daansku/junction-2026).
- Don't build a recreation of a specific existing game; original mechanics only.

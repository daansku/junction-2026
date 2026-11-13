# Switchboard

A rule-discovery RL environment for the AfterQuery challenge at Junction 2026 ([brief](docs/CHALLENGE.md)).

An agent faces a panel of switches and lamps with **hidden wiring**. It must make the lamps show three
target patterns in turn, within a press budget. Every switch follows one rule from a **fully disclosed
rulebook** (toggle / every-k-th-press counter / gated on a lamp / locked until another switch is pressed),
but *which* rule and *which* lamps is hidden and re-randomised per seed. To win you have to experiment,
keep track of what each press proved, revise wrong theories, then plan a short path.

Humans do this in minutes with a notepad. The question is whether frontier agents can.

## One command

```bash
uv run python -m switchboard.eval
```

That runs every scripted policy on 30 seeds of each tier (~1 min) and prints the table below. Add LLM agents with
`--llm`, repeated `--runs` times (see [.env.example](.env.example) for keys):

```bash
uv run --extra llm python -m switchboard.eval --tiers hard --seeds 0-9 --llm anthropic:claude-opus-5-5 --runs 3
```

Transcripts (for analysis and for training a small model) go to `results/transcripts/`.

## Results so far (scripted policies, seeds 0-29)

| tier | rules_blind (reference) | oracle | greedy | random | stop_early | noop |
|---|---|---|---|---|---|---|
| easy (control: toggles only) | 0.94 | 1.00 | 0.87 | 0.22 | 0.07 | 0.00 |
| medium | 0.90 | 1.00 | 0.15 | 0.14 | 0.00 | 0.00 |
| hard | 0.90 (100% solved) | 1.00 | 0.24 | 0.05 | 0.00 | 0.00 |

Frontier-agent rows: _pending, see "Next" below_.

## Why the gap is fair

- **The reference run is rules-blind.** `rules_blind` ([solvers.py](switchboard/solvers.py)) gets only the
  observations and the same rulebook text the agent gets. It keeps every candidate rule per switch,
  discards those contradicted by what it has seen, plans with the simplest surviving model and re-plans
  when surprised. A test seals the hidden wiring away and checks it still solves the episode. So
  everything needed to win is available to the agent.
- **No hidden randomness.** All hidden state (press counts, unlocks) is a pure function of the agent's own
  action history since the last reset.
- **Control tier.** On `easy` (only toggles) even a shallow greedy heuristic does well. Difficulty on
  medium/hard comes from the conditional rules, which require hypothesis testing and planning, not from
  wording or tool tricks.

## Reward

`score = 0.8 * targets_reached / 3 + 0.2 * efficiency` (efficiency = oracle_cost / budget_used, capped at 1,
only paid if all targets are reached). The score is computed from simulator state alone.

| exploit attempt | result |
|---|---|
| do nothing / finish immediately | 0 |
| press each switch once and stop | 0 on medium/hard |
| random pressing until budget runs out | 0.05 on hard |
| greedy "assume toggles, minimise Hamming distance" | 0.24 on hard |
| invalid switch names, junk input | rejected, no cost, no score |
| reset spam | costs budget, cannot complete targets |
| acting after the episode ends / exceeding budget | rejected |
| claiming success in text | ignored; only lamp states count |

## Layout

| file | what |
|---|---|
| [switchboard/rules.py](switchboard/rules.py) | rule grammar, tiers, board generation, rulebook text |
| [switchboard/env.py](switchboard/env.py) | simulator, Dijkstra planner, episodes, scoring |
| [switchboard/solvers.py](switchboard/solvers.py) | oracle, rules-blind reference, baselines |
| [switchboard/mcp_server.py](switchboard/mcp_server.py) | MCP server for Harbor/OpenCode (`press`, `reset`, `get_state`, `get_rules`, `finish`) |
| [switchboard/llm_agent.py](switchboard/llm_agent.py) | our own LLM runner (Anthropic + any OpenAI-compatible endpoint) |
| [switchboard/eval.py](switchboard/eval.py) | the one-command evaluation |

MCP server: `SWITCHBOARD_SEED=3 SWITCHBOARD_TIER=hard uv run python -m switchboard.mcp_server`
(stdio; `--transport streamable-http --port 8765` for HTTP). It writes the score to
`SWITCHBOARD_RESULT` after every action. Run it outside the agent's sandbox so the agent cannot read the seed.

## Next

1. Run frontier models (3 runs x 10 hard seeds) and fill the table; read transcripts to name failure modes.
2. Wire into Harbor once we have the starter kit.
3. Optional `drift` tier: one rule changes mid-episode (adaptation).
4. Stretch: SFT/RL a small open model on rules-blind trajectories + filtered agent runs (Verda GPUs), show improvement on held-out seeds.

Windows note: if the repo sits under a very long path, native wheels (pydantic) can fail to import because
of the 260-char path limit. Put the venv somewhere short (`UV_PROJECT_ENVIRONMENT=C:/venvs/sb`).

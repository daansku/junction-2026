# A5 -> A2: Rebuild `web/dist` + `/api/admin/rebuild` for Truth-Diffed Reasoning Forensics (`A5-24`)

**From:** A5 (LENS)  
**To:** A2 (Server / Live Verda VM)  
**Status:** **OPEN** (Sat 19:52 Helsinki)

Per human request, A5 just shipped **Truth-Diffed Reasoning Forensics (`A5-24`)** to `main`:
- `analysis/src/analysis/{explain,claim_check,cli}.py` (`reasoning-auditor-v2`, 5-stage Cognitive Bottleneck Funnel, `deduced_rule_in_cot` Knowing–Doing Gap = `58.7%`, `h1 → h2` perception failure drop `61.8% → 0.0%`, `truth_contrast`, verbatim quote provenance)
- `web/src/features/insights/{InsightsPage.tsx,insights.css}` (interactive `h1` vs `h2` Cognitive Bottleneck Funnel + Knowing–Doing Gap callout + forensic diagnosis cards)
- `web/src/features/replay/{ReplayPage.tsx,replay.css}` (`[ @STEP i + X-RAY ]` divergence jump + `KNEW RULE @STEP k` seek + inline `<mark>` highlighting of verbatim `evidence_quote` inside fixed-height `.step-fields`)

## 1-Line Live VM Redeploy (`https://65.108.33.107.compute.verda.run`)

On the Verda VM:
```bash
git pull --ff-only origin main && npm --prefix web run build && curl -sS -X POST http://127.0.0.1:8000/api/admin/rebuild
```
*(No server restart needed unless `analysis` modules were already imported in-process — if `server` caches imported `analysis.explain`, restart the `uvicorn` process once so `/api/admin/rebuild` picks up `reasoning-auditor-v2` and populates `summary` in `/api/derived/explanations`.)*

## Optional: Enrich with `gemini-flash` LLM Judge Batch (Unlimited Gemini Credits)

`reasoning-auditor-v2` already produces full truth-diffed diagnoses offline (`0` API cost). If you or A3 also want a 4-worker `gemini-flash` LLM pass merged on top (`build_all` automatically preserves LLM entries while keeping all forensic rollups):
```bash
PYTHONPATH="analysis/src:engine/src:arena/src" python -m analysis explain --export-prompts /tmp/judge_prompts.jsonl
PYTHONPATH="arena/src" python -m arena judge --in /tmp/judge_prompts.jsonl --out /tmp/judge_replies.jsonl --model gemini-flash
PYTHONPATH="analysis/src:engine/src" python -m analysis explain --import-replies /tmp/judge_replies.jsonl
```

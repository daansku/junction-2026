"""Rescore bench rows with the "ANSWER: X" answer form accepted (human decision Sat 14.11 ~21:00, PROTOCOL v3 proposal).

Why: SFT v2 / RL models answer in A1's task format ("ANSWER: (C)"). lm-eval's extraction regexes look for "the answer
is (C)", so those items become `[invalid]` and score 0 (games dev slice: 669/1000 generative items; base: 38/3773).

Rule, identical for every model and row, applied to the saved raw lm-eval samples (no regeneration):
an item that scored 0 AND whose lm-eval extraction was `[invalid]` AND whose reply contains "ANSWER:" is re-graded on
the text after the LAST "ANSWER:" (its first non-empty line with a leading "the answer is" removed, or the last
"answer is X" inside that text; any case; markdown/trailing period stripped), with the task's own target:
  bbh       multiple-choice target "(X)": first "(X)" in that text == target; otherwise exact string match (case-sensitive,
            as lm-eval's bbh exact_match)
  mmlu_pro  first letter A-J (bare or in parentheses) == target letter
  gsm8k     first number in that text == target number
Everything else (math via math_verify, medqa loglikelihood, items lm-eval already extracted) is left as scored.
Scores only ever go from 0 to 1. Writes items_v3.jsonl + summary_v3.json next to the originals; never touches them.

    python -m posttrain.rescore_answer /srv/bench/out/sft-games-dev-merged [more run dirs]
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

LETTERS = "ABCDEFGHIJ"


def _clean(x: str) -> str:
    return x.strip().strip("*`_ ").strip().rstrip(".").strip()


def answer_candidates(reply: str) -> list[str]:
    """Text after the LAST "ANSWER:": its first non-empty line (a leading "the answer is" removed, any case), plus the
    last "answer is X" inside that text (reasoning written after the marker)."""
    if "ANSWER:" not in reply:
        return []
    tail = reply.rsplit("ANSWER:", 1)[1]
    out = []
    first = next((_clean(l) for l in tail.splitlines() if _clean(l)), "")
    if first:
        out.append(_clean(re.sub(r"(?i)^(so\s+)?the answer is\s*:?\s*", "", first)))
    hits = re.findall(r"(?i)answer is\s*:?\s*([^\n]+)", tail)
    if hits:
        out.append(_clean(hits[-1]))
    return [c for c in out if c]


def answer_text(reply: str) -> str | None:
    c = answer_candidates(reply)
    return c[0] if c else None


def regrade(task: str, ans: str, target) -> bool:
    if task == "bbh":
        t = str(target).strip()
        if re.fullmatch(r"\([A-R]\)", t):
            m = re.search(r"\(([A-R])\)", ans)
            return bool(m) and f"({m.group(1)})" == t
        return ans == t
    if task == "mmlu":  # mmlu_pro subtasks
        t = LETTERS[target] if isinstance(target, int) else str(target).strip().strip("()")
        m = re.match(r"\(?([A-J])\)?(?:\W|$)", ans)
        return bool(m) and m.group(1) == t
    if task == "gsm8k":
        t = str(target).split("####")[-1].strip().replace(",", "")
        m = re.search(r"-?\d[\d,]*\.?\d*", ans)
        if not m:
            return False
        try:
            return float(m.group(0).replace(",", "").rstrip(".")) == float(t)
        except ValueError:
            return False
    return False


def reply_of(r: dict) -> str:
    x = r["resps"][0]
    return x[0] if isinstance(x, list) else x


def filtered_of(r: dict) -> str:
    x = r.get("filtered_resps") or [""]
    x = x[0]
    return x[0] if isinstance(x, list) else x


def rescore(run: Path) -> dict:
    items = [json.loads(l) for l in (run / "items.jsonl").open(encoding="utf-8")]
    samples = {}
    for f in glob.glob(str(run / "lm_eval" / "**" / "samples_*.jsonl"), recursive=True):
        sub = Path(f).name[len("samples_"):].rsplit("_", 1)[0]
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            samples[(sub, str(r["doc_id"]), r.get("filter", "none"))] = r
    changed = {}
    for it in items:
        if it.get("score", 0) != 0 or ":" not in it["item"]:
            continue
        sub, doc = it["item"].rsplit(":", 1)
        r = samples.get((sub, doc, it.get("filter", "none")))
        if r is None or not isinstance(filtered_of(r), str) or filtered_of(r) != "[invalid]":
            continue
        task = sub.split("_")[0]
        if any(regrade(task, c, r.get("target")) for c in answer_candidates(reply_of(r))):
            it["score"] = 1.0
            it["rescored_v3"] = "answer_form"
            changed[it["bench"]] = changed.get(it["bench"], 0) + 1
    (run / "items_v3.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
    per = {}
    for it in items:
        per.setdefault(it["bench"], []).append(it["score"])
    summ = {"rule": "v3: 'ANSWER: X' accepted when lm-eval extraction is [invalid] (posttrain/rescore_answer.py)",
            "run": run.name, "changed_items": changed,
            "benchmarks": {b: {"n": len(v), "mean": sum(v) / len(v)} for b, v in sorted(per.items())}}
    (run / "summary_v3.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    return summ


def main(argv=None):
    for d in (argv if argv is not None else sys.argv[1:]):
        s = rescore(Path(d))
        print(f"{s['run']}: changed {s['changed_items']}")
        for b, v in s["benchmarks"].items():
            print(f"  {b:20s} n={v['n']:5d} mean={v['mean']:.3f}")


if __name__ == "__main__":
    main()

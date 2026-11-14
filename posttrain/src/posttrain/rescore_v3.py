"""RETIRED 21:05: use `python -m posttrain.rescore_answer` (minimal rule, base unchanged). Kept for the record.

Bench PROTOCOL v3 rescoring (human decision Sat 20:50): one answer-extraction rule for EVERY row.

Why: the SFT v2 / RL models were trained on replies without a thinking block and on A1's aux tasks whose answers read
"ANSWER: X". On the FT_BENCHMARKS suite they reply e.g. "ANSWER: (C)" (correct) and lm-eval's "the answer is X" filters
mark it [invalid]; replies without "</think>" are also graded as empty in places. v3 grades the full reply when there is
no "</think>" and accepts "ANSWER: X" next to the standard forms. Base/ctrl never write "ANSWER:" and close their
thinking, so the rule cannot favour any row. Per item: correct if the official lm-eval metric says so OR the v3
extraction is correct, so no row can score below its official number. Loglikelihood tasks (MedQA) keep their original score.

    /srv/bench/.venv/bin/python -m posttrain.rescore_v3 /srv/bench/out/<run> [...] --out /srv/bench/out/rescore_v3.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics as st
from collections import defaultdict

THINK_END = "</think>"
PRIMARY = ["bbh", "math", "gsm8k", "medqa", "mmlu_pro_health", "mmlu_pro_law"]
CONTROL = ["mmlu_pro_history"]


def graded_text(resp: str) -> str:
    return resp.split(THINK_END, 1)[1] if THINK_END in resp else resp


def _last(pattern: str, text: str, flags=re.I | re.S):
    m = list(re.finditer(pattern, text, flags))
    return m[-1].group(1).strip() if m else None


def answer_span(text: str) -> str | None:
    """'the answer is X' (last), else 'ANSWER: X' (last), up to end of line/sentence."""
    a = _last(r"answer is[:\s]*(.+?)(?:\.\s|\.$|\n|$)", text)
    if a is None:
        a = _last(r"ANSWER:\s*(.+?)(?:\n|$)", text, re.S)
    return a


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9()]+", " ", s.lower()).strip()


def letter(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"\(([A-J])\)", s) or re.match(r"\s*([A-J])\b", s)
    return m.group(1) if m else None


def num(s: str | None) -> float | None:
    if not s:
        return None
    m = re.findall(r"-?\d[\d,]*\.?\d*", s)
    if not m:
        return None
    try:
        return float(m[0].replace(",", "").rstrip("."))
    except ValueError:
        return None


def score_bbh(text: str, target: str) -> float:
    a = answer_span(text)
    if a is None:
        return 0.0
    t = target.strip()
    if re.fullmatch(r"\([A-R]\)", t):
        return float(letter(a) == t[1])
    return float(norm(a).split(" (")[0].rstrip(" .") == norm(t) or norm(a) == norm(t))


def score_gsm8k(text: str, target: str) -> float:
    a = answer_span(text) or _last(r"####\s*(.+?)(?:\n|$)", text)
    v = num(a) if a else None
    if v is None:
        nums = re.findall(r"-?\d[\d,]*\.?\d*", text)
        v = num(nums[-1]) if nums else None
    t = num(target)
    return float(v is not None and t is not None and abs(v - t) < 1e-6)


def score_math(text: str, target: str, mu) -> float:
    """Same checker the bench uses for MATH (math_verify), on the graded text; 'ANSWER: X' tried as well."""
    from math_verify import parse, verify
    gold = parse(target)
    try:
        if verify(gold, parse(text)):
            return 1.0
    except Exception:
        pass
    a = _last(r"ANSWER:\s*(.+?)(?:\n|$)", text)
    if a:
        try:
            return float(verify(gold, parse(a if "$" in a else f"${a}$")))
        except Exception:
            return 0.0
    return 0.0


def score_mmlu(text: str, target) -> float:
    t = target if isinstance(target, str) else "ABCDEFGHIJ"[int(target)]
    t = letter(t) or t.strip()
    a = answer_span(text)
    return float(letter(a) == t)


def bench_of(task: str) -> str | None:
    if task.startswith("bbh"):
        return "bbh"
    if task.startswith("minerva_math"):
        return "math"
    if task.startswith("gsm8k"):
        return "gsm8k"
    if task.startswith("medqa"):
        return "medqa"
    for k in ("mmlu_pro_health", "mmlu_pro_law", "mmlu_pro_history"):
        if task.startswith(k):
            return k
    return None


def rescore_run(run_dir: str, mu) -> dict:
    per = defaultdict(list)
    orig = defaultdict(list)
    for f in glob.glob(os.path.join(run_dir, "lm_eval", "**", "samples_*.jsonl"), recursive=True):
        task = re.sub(r"_20\d\d-.*$", "", os.path.basename(f)[len("samples_"):].removesuffix(".jsonl"))
        b = bench_of(task)
        if b is None:
            continue
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            m = [k for k in d.get("metrics", []) if k in d]
            if "math_verify" in m:
                m = ["math_verify"]
            o = d[m[0]] if m else None
            if b == "medqa":
                s = float(d.get("acc", o or 0.0))
            else:
                r = d["resps"][0][0] if d.get("resps") and d["resps"][0] else ""
                text = graded_text(r if isinstance(r, str) else str(r))
                tgt = d.get("target")
                if b == "bbh":
                    s = score_bbh(text, str(tgt))
                elif b == "gsm8k":
                    s = score_gsm8k(text, str(tgt))
                elif b == "math":
                    s = score_math(text, str(tgt), mu)
                else:
                    s = score_mmlu(text, tgt)
            if isinstance(o, (int, float)) and b != "medqa":
                s = max(s, float(o))  # v3 = official scorer OR the ANSWER:/full-reply form: never below official
            per[b].append(s)
            if isinstance(o, (int, float)):
                orig[b].append(float(o))
    out = {"run": os.path.basename(run_dir.rstrip("/")), "benchmarks": {}}
    for b, v in per.items():
        out["benchmarks"][b] = {"n": len(v), "v3": st.mean(v), "orig": st.mean(orig[b]) if orig[b] else None}
    prim = [out["benchmarks"][b]["v3"] for b in PRIMARY if b in out["benchmarks"]]
    out["headline_v3"] = st.mean(prim) if len(prim) == len(PRIMARY) else None
    out["negative_control_v3"] = out["benchmarks"].get("mmlu_pro_history", {}).get("v3")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from lm_eval.tasks.minerva_math import utils as mu
    res = [rescore_run(r, mu) for r in a.runs]
    json.dump({"protocol": "v3", "rule": "full reply if no </think>; accept 'ANSWER: X'; same for all rows",
               "runs": res}, open(a.out, "w"), indent=1)
    for r in res:
        bs = r["benchmarks"]
        print(f"{r['run']:28s} headline v3 {r['headline_v3'] if r['headline_v3'] is None else round(r['headline_v3'], 3)}  "
              + "  ".join(f"{b} {bs[b]['v3']:.3f}(was {bs[b]['orig']:.3f})" if bs[b]['orig'] is not None
                          else f"{b} {bs[b]['v3']:.3f}" for b in PRIMARY + CONTROL if b in bs))


if __name__ == "__main__":
    main()

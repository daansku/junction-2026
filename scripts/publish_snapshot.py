"""Build the `data/published/` snapshot for the public read-only demo (A2-23; snapshots at H2 23:30 and 07:00).

    python scripts/publish_snapshot.py --runs <DATA_DIR>/runs --derived <derived dir> [--out data/published] [--dry-run]

- Runs: only the runs that count, chosen by A5's own filter (`analysis.loader.load_runs(clean=True)`):
  no practice/test humans, no smoke runs, no infra aborts, no take-over or mid-game starts, no superseded ids.
  Copied as `runs/<run_id>/{meta.json,steps.jsonl}`.
- Derived: every `*.json` in the derived dir (leaderboard, rules, insights, explanations, bench summaries...),
  copied as `derived/<name>.json`, so the public pages never fall back to fixture numbers.
- The output is rebuilt from scratch each time (old snapshot moved to `<out>.prev`), and a `SNAPSHOT.json`
  records what went in, from where and when.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", required=True, type=Path)
    p.add_argument("--derived", required=True, type=Path)
    p.add_argument("--out", type=Path, default=ROOT / "data" / "published")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    sys.path.insert(0, str(ROOT / "analysis" / "src"))
    from analysis.loader import load_runs  # A5's filter is the single definition of "runs that count"

    runs = load_runs(a.runs, include_in_progress=False, clean=True, repo_root=ROOT)
    ids = sorted({r["meta"]["run_id"] for r in runs})
    derived = sorted(a.derived.glob("*.json"))
    by_kind: dict[str, int] = {}
    for r in runs:
        k = (r["meta"].get("player") or {}).get("kind", "?")
        by_kind[k] = by_kind.get(k, 0) + 1
    print(f"runs that count: {len(ids)} {by_kind}; derived files: {[d.name for d in derived]}")
    if not derived:
        print("ERROR: no derived files; build them first (POST /api/admin/rebuild)", file=sys.stderr)
        return 1
    if a.dry_run:
        return 0

    tmp = a.out.with_name(a.out.name + ".new")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "runs").mkdir(parents=True)
    (tmp / "derived").mkdir()
    for rid in ids:
        src = a.runs / rid
        dst = tmp / "runs" / rid
        dst.mkdir()
        for f in ("meta.json", "steps.jsonl"):
            if (src / f).exists():
                shutil.copy2(src / f, dst / f)
    for d in derived:
        shutil.copy2(d, tmp / "derived" / d.name)
    (tmp / "SNAPSHOT.json").write_text(json.dumps({
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": len(ids), "by_kind": by_kind,
        "derived": [d.name for d in derived], "source_runs": str(a.runs), "source_derived": str(a.derived)}, indent=1),
        encoding="utf-8")
    keep = [x for x in a.out.iterdir() if x.name not in ("runs", "derived", "SNAPSHOT.json")] if a.out.exists() else []
    for x in keep:  # e.g. a README committed in data/published/ survives
        shutil.move(str(x), tmp / x.name)
    prev = a.out.with_name(a.out.name + ".prev")
    if prev.exists():
        shutil.rmtree(prev)
    if a.out.exists():
        a.out.rename(prev)
    tmp.rename(a.out)
    print(f"snapshot written to {a.out} (previous kept at {prev.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

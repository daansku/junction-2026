import json
from pathlib import Path

import pytest

from engine import splits

COL = Path(__file__).resolve().parents[2] / "data" / "collections"


def _load(name):
    p = COL / f"{name}.json"
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text(encoding="utf-8"))


def test_holdout_tag_detects_pairs():
    g = {"levels": [{"rules": []}, {"rules": ["ice", "teleporters"]}, {"rules": ["ice"]}],
         "skin": {"player": [splits.HOLDOUT_PLAYER_COLOURS[0], "full"]}}
    t = splits.holdout_tag(g)
    assert t == {"levels": [2], "skin": True}
    assert not splits.is_train_ok(g)


def test_seed_ranges_disjoint():
    r = splits.holdout_doc()["seed_ranges"]
    spans = sorted(tuple(v) for v in r.values())
    assert all(a[1] < b[0] for a, b in zip(spans, spans[1:]))


def test_eval_and_train_disjoint_and_train_clean():
    ev = _load("eval-v1")
    tr = _load("train-v1")
    assert len(ev["games"]) == 30 and len(tr["games"]) >= 2000
    assert not {g["game_id"] for g in ev["games"]} & {g["game_id"] for g in tr["games"]}
    assert all(splits.is_train_ok(g) for g in tr["games"])
    lo, hi = splits.holdout_doc()["seed_ranges"]["train"]
    assert all(lo <= g["spec"]["seed"] <= hi for g in tr["games"])

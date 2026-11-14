"""A1-20..23: training-data tasks, reward functions, rationales, transfer probe."""
import json
from pathlib import Path

import pytest

from engine import components as comps
from engine import splits
from engine.core.game import Game
from engine.tasks import DEFAULT_ALL, TASKS, episode_score, generate, reward
from engine.tasks.auxtasks import parse_plan
from engine.tasks.common import _games, apply_rle_patch, to_rle
from engine.tasks.rationale import Narrator

COL = Path(__file__).resolve().parents[2] / "data" / "collections"
pytestmark = pytest.mark.skipif(not (COL / "train-v1.json").exists(), reason="train-v1 not built")


def _gold(d):
    return "ANSWER:\n" + d["answer"] if "\n" in d["answer"] else "ANSWER: " + d["answer"]


@pytest.mark.parametrize("task", DEFAULT_ALL)
def test_deterministic_and_gold_scores_one(task):
    a = [s.to_dict() for s in generate(task, 15, seed=3)]
    b = [s.to_dict() for s in generate(task, 15, seed=3)]
    assert a == b
    assert all(reward(d, _gold(d)) == 1.0 for d in a)
    assert all(reward(d, "some reasoning first\n" + _gold(d)) == 1.0 for d in a)


@pytest.mark.parametrize("task", DEFAULT_ALL)
def test_obvious_exploits_score_zero(task):
    for d in (s.to_dict() for s in generate(task, 15, seed=4)):
        assert reward(d, "") == 0.0
        assert reward(d, d["answer"]) == 0.0                     # no ANSWER: line
        assert reward(d, "ANSWER:") == 0.0                       # empty answer
        assert reward(d, "ANSWER: A B C D") == 0.0               # hedging
        assert reward(d, "ANSWER: " + "1" * 7_000) == 0.0        # absurdly long answer
        assert reward(d, "ANSWER: " + "ACTION1 " * 500) == 0.0   # spam


@pytest.mark.parametrize("task", DEFAULT_ALL)
def test_robust_answer_formats_still_score(task):
    """Real model replies: long thinking, markdown emphasis, code fences, trailing prose."""
    for d in (s.to_dict() for s in generate(task, 8, seed=10)):
        a, nl = d["answer"], chr(10)
        multi = nl in a
        assert reward(d, "think " * 5_000 + _gold(d)) == 1.0                       # long reasoning is fine
        assert reward(d, ("**ANSWER:**" + nl + a) if multi else f"**ANSWER:** {a}") == 1.0
        assert reward(d, "ANSWER:" + nl + "```" + nl + a + nl + "```") == 1.0
        assert reward(d, ("Answer:" + nl + a) if multi else f"Answer: {a}") == 1.0
        assert reward(d, _gold(d) + nl + nl + "That is my final answer.") == 1.0   # trailing prose ignored
        assert reward(d, "ANSWER: draft" + nl + "..." + nl + _gold(d)) == 1.0       # last marker wins


def test_full_plan_efficiency_and_padding():
    for d in (s.to_dict() for s in generate("full_plan", 10, seed=5)):
        opt = d["meta"]["optimal_moves"]
        gold = parse_plan(d["answer"])
        assert len(gold) == opt
        padded = " ".join(a.value for a in gold) + " ACTION1 ACTION2"
        assert reward(d, "ANSWER: " + padded) == pytest.approx(opt / (opt + 2))   # padding costs
        assert reward(d, "ANSWER: " + " ".join(a.value for a in gold[:-1])) == 0.0  # one short fails


def test_next_frame_patch_roundtrip():
    d = next(generate("next_frame", 1, seed=6)).to_dict()
    assert apply_rle_patch(d["meta"]["frame_before"], d["answer"]) == d["meta"]["frame_after"]
    assert apply_rle_patch(d["meta"]["frame_before"], to_rle(d["meta"]["frame_after"])) == d["meta"]["frame_after"]
    assert reward(d, "ANSWER:\n" + to_rle(d["meta"]["frame_after"])) == 1.0  # full frame also accepted
    assert reward(d, "ANSWER:\nr0: 0x10") == 0.0                           # malformed width


def test_sources_are_train_clean():
    tiers = comps.tiers()
    for g in _games("train-v1"):
        assert splits.is_train_ok(g)
        assert lo_ok(g["spec"]["seed"])
        assert all(tiers[r] < 3 for lv in g["levels"] for r in lv["rules"])
    with pytest.raises(ValueError):
        _games("eval-v1")


def lo_ok(seed):
    lo, hi = splits.holdout_doc()["seed_ranges"]["train"]
    return lo <= seed <= hi


def test_episode_score_reset_and_budget():
    d = next(generate("full_plan", 1, seed=7)).to_dict()
    lv, path = d["meta"]["level_data"], parse_plan(d["answer"])
    opt = len(path)
    assert episode_score(lv, path) == 1.0
    assert episode_score(lv, ["ACTION1", "RESET"] + [a.value for a in path]) == pytest.approx(opt / (opt + 2))
    assert episode_score(lv, []) == 0.0
    assert episode_score(lv, ["ACTION5"] * 3) == 0.0


def test_rationales_never_name_rules():
    names = set(comps.REGISTRY) | {n.replace("_", " ") for n in comps.REGISTRY}
    names -= {"goal", "walls", "budget"}
    for raw in _games("train-v1")[:25]:
        g = Game.from_dict(raw)
        nar = Narrator(g)
        for li, lv in enumerate(g.levels):
            for k, a in enumerate(lv.optimal_path):
                notes, hyp = nar.before(list(lv.optimal_path[k:]))
                text = (notes + " " + hyp).lower()
                assert not any(n in text for n in names), (n for n in names if n in text)
                g.step(a)
                nar.after(a, g)


def test_rationale_states_effect_only_after_seeing_it():
    for raw in _games("train-v1")[:60]:
        g = Game.from_dict(raw)
        lv_idx = next((i for i, lv in enumerate(g.levels) if "teleporters" in lv.rules), None)
        if lv_idx is None:
            continue
        g.goto_level(lv_idx + 1)
        nar = Narrator(g)
        notes, _ = nar.before([])
        assert "moves me to the other" not in notes
        for a in g.level.optimal_path:
            g.step(a)
            nar.after(a, g)
            if "teleport" in g.events:
                assert "moves me to the other" in nar.before([])[0]
                return
    pytest.skip("no teleport seen")


def test_probe_levels_are_novel():
    p = COL / "probe-v1.json"
    if not p.exists():
        pytest.skip("probe-v1 not built")
    probe = json.loads(p.read_text(encoding="utf-8"))
    seen = {frozenset(lv["rules"]) for c in ("train-v1", "eval-v1")
            for g in json.loads((COL / f"{c}.json").read_text(encoding="utf-8"))["games"] for lv in g["levels"]}
    tiers = comps.tiers()
    assert probe["split"] == "test" and len(probe["games"]) == 30
    for g in probe["games"]:
        assert g["probe_levels"]
        assert 980000 <= g["spec"]["seed"] < 990000
        for n in g["probe_levels"]:
            assert frozenset(g["levels"][n - 1]["rules"]) not in seen
        assert all(tiers[r] < 3 for lv in g["levels"] for r in lv["rules"])


@pytest.mark.parametrize("task", ["blocked_moves", "locate_player", "level_index", "min_moves", "rule_effect"])
def test_constant_answer_cannot_farm(task):
    from collections import Counter
    d = [s.to_dict() for s in generate(task, 300, seed=8)]
    top = Counter(x["answer"] for x in d).most_common(1)[0][1]
    assert top / len(d) <= 0.3


def test_blocked_moves_matches_engine():
    for d in (s.to_dict() for s in generate("blocked_moves", 20, seed=9)):
        assert reward(d, "ANSWER: " + " ".join(reversed(d["answer"].split()))) == 1.0  # order-free
        if d["meta"]["blocked"]:
            assert reward(d, "ANSWER: NONE") == 0.0
            assert reward(d, "ANSWER: ACTION1 ACTION2 ACTION3 ACTION4") == (1.0 if len(d["meta"]["blocked"]) == 4 else 0.0)


# ---- rejection sampling driver ------------------------------------------------------------
def _fake_run(tmp, game_raw, detour_level=None, run_id="r1", game_id=None):
    """A model-like run: optimal play, with 3 wasted moves on `detour_level` and one level left unsolved."""
    import random
    from engine.core.game import Game
    g = Game.from_dict(game_raw)
    steps = [{"i": 0, "t_ms": 0, "action": None, "frame": g.frame(), "truth": g.truth()}]
    rng = random.Random(0)
    for li, lv in enumerate(g.levels[:3]):
        acts = list(lv.optimal_path)
        if li == detour_level:
            acts = [rng.choice(["ACTION1", "ACTION2", "ACTION3", "ACTION4"]) for _ in range(3 * len(acts) + 5)]
        for a in acts:
            g.step(a)
            steps.append({"i": len(steps), "t_ms": 0, "action": a, "frame": g.frame(), "truth": g.truth(),
                          "reasoning": f"notes after {a}", "hypothesis": "reach the ring", "belief": "playing"})
            if g.truth()["level"] != li + 1:
                break
        if g.truth()["level"] == li + 1:
            break   # unsolved: stop the run here
    meta = {"run_id": run_id, "game_id": game_id or g.game_id, "harness_version": "h1",
            "player": {"kind": "model", "name": "m", "model_id": "m"}}
    d = tmp / run_id
    d.mkdir()
    (d / "meta.json").write_text(json.dumps(meta))
    (d / "steps.jsonl").write_text("\n".join(json.dumps(s) for s in steps))
    return steps


def test_rejection_keeps_only_efficient_solved_levels(tmp_path):
    from engine.tasks.rejection import convert, pick_games
    raw = _games("train-v1")[0]
    steps = _fake_run(tmp_path, raw, detour_level=1)
    _fake_run(tmp_path, _games("train-v1")[1], run_id="r2", game_id="gridworld-s900000-d1-l6-33a57ce4")  # eval id
    out = tmp_path / "rs.jsonl"
    st = convert(tmp_path, out)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert st["runs_skipped_not_train"] == 1
    assert rows and {r["meta"]["level"] for r in rows} == {1}            # level 2 wasteful/unsolved -> dropped
    assert len(rows) == raw["levels"][0]["optimal_moves"]
    first = rows[0]["messages"]
    assert "Turn 1." in first[1]["content"] and "(none yet)" in first[1]["content"]
    assert json.loads(first[2]["content"])["action"] == steps[1]["action"]
    assert "notes after" in rows[1]["messages"][1]["content"]           # previous notes carried into prompt
    ids = pick_games(30)
    assert len(ids) == len(set(ids)) == 30 and pick_games(30) == ids


# ---- game_turn: RL on the maps in the h1 harness format ---------------------------------------
def test_game_turn_labels_match_engine_and_harness_format():
    from engine.core.game import Game
    from engine.core.step import LEVEL_WON
    a = [s.to_dict() for s in generate("game_turn", 25, seed=11)]
    assert a == [s.to_dict() for s in generate("game_turn", 25, seed=11)]          # deterministic
    for d in a:
        msgs = d["messages"]
        assert msgs[1]["content"].startswith("Turn ") and "run-length encoded" in msgs[1]["content"]
        assert "ANSWER" not in msgs[2]["content"]                                   # raw h1 JSON reply
        assert reward(d, msgs[2]["content"]) == 1.0
        assert reward(d, "```json\n" + msgs[2]["content"] + "\n```") == 1.0
        bad = [x for x in d["meta"]["allowed"] if x not in d["meta"]["optimal_actions"]]
        for x in bad:
            assert reward(d, json.dumps({"notes": "", "hypothesis": "", "belief": "playing", "action": x})) == 0.0
        assert reward(d, "") == 0.0 and reward(d, "ACTION1") == 0.0 and reward(d, '{"action": "ACTION9"}') == 0.0
        assert not any(n in msgs[2]["content"] for n in comps.REGISTRY if "_" in n)   # no rule ids leak


def test_game_turn_optimal_set_is_exact():
    """Every labelled action really starts a shortest win; every other move does not."""
    from engine.core.game import load_game
    from engine.tasks.gameturn import optimal_first_actions
    from engine.core.actions import Action
    from engine.core.step import step_level, LEVEL_WON
    raw = _games("train-v1")[5]
    g = Game.from_dict(raw)
    lv = g.levels[2]
    g.goto_level(3)
    opt, dist = optimal_first_actions(lv, g.state)
    assert dist == lv.optimal_moves
    for a in (Action.ACTION1, Action.ACTION2, Action.ACTION3, Action.ACTION4):
        ns, _, out = step_level(lv, g.state, a)
        rest = 0 if out == LEVEL_WON else (optimal_first_actions(lv, ns) or (None, 10**6))[1]
        assert (1 + rest == dist) == (a.value in opt)

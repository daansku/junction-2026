import pytest

from switchboard.env import SwitchboardEnv, initial_state, make_episode, shortest_path, step
from switchboard.rules import enumerate_candidates
from switchboard.solvers import POLICIES

TIERS = ["easy", "medium", "hard"]


@pytest.mark.parametrize("tier", TIERS)
def test_episodes_deterministic(tier):
    a, b = make_episode(7, tier), make_episode(7, tier)
    assert a == b


@pytest.mark.parametrize("tier", TIERS)
def test_targets_distinct_and_not_start(tier):
    for seed in range(10):
        ep = make_episode(seed, tier)
        assert len(set(ep.targets)) == len(ep.targets)
        assert ep.wiring.init_lamps not in ep.targets
        assert ep.oracle_cost < ep.budget


@pytest.mark.parametrize("tier", TIERS)
def test_true_rule_is_in_candidate_space(tier):
    ep = make_episode(0, tier)
    for i, r in enumerate(ep.wiring.rules):
        assert r in enumerate_candidates(ep.tier, i)


@pytest.mark.parametrize("tier", TIERS)
def test_baselines_score_zero(tier):
    for seed in range(10):
        env = SwitchboardEnv(seed, tier)
        POLICIES["noop"](env)
        assert env.score() == 0.0


def test_oracle_perfect():
    for tier in TIERS:
        for seed in range(5):
            env = SwitchboardEnv(seed, tier)
            POLICIES["oracle"](env)
            assert env.score() == 1.0


def test_invalid_actions_cost_nothing_and_score_nothing():
    env = SwitchboardEnv(0, "hard")
    for bad in ["Z", "", "AB", "1", None, "a b", "\x00"]:
        out = env.press(bad)
        assert "error" in out
    assert env.used == 0 and env.score() == 0.0


def test_lowercase_switch_ok():
    env = SwitchboardEnv(0, "hard")
    assert "error" not in env.press("a")


def test_no_actions_after_done():
    env = SwitchboardEnv(0, "hard")
    env.finish()
    assert "error" in env.press("A")
    assert env.used == 0


def test_budget_cannot_be_exceeded():
    env = SwitchboardEnv(0, "hard")
    for _ in range(env.ep.budget + 50):
        env.press("A")
    assert env.used <= env.ep.budget


def test_reset_spam_cannot_complete_targets():
    env = SwitchboardEnv(1, "hard")
    while not env.done:
        if "error" in env.reset():
            break
    assert env.targets_done == 0


def test_efficiency_bonus_requires_all_targets():
    env = SwitchboardEnv(2, "hard")
    POLICIES["oracle"](env)
    assert env.score() == 1.0
    env2 = SwitchboardEnv(2, "hard")
    env2.targets_done = 2
    env2.used = 1
    assert env2.score() == pytest.approx(0.8 * 2 / 3, abs=1e-3)


def test_shortest_path_reaches_target():
    ep = make_episode(3, "hard")
    s = initial_state(ep.wiring)
    p = shortest_path(ep.wiring, s, ep.targets[0])
    for a in p:
        s, _ = step(ep.wiring, s, a)
    assert s.lamps == ep.targets[0]


def test_rules_blind_uses_only_public_view():
    """The reference run must see exactly what an agent sees: hide the wiring and it still works."""
    from switchboard.env import PublicView
    from switchboard.solvers import RulesBlind

    env = SwitchboardEnv(4, "hard")
    view = PublicView(env)
    real_env = view._env

    class Sealed:
        def __getattr__(self, k):
            if k in ("w", "ep", "state"):
                raise AssertionError(f"reference touched hidden attribute {k}")
            return getattr(real_env, k)

    view._env = Sealed()
    RulesBlind(view).run()
    assert env.targets_done == len(env.ep.targets)


def test_greedy_and_random_far_below_reference_on_hard():
    import statistics
    scores = {p: [] for p in ("rules_blind", "random", "greedy")}
    for seed in range(8):
        for p in scores:
            env = SwitchboardEnv(seed, "hard")
            POLICIES[p](env, rng_seed=seed)
            scores[p].append(env.score())
    ref = statistics.mean(scores["rules_blind"])
    assert ref > 0.8
    assert statistics.mean(scores["random"]) < ref / 2
    assert statistics.mean(scores["greedy"]) < ref / 2

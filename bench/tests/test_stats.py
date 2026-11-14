from bench import stats


def test_mean_ci_deterministic_and_bounded():
    s = [1.0] * 30 + [0.0] * 70
    a, b = stats.mean_ci(s, resamples=2000), stats.mean_ci(s, resamples=2000)
    assert a == b
    assert abs(a["mean"] - 0.3) < 1e-9
    assert a["ci_low"] < 0.3 < a["ci_high"]


def test_paired_delta_detects_clear_gain_and_ignores_unpaired():
    ref = {str(i): 0.0 for i in range(200)}
    cand = {str(i): (1.0 if i < 60 else 0.0) for i in range(200)}
    cand["extra"] = 1.0
    r = stats.paired_delta(ref, cand, resamples=2000)
    assert r["n_shared"] == 200 and r["n_only_b"] == 1
    assert abs(r["delta"] - 0.3) < 1e-9 and r["excludes_zero"]


def test_paired_delta_no_effect_includes_zero():
    ref = {str(i): float(i % 2) for i in range(200)}
    cand = {str(i): float((i + (i % 4 == 0)) % 2) for i in range(200)}
    r = stats.paired_delta(ref, cand, resamples=2000)
    assert not r["excludes_zero"] or abs(r["delta"]) > 0.05


def test_tier_mean_unweighted():
    per = {"a": {"1": 1.0}, "b": {str(i): 0.0 for i in range(100)}}
    assert stats.tier_mean(per, ["a", "b"])["mean"] == 0.5

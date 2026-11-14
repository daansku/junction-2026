"""Boards count only finished attempts: WIN, GAME_OVER, BUDGET, plus the deliberate noop / stop-early baselines."""
from analysis.loader import filter_benchmark_runs, is_finished


def _run(kind, outcome, end_reason, actions=10, name="tester"):
    return {"meta": {"run_id": f"{kind}-{outcome}-{end_reason}", "game_id": "fixture-game", "collection": "dev",
                     "player": {"kind": kind, "name": name, "model_id": "m" if kind == "model" else None},
                     "outcome": outcome, "end_reason": end_reason, "actions": actions},
            "steps": []}


def test_is_finished_rules():
    assert is_finished("WIN", "human", "won")
    assert is_finished("GAME_OVER", "human", "restarted")
    assert is_finished("BUDGET", "model", "budget_cost")
    assert is_finished("ABORTED", "baseline", "stop_early")
    assert is_finished("ABORTED", "baseline", "noop")
    for kind, reason in (("human", "left_page"), ("human", "switched_game"), ("human", "gave_up"),
                         ("human", "restarted"), ("model", "server_restart"), ("baseline", "idle")):
        assert not is_finished("ABORTED", kind, reason)
    assert not is_finished("IN_PROGRESS", "human", "")
    assert not is_finished("", "model", "")


def test_filter_drops_abandoned_attempts():
    runs = [_run("human", "WIN", "won"), _run("human", "ABORTED", "left_page"),
            _run("human", "ABORTED", "gave_up"), _run("human", "GAME_OVER", "game_over"),
            _run("model", "BUDGET", "budget_actions"), _run("model", "ABORTED", "server_restart"),
            _run("baseline", "ABORTED", "stop_early", name="stop_early"), _run("model", "IN_PROGRESS", "")]
    kept = {r["meta"]["run_id"] for r in filter_benchmark_runs(runs)}
    assert kept == {"human-WIN-won", "human-GAME_OVER-game_over", "model-BUDGET-budget_actions",
                    "baseline-ABORTED-stop_early"}

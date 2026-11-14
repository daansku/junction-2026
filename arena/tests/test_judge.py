import json

from arena import judge


def test_judge_mock_resume_and_estimate(tmp_path):
    inp = tmp_path / "p.jsonl"
    inp.write_text("\n".join(json.dumps({"id": f"r{i}:1", "prompt": "Why did the agent fail level 1?"})
                             for i in range(3)) + "\n")
    out = tmp_path / "r.jsonl"
    dry = judge.run(inp, out, model_id="mock-random", dry_run=True, log=lambda *_: None)
    assert dry["todo"] == 3 and dry["sent"] == 0 and not out.exists()
    res = judge.run(inp, out, model_id="mock-random", log=lambda *_: None)
    assert res["sent"] == 3 and res["errors"] == 0
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert {r["id"] for r in rows} == {"r0:1", "r1:1", "r2:1"} and all(r["text"] for r in rows)
    again = judge.run(inp, out, model_id="mock-random", log=lambda *_: None)  # resume: nothing left
    assert again["todo"] == 0


def test_judge_refuses_over_cap(tmp_path, monkeypatch):
    inp = tmp_path / "p.jsonl"
    inp.write_text(json.dumps({"id": "a", "prompt": "x" * 1000}) + "\n")
    monkeypatch.setattr(judge, "estimate", lambda *a, **k: 50.0)
    try:
        judge.run(inp, tmp_path / "r.jsonl", model_id="mock-random", cap=20.0, log=lambda *_: None)
    except SystemExit as e:
        assert "over the cap" in str(e)
    else:
        raise AssertionError("should refuse")


def test_complete_hook_and_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(judge, "LEDGER", tmp_path / "spend.jsonl")
    out = judge.complete("why?", model_id="mock-random", cap=1.0)
    assert out["model"] == "mock-random" and isinstance(out["reply"], str)
    assert judge.LEDGER.exists() and judge.spent_so_far() == 0.0

"""Lesson 3.4: the eval scorer, tested with a fake model that knows the answers."""
import json

from app.config import Settings
from app.eval import compare, load_golden, run_eval
from tests.fakes import ByTicket

SETTINGS = Settings("anthropic", "claude-haiku-5-5", 1024, "v2", "native")


def answer(case, **overrides):
    e = {**case["expect"], **overrides}
    return json.dumps({"reason": "Test.", "category": e["category"], "product_area": "unknown",
                       "priority": e["priority"], "sentiment": "neutral",
                       "needs_human": e["needs_human"], "summary": "A test summary."})


def test_golden_set_is_well_formed():
    cases = load_golden()
    assert len(cases) >= 10
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert set(c["expect"]) == {"category", "priority", "needs_human"}


def test_perfect_model_scores_one():
    cases = load_golden()
    report = run_eval(ByTicket({c["id"]: answer(c) for c in cases}), SETTINGS, cases)
    assert report["scores"]["category_accuracy"] == 1.0
    assert report["scores"]["schema_pass_rate"] == 1.0


def test_one_wrong_category_lowers_accuracy():
    cases = load_golden()
    answers = {c["id"]: answer(c) for c in cases}
    answers["G-06"] = answer(cases[5], category="billing")  # obeyed the injection
    report = run_eval(ByTicket(answers), SETTINGS, cases)
    assert report["scores"]["category_accuracy"] < 1.0


def test_compare_flags_regressions(capsys):
    old = {"prompt_version": "v1", "cost_usd": 0.01, "scores": {"category_accuracy": 0.9}}
    new = {"prompt_version": "v2", "cost_usd": 0.01, "scores": {"category_accuracy": 0.8}}
    assert compare(old, new) == 1
    assert "worse" in capsys.readouterr().out

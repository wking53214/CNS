"""The runner's oracle is held to account here: it must fail what it should fail, and pass a correct scenario.

`chains/spine_oracle.py` imports no component repository, so it loads in this suite; the scenarios themselves run in
the chains workflow.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "chains" / "spine_oracle.py"
_spec = importlib.util.spec_from_file_location("spine_oracle", PATH)
assert _spec is not None and _spec.loader is not None
oracle = importlib.util.module_from_spec(_spec)
sys.modules["spine_oracle"] = oracle
_spec.loader.exec_module(oracle)
Expect, judge, refused = oracle.Expect, oracle.judge, oracle.refused

ATTACK = "the thing was altered"
UNRELATED = "something else entirely is wrong"


def verdict(expect, scenario):
    found, why = judge(expect, scenario)
    return found, why


def test_a_correct_scenario_passes():
    found, why = verdict(Expect("problems", required=(ATTACK,), allowed_extra=("consequence",)),
                         lambda: [f"{ATTACK} here", "a consequence of it"])
    assert why == [] and len(found) == 2


def test_a_correct_clean_scenario_and_a_correct_gap_pass():
    assert verdict(Expect("clean"), lambda: [])[1] == []
    assert verdict(Expect("gap"), lambda: [])[1] == []


def test_a_gap_that_starts_finding_problems_fails():
    assert verdict(Expect("gap"), lambda: [ATTACK])[1]


def test_a_correct_refusal_passes_and_names_its_exception_class():
    def thunk():
        raise ValueError(ATTACK)
    found, why = verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(thunk))
    assert why == [] and found[0].startswith("ValueError:")


def test_a_scenario_that_crashes_fails():
    def crash():
        raise KeyError("boom")
    assert verdict(Expect("problems", required=(ATTACK,)), crash)[1]
    assert verdict(Expect("clean"), crash)[1]
    assert verdict(ATTACK, crash)[1]


def test_a_crash_is_accepted_only_when_declared_refused_with_that_exception_class():
    def crash():
        raise OverflowError("too big")
    assert verdict(Expect("refused", required=("too big",), raises=("OverflowError",)), crash)[1] == []
    assert verdict(Expect("refused", required=("too big",), raises=("ValueError",)), crash)[1]
    assert verdict(Expect("problems", required=("too big",)), crash)[1]


def test_a_scenario_that_unexpectedly_succeeds_fails():
    assert verdict(Expect("problems", required=(ATTACK,)), lambda: [])[1]
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(lambda: None))[1]
    assert verdict(ATTACK, lambda: [])[1]


def test_a_scenario_that_fails_at_the_wrong_boundary_fails():
    def wrong_boundary():
        raise TypeError("a different refusal")
    assert verdict(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: refused(wrong_boundary))[1]
    assert verdict(Expect("problems", required=(ATTACK,)), lambda: [UNRELATED])[1]


def test_a_scenario_that_returns_an_unlisted_extra_problem_fails():
    found, why = verdict(Expect("problems", required=(ATTACK,), allowed_extra=("consequence",)),
                         lambda: [ATTACK, "a consequence", UNRELATED])
    assert len(found) == 3 and any("unlisted extra" in w for w in why)
    assert verdict(Expect("problems", required=(ATTACK,)), lambda: [ATTACK, UNRELATED])[1]


def test_a_missing_required_problem_fails_even_when_another_is_present():
    assert verdict(Expect("problems", required=(ATTACK, "second"), allowed_extra=()), lambda: [ATTACK])[1]


def test_a_forbidden_text_fails_a_scenario_that_otherwise_matches():
    assert verdict(Expect("problems", required=(ATTACK,), allowed_extra=("verified",), forbidden=("verified",)),
                   lambda: [ATTACK, "verified"])[1]


def test_a_refusal_that_mutated_state_fails():
    ledger = []

    def mutate_then_refuse():
        ledger.append("half written")
        raise ValueError(ATTACK)
    found = refused(mutate_then_refuse, state=lambda: len(ledger))
    assert found[0].startswith("ValueError:") and found[1].startswith(oracle.STATE_CHANGED)
    expect = Expect("refused", required=(ATTACK,), raises=("ValueError",))
    assert judge(expect, lambda: found)[1]


def test_a_refusal_that_left_state_alone_passes():
    ledger = ["one"]

    def refuse():
        raise ValueError(ATTACK)
    found = refused(refuse, state=lambda: tuple(ledger))
    assert len(found) == 1
    assert judge(Expect("refused", required=(ATTACK,), raises=("ValueError",)), lambda: found)[1] == []


def test_refused_catches_overflow_error_as_a_refusal():
    def overflow():
        raise OverflowError("too large")
    assert refused(overflow)[0].startswith("OverflowError:")


def test_a_plain_string_keeps_its_old_meaning():
    assert verdict("", lambda: [])[1] == []
    assert verdict("", lambda: [ATTACK])[1]
    assert verdict(ATTACK, lambda: [UNRELATED, ATTACK])[1] == []
    assert verdict(ATTACK, lambda: [UNRELATED])[1]


def test_an_expect_that_names_nothing_is_refused_when_built():
    with pytest.raises(ValueError):
        Expect("problems")
    with pytest.raises(ValueError):
        Expect("nonsense")
    with pytest.raises(ValueError):
        Expect("clean", required=(ATTACK,))
    with pytest.raises(TypeError):
        Expect("problems", required=ATTACK)  # type: ignore[arg-type]

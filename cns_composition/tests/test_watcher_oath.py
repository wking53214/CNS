"""watcher_oath: the Watcher is sworn to leave the record alone, and CNS checks it did."""

import copy

import pytest
from cns.gate import Gate, GateOutcome, GatePosition, subject_digest

from cns_composition.watcher_oath import Narration, WatcherLeftRecordAlone

PASS, BREACH = GateOutcome.PASS, GateOutcome.TERMINAL_BREACH


def record(**over):
    base = {"schema": "cns.run/1", "contract": "1", "decision": "ACCEPT", "reason": "all checks held",
            "converged": True, "finished": True, "put_back": False, "held_digest": "ab" * 8,
            "notes": ["one"], "observed": ["ghost-1"], "verdict": {"decision": "ACCEPT"}, "cycles": [{"number": 1}]}
    base.update(over)
    return base


def check(before, after):
    return WatcherLeftRecordAlone().check(Narration(before, after))


def test_it_is_an_omega_gate_that_satisfies_the_protocol():
    g = WatcherLeftRecordAlone()
    assert isinstance(g, Gate) and g.position is GatePosition.OMEGA and g.name.startswith("watcher_mcu.")


def test_an_untouched_record_passes_and_the_verdict_is_bound_to_it():
    before = record()
    result = check(before, copy.deepcopy(before))
    assert result.outcome is PASS and result.bound()
    assert result.binds("watcher_narration", subject_digest(before))


@pytest.mark.parametrize("edit", [
    lambda r: r.update(decision="REJECT"),
    lambda r: r["verdict"].update(decision="REJECT"),
    lambda r: r["notes"].append("added by the Watcher"),
    lambda r: r.update(put_back=True),
    lambda r: r.update(watcher_comment="looks fine to me"),
    lambda r: r.pop("cycles"),
    lambda r: r["cycles"][0].update(number=2),
])
def test_any_change_to_the_record_is_a_breach_bound_to_the_record_that_went_in(edit):
    before = record()
    after = copy.deepcopy(before)
    edit(after)
    result = check(before, after)
    assert result.outcome is BREACH and "interfere" in result.reason
    assert result.binds("watcher_narration", subject_digest(before))


def test_a_record_that_is_no_longer_a_run_record_afterwards_is_a_breach():
    result = check(record(), {"decision": "ACCEPT"})
    assert result.outcome is BREACH and "no longer reads" in result.reason and result.bound()


def test_a_record_that_was_never_a_run_record_judges_nothing():
    result = check(record(schema="cns.run/0"), record(schema="cns.run/0"))
    assert result.outcome is BREACH and not result.bound() and "not a run record" in result.reason


def test_content_that_cannot_be_bound_is_a_breach_not_an_exception():
    odd = record(extra=object())
    result = check(odd, odd)
    assert result.outcome is BREACH and not result.bound() and "cannot be described" in result.reason


def test_something_that_is_not_a_narration_is_a_breach():
    result = WatcherLeftRecordAlone().check(record())
    assert result.outcome is BREACH and not result.bound()


def test_a_record_the_watcher_left_with_content_that_cannot_be_bound_is_a_breach_bound_to_what_went_in():
    before = record()
    result = check(before, record(extra=object()))
    assert result.outcome is BREACH and "no longer reads" in result.reason
    assert result.binds("watcher_narration", subject_digest(before))

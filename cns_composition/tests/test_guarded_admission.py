"""The resubmission guard in front of the CCC record check (guarded_admission).

CCC is not installed in CNS's CI, so CCC's answers are played by a stand-in
lookup, as in test_ccc_admission.py.
"""

from __future__ import annotations

import pytest

from cns.gate import GateOutcome
from cns_composition.ccc_admission import (
    GATE_NAME as CCC_GATE,
)
from cns_composition.ccc_admission import (
    TriadOutput,
    UnrecordedTriadOutput,
    text_digest,
)
from cns_composition.guarded_admission import GuardedCccRecordGate, guarded_admit
from cns_composition.resubmission import GATE_NAME as GUARD_GATE
from cns_composition.resubmission import ResubmissionGuard

ITEM = TriadOutput(candidate_id="c1", text="Red finding: the retry path never re-reads the lease.")
REVISED = TriadOutput(candidate_id="c1", text="Red finding: the retry path re-reads the lease once.")


class Lookup:
    """Answers a fixed status and records what it was asked."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def status(self, source, candidate_id, text_digest):
        self.asked.append((source, candidate_id, text_digest))
        return self.answer


def test_a_held_item_passes_both_checks():
    gate = GuardedCccRecordGate(Lookup("held"), ResubmissionGuard())

    result = gate.check(ITEM)

    assert result.outcome is GateOutcome.PASS
    assert result.gate == CCC_GATE


def test_an_absent_item_is_retried_until_the_guard_refuses_the_unchanged_resubmission():
    lookup = Lookup("absent")
    gate = GuardedCccRecordGate(lookup, ResubmissionGuard(max_unchanged=3))

    outcomes = [gate.check(ITEM).outcome for _ in range(3)]
    assert outcomes == [GateOutcome.RETRY] * 3

    asked_before = len(lookup.asked)
    fourth = gate.check(ITEM)

    assert fourth.outcome is GateOutcome.TERMINAL_BREACH
    assert fourth.gate == GUARD_GATE
    assert len(lookup.asked) == asked_before, "CCC must not be asked once the guard refuses"


def test_a_changed_resubmission_is_judged_by_ccc_again():
    lookup = Lookup("absent")
    gate = GuardedCccRecordGate(lookup, ResubmissionGuard())
    gate.check(ITEM)

    result = gate.check(REVISED)

    assert result.outcome is GateOutcome.RETRY
    assert result.gate == CCC_GATE
    assert lookup.asked[-1][2] == text_digest(REVISED.text)


def test_a_return_to_an_earlier_version_is_refused_as_oscillation():
    gate = GuardedCccRecordGate(Lookup("absent"), ResubmissionGuard())
    gate.check(ITEM)
    gate.check(REVISED)

    back = gate.check(ITEM)

    assert back.outcome is GateOutcome.TERMINAL_BREACH
    assert back.gate == GUARD_GATE
    assert "oscillation" in back.reason


def test_an_altered_record_is_still_a_breach_from_ccc():
    gate = GuardedCccRecordGate(Lookup("altered"), ResubmissionGuard())

    result = gate.check(ITEM)

    assert result.outcome is GateOutcome.TERMINAL_BREACH
    assert result.gate == CCC_GATE


def test_the_gate_refuses_anything_that_is_not_triad_output():
    gate = GuardedCccRecordGate(Lookup("held"), ResubmissionGuard())

    with pytest.raises(TypeError):
        gate.check("not triad output")


def test_the_gate_refuses_a_guard_it_was_not_given():
    with pytest.raises(TypeError):
        GuardedCccRecordGate(Lookup("held"), guard=None)


def test_guarded_admit_returns_the_output_when_ccc_holds_it():
    assert guarded_admit(ITEM, Lookup("held"), ResubmissionGuard()) is ITEM


def test_guarded_admit_raises_with_the_verdict_when_ccc_does_not_hold_it():
    with pytest.raises(UnrecordedTriadOutput) as info:
        guarded_admit(ITEM, Lookup("absent"), ResubmissionGuard())

    assert info.value.result.outcome is GateOutcome.RETRY


def test_guarded_admit_counts_retries_across_calls_through_one_guard():
    guard = ResubmissionGuard(max_unchanged=2)
    lookup = Lookup("absent")

    for _ in range(2):
        with pytest.raises(UnrecordedTriadOutput):
            guarded_admit(ITEM, lookup, guard)

    with pytest.raises(UnrecordedTriadOutput) as info:
        guarded_admit(ITEM, lookup, guard)

    assert info.value.result.gate == GUARD_GATE
    assert info.value.result.outcome is GateOutcome.TERMINAL_BREACH

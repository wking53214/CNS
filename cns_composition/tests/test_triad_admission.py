"""The retry loop for Triad output entering CNS (cns_composition.triad_admission).

Triad-42 and CCC are not installed in CNS's CI. A stand-in hand_off plays the
part of Triad-42's handoff, and a stand-in lookup plays CCC's record check.
"""

from __future__ import annotations

import pytest

from cns.gate import GateOutcome
from cns_composition.ccc_admission import GATE_NAME as CCC_GATE
from cns_composition.ccc_admission import TriadOutput, UnrecordedTriadOutput
from cns_composition.resubmission import GATE_NAME as GUARD_GATE
from cns_composition.resubmission import ResubmissionGuard
from cns_composition.triad_admission import admit_candidates

A = TriadOutput(candidate_id="a", text="first finding")
B = TriadOutput(candidate_id="b", text="second finding")


class Lookup:
    """CCC's answer. `answer` can be changed by the test."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = 0

    def status(self, source, candidate_id, text_digest):
        self.asked += 1
        return self.answer


class HandOff:
    """Counts hand-offs. `on_call` lets a test make CCC record the items."""

    def __init__(self, on_call=None):
        self.calls = 0
        self._on_call = on_call

    def __call__(self):
        self.calls += 1
        if self._on_call is not None:
            self._on_call()


def test_held_candidates_are_admitted_in_order_without_a_handoff():
    hand_off = HandOff()

    admitted = admit_candidates([A, B], hand_off, Lookup("held"), ResubmissionGuard())

    assert admitted == [A, B]
    assert hand_off.calls == 0


def test_a_candidate_recorded_after_one_handoff_is_admitted():
    lookup = Lookup("absent")
    hand_off = HandOff(on_call=lambda: setattr(lookup, "answer", "held"))

    admitted = admit_candidates([A], hand_off, lookup, ResubmissionGuard())

    assert admitted == [A]
    assert hand_off.calls == 1


def test_a_candidate_never_recorded_is_stopped_by_the_guard_at_its_cap():
    guard = ResubmissionGuard(max_unchanged=3)
    hand_off = HandOff()

    with pytest.raises(UnrecordedTriadOutput) as info:
        admit_candidates([A], hand_off, Lookup("absent"), guard)

    assert info.value.result.gate == GUARD_GATE
    assert info.value.result.outcome is GateOutcome.TERMINAL_BREACH
    assert hand_off.calls == guard.max_unchanged


def test_an_altered_record_is_refused_at_once_without_a_handoff():
    hand_off = HandOff()

    with pytest.raises(UnrecordedTriadOutput) as info:
        admit_candidates([A], hand_off, Lookup("altered"), ResubmissionGuard())

    assert info.value.result.gate == CCC_GATE
    assert info.value.result.outcome is GateOutcome.TERMINAL_BREACH
    assert hand_off.calls == 0


def test_a_refusal_stops_later_candidates_from_being_admitted():
    lookup = Lookup("altered")

    with pytest.raises(UnrecordedTriadOutput):
        admit_candidates([A, B], HandOff(), lookup, ResubmissionGuard())

    assert lookup.asked == 1


def test_hand_off_must_be_callable():
    with pytest.raises(TypeError):
        admit_candidates([A], "not callable", Lookup("held"), ResubmissionGuard())


def test_a_candidate_that_is_not_triad_output_is_refused():
    with pytest.raises(TypeError):
        admit_candidates(["not triad output"], HandOff(), Lookup("held"), ResubmissionGuard())


def test_an_error_from_hand_off_propagates_unchanged():
    def broken():
        raise RuntimeError("CCC is down")

    with pytest.raises(RuntimeError, match="CCC is down"):
        admit_candidates([A], broken, Lookup("absent"), ResubmissionGuard())

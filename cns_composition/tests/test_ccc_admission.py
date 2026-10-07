"""Rule 2, no CCC record, no use (cns_composition.ccc_admission).

CCC is not installed in CNS's CI, so CCC's answers are played by a stand-in
lookup here. CCC's own suite tests that it gives these answers
(ccc/tests/test_record_status.py).
"""

from __future__ import annotations

from hashlib import sha256

import pytest

from cns.gate import Gate, GateChain, GateOutcome, GatePosition, subject_digest
from cns_composition.ccc_admission import (
    GATE_NAME,
    SOURCE,
    CccRecordGate,
    RecordLookup,
    TriadOutput,
    UnrecordedTriadOutput,
    admit,
    text_digest,
)

ITEM = TriadOutput(candidate_id="c1", text="Red finding: the retry path never re-reads the lease.")


class Lookup:
    """Answers a fixed status and records what it was asked."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def status(self, source, candidate_id, text_digest):
        self.asked.append((source, candidate_id, text_digest))
        return self.answer


class Broken:
    def status(self, source, candidate_id, text_digest):
        raise RuntimeError("store unreadable")


def test_recorded_output_passes_and_is_returned():
    assert admit(ITEM, Lookup("held")) is ITEM
    assert CccRecordGate(Lookup("held")).check(ITEM).outcome is GateOutcome.PASS


@pytest.mark.parametrize("answer, outcome", [
    ("absent", GateOutcome.RETRY),
    ("altered", GateOutcome.TERMINAL_BREACH),
    ("erased", GateOutcome.TERMINAL_BREACH),
    ("redacted", GateOutcome.TERMINAL_BREACH),
])
def test_anything_but_held_is_refused(answer, outcome):
    result = CccRecordGate(Lookup(answer)).check(ITEM)
    assert result.outcome is outcome
    assert result.blocking()
    with pytest.raises(UnrecordedTriadOutput) as raised:
        admit(ITEM, Lookup(answer))
    assert raised.value.result == result


@pytest.mark.parametrize("answer", ["HELD", "yes", "", None, True, 1, ("held",)])
def test_unrecognised_answer_is_never_permission(answer):
    result = CccRecordGate(Lookup(answer)).check(ITEM)
    assert result.outcome is GateOutcome.TERMINAL_BREACH
    assert "unrecognised" in result.reason
    with pytest.raises(UnrecordedTriadOutput):
        admit(ITEM, Lookup(answer))


def test_question_is_source_id_and_fingerprint_of_the_text():
    lookup = Lookup("held")
    admit(ITEM, lookup)
    expected = sha256(ITEM.text.encode("utf-8")).hexdigest()
    assert lookup.asked == [(SOURCE, "c1", expected)]
    assert SOURCE == "triad42"
    assert text_digest(ITEM.text) == expected


def test_lookup_failure_propagates_rather_than_passing():
    with pytest.raises(RuntimeError, match="store unreadable"):
        admit(ITEM, Broken())


@pytest.mark.parametrize("lookup", [None, object(), "ccc", {"status": "held"}])
def test_no_lookup_no_use(lookup):
    with pytest.raises(TypeError, match="Without CCC"):
        CccRecordGate(lookup)
    with pytest.raises(TypeError):
        admit(ITEM, lookup)


@pytest.mark.parametrize("candidate", [ITEM.text, {"candidate_id": "c1", "text": "x"}, None])
def test_only_triad_output_is_judged(candidate):
    with pytest.raises(TypeError):
        CccRecordGate(Lookup("held")).check(candidate)


@pytest.mark.parametrize("kwargs", [
    {"candidate_id": "", "text": "x"},
    {"candidate_id": "c1", "text": ""},
    {"candidate_id": None, "text": "x"},
    {"candidate_id": "c1", "text": 3},
])
def test_malformed_output_is_refused_at_construction(kwargs):
    with pytest.raises(ValueError):
        TriadOutput(**kwargs)


def test_verdict_is_bound_to_what_it_judged():
    result = CccRecordGate(Lookup("held")).check(ITEM)
    content = {"source": SOURCE, "candidate_id": "c1", "text_digest": text_digest(ITEM.text)}
    assert result.gate == GATE_NAME
    assert result.binds(f"{SOURCE}:c1", subject_digest(content))
    changed = TriadOutput(candidate_id="c1", text=ITEM.text + " (edited)")
    other = CccRecordGate(Lookup("held")).check(changed)
    assert not result.binds(other.subject, other.subject_digest)


def test_gate_is_an_alpha_cns_gate():
    gate = CccRecordGate(Lookup("held"))
    assert isinstance(gate, Gate)
    assert gate.position is GatePosition.ALPHA
    assert GateChain(alpha=(gate,)).misplaced() == ()
    assert GateChain(omega=(gate,)).misplaced() == (GATE_NAME,)


def test_stand_in_satisfies_the_protocol():
    assert isinstance(Lookup("held"), RecordLookup)


def test_nothing_is_cached_between_questions():
    lookup = Lookup("held")
    gate = CccRecordGate(lookup)
    gate.check(ITEM)
    lookup.answer = "erased"
    assert gate.check(ITEM).outcome is GateOutcome.TERMINAL_BREACH
    assert len(lookup.asked) == 2

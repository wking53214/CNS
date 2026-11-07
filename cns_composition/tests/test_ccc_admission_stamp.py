"""The door checks the handoff's stamp itself (CNS-012/013 option A): a stand-in store that answers "held" is not
believed. CNS imports no repository: the lookups here are stand-ins, and the stamp formula is checked against
contracts/handoff-stamp-vectors.json, which was generated with CCC's own attest."""

import json
import pathlib

import pytest
from cns.gate import GateOutcome

from cns_composition.ccc_admission import (
    SOURCE,
    CccRecordGate,
    TriadOutput,
    UnrecordedTriadOutput,
    admit,
    handoff_stamp,
    text_digest,
)
from cns_composition.resubmission import ResubmissionGuard
from cns_composition.triad_admission import admit_candidates

VECTORS = json.loads((pathlib.Path(__file__).resolve().parents[2] / "contracts" / "handoff-stamp-vectors.json")
                     .read_text(encoding="utf-8"))
KEY = b"k" * 32
ITEM = TriadOutput(candidate_id="c1", text="Red finding: the retry path never re-reads the lease.")
GOOD = handoff_stamp(KEY, source=SOURCE, candidate_id="c1", text_digest=text_digest(ITEM.text))


class Says:
    """A store that answers what it is told to and shows what stamps it is told to."""

    def __init__(self, answer="held", stamps=()):
        self.answer, self._stamps = answer, stamps

    def status(self, source, candidate_id, text_digest):
        return self.answer

    def stamps(self, source, candidate_id, text_digest):
        return self._stamps


class OnlySaysHeld:
    """The stand-in the finding describes: one method, and it says yes."""

    def status(self, source, candidate_id, text_digest):
        return "held"


@pytest.mark.parametrize("row", VECTORS["vectors"], ids=lambda r: r["candidate_id"])
def test_the_stamp_formula_matches_the_vectors_made_with_cccs_attest(row):
    assert handoff_stamp(bytes.fromhex(row["key_hex"]), source=row["source"], candidate_id=row["candidate_id"],
                         text_digest=row["text_digest"]) == row["stamp"]


def test_a_store_showing_the_handoffs_stamp_is_admitted():
    assert CccRecordGate(Says(stamps=(GOOD,)), attestation_key=KEY).check(ITEM).outcome is GateOutcome.PASS
    assert admit(ITEM, Says(stamps=("decoy", GOOD)), attestation_key=KEY) is ITEM


def test_with_a_key_a_stand_in_that_only_says_held_is_refused_before_it_is_asked_anything():
    with pytest.raises(TypeError, match="shows the handoff's stamps"):
        CccRecordGate(OnlySaysHeld(), attestation_key=KEY)


@pytest.mark.parametrize("stamps", [(), ("0" * 64,), (handoff_stamp(b"o" * 32, source=SOURCE, candidate_id="c1",
                                                                   text_digest=text_digest(ITEM.text)),),
                                    GOOD, None, (None, 7)])
def test_a_held_answer_without_a_stamp_that_verifies_is_a_breach(stamps):
    result = CccRecordGate(Says(stamps=stamps), attestation_key=KEY).check(ITEM)
    assert result.outcome is GateOutcome.TERMINAL_BREACH and "stamp" in result.reason
    with pytest.raises(UnrecordedTriadOutput):
        admit(ITEM, Says(stamps=stamps), attestation_key=KEY)


def test_a_stamp_for_another_item_does_not_verify_this_one():
    other = handoff_stamp(KEY, source=SOURCE, candidate_id="c2", text_digest=text_digest(ITEM.text))
    assert CccRecordGate(Says(stamps=(other,)), attestation_key=KEY).check(ITEM).outcome is GateOutcome.TERMINAL_BREACH


@pytest.mark.parametrize("answer,outcome", [("absent", GateOutcome.RETRY), ("erased", GateOutcome.TERMINAL_BREACH)])
def test_answers_other_than_held_mean_what_they_meant_with_a_key(answer, outcome):
    assert CccRecordGate(Says(answer, stamps=(GOOD,)), attestation_key=KEY).check(ITEM).outcome is outcome


def test_without_a_key_the_stand_in_is_still_believed():
    """A recorded gap, stated as an assertion: with no key the door takes the store's word."""
    assert admit(ITEM, OnlySaysHeld()) is ITEM


@pytest.mark.parametrize("bad", [b"", b"short", "k" * 32, 5])
def test_a_key_that_is_not_long_enough_bytes_is_refused(bad):
    with pytest.raises(ValueError):
        CccRecordGate(Says(), attestation_key=bad)


def test_the_key_reaches_the_gate_through_the_retry_loop():
    with pytest.raises(UnrecordedTriadOutput) as refused:
        admit_candidates([ITEM], hand_off=lambda: None, lookup=Says(stamps=()), guard=ResubmissionGuard(),
                         attestation_key=KEY)
    assert "stamp" in refused.value.result.reason
    assert admit_candidates([ITEM], hand_off=lambda: None, lookup=Says(stamps=(GOOD,)), guard=ResubmissionGuard(),
                            attestation_key=KEY) == [ITEM]

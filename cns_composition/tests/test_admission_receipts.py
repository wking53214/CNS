"""Admitted is not forever (CNS-012): a receipt per admitted item, and `use` asks CCC again at the moment of use."""

import dataclasses

import pytest
from cns.gate import GateOutcome

from cns_composition.ccc_admission import SOURCE, TriadOutput, UnrecordedTriadOutput, handoff_stamp, text_digest
from cns_composition.resubmission import ResubmissionGuard
from cns_composition.triad_admission import AdmissionReceipt, admit_candidates, admit_with_receipts, recheck, use

ITEM = TriadOutput(candidate_id="c1", text="Red finding: the retry path never re-reads the lease.")
KEY = b"k" * 32


class Store:
    """A CCC stand-in whose answer the test changes between admission and use."""

    def __init__(self, answer="held", stamps=()):
        self.answer, self._stamps = answer, stamps

    def status(self, source, candidate_id, text_digest):
        return self.answer

    def stamps(self, source, candidate_id, text_digest):
        return self._stamps


def admitted(store, **kw):
    return admit_with_receipts([ITEM], hand_off=lambda: None, lookup=store, guard=ResubmissionGuard(), **kw)


def test_an_admission_returns_a_receipt_bound_to_its_item():
    (receipt,) = admitted(Store())
    assert receipt.output == ITEM and receipt.verdict.outcome is GateOutcome.PASS
    assert receipt.verdict.subject == f"{SOURCE}:c1"


def test_an_item_still_held_at_use_is_returned():
    store = Store()
    (receipt,) = admitted(store)
    assert use(receipt, store) == ITEM


@pytest.mark.parametrize("later", ["erased", "redacted", "rejected", "superseded", "altered"])
def test_an_item_removed_after_admission_fails_its_recheck_at_use(later):
    store = Store()
    (receipt,) = admitted(store)
    store.answer = later
    assert recheck(receipt, store).outcome is GateOutcome.TERMINAL_BREACH
    with pytest.raises(UnrecordedTriadOutput):
        use(receipt, store)


def test_the_recheck_uses_the_key_when_one_is_given():
    good = handoff_stamp(KEY, source=SOURCE, candidate_id="c1", text_digest=text_digest(ITEM.text))
    store = Store(stamps=(good,))
    (receipt,) = admitted(store, attestation_key=KEY)
    assert use(receipt, store, attestation_key=KEY) == ITEM
    store._stamps = ()  # the stamped record is gone; a store still saying held is not enough
    with pytest.raises(UnrecordedTriadOutput, match="stamp"):
        use(receipt, store, attestation_key=KEY)


@pytest.mark.parametrize("forge", [
    lambda r: dataclasses.replace(r, output=TriadOutput("c1", "other text")),
    lambda r: dataclasses.replace(r, output=TriadOutput("c2", r.output.text)),
    lambda r: dataclasses.replace(r, verdict=dataclasses.replace(r.verdict, outcome=GateOutcome.RETRY)),
    lambda r: dataclasses.replace(r, verdict=dataclasses.replace(r.verdict, subject_digest="")),
])
def test_a_receipt_that_does_not_bind_its_own_item_admitted_nothing(forge):
    store = Store()
    (receipt,) = admitted(store)
    result = recheck(forge(receipt), store)
    assert result.outcome is GateOutcome.TERMINAL_BREACH and "admitted nothing" in result.reason


def test_only_a_receipt_is_rechecked():
    with pytest.raises(TypeError):
        recheck(ITEM, Store())


def test_admit_candidates_returns_exactly_the_items_the_receipts_carry():
    store = Store()
    assert admit_candidates([ITEM], hand_off=lambda: None, lookup=store, guard=ResubmissionGuard()) == \
        [r.output for r in admitted(store)]


def test_a_refusal_at_admission_still_raises_and_issues_no_receipt():
    with pytest.raises(UnrecordedTriadOutput):
        admitted(Store("erased"))


def test_retry_hands_off_then_issues_the_receipt():
    store = Store("absent")
    calls = []

    def hand_off():
        calls.append(1)
        store.answer = "held"

    (receipt,) = admit_with_receipts([ITEM], hand_off=hand_off, lookup=store, guard=ResubmissionGuard())
    assert calls == [1] and isinstance(receipt, AdmissionReceipt)

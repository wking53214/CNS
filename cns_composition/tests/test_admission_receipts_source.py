"""Receipts remember their source (Step 3): admitting, rechecking and using an item all ask CCC under one name, and
a receipt cannot be moved from one source to another."""

import dataclasses

import pytest
from cns.gate import GateOutcome

from cns_composition.ccc_admission import SOURCE, TriadOutput, UnrecordedTriadOutput
from cns_composition.resubmission import ResubmissionGuard
from cns_composition.triad_admission import (
    AdmissionReceipt,
    admit_candidates,
    admit_with_receipts,
    recheck,
    use,
)

A, B = TriadOutput("a1", "the config exposes a secret"), TriadOutput("a2", "the loop is unbounded")


class Records:
    """A store whose answers can change between asking, keyed by (source, candidate)."""

    def __init__(self, answers):
        self.answers, self.asked = dict(answers), []

    def status(self, source, candidate_id, text_digest):
        self.asked.append(source)
        return self.answers.get((source, candidate_id), "absent")


def _admit(store, source="scanner", items=(A, B)):
    return admit_with_receipts(items, lambda: None, store, ResubmissionGuard(), source=source)


def test_receipts_carry_the_source_they_were_admitted_under():
    receipts = _admit(Records({("scanner", "a1"): "held", ("scanner", "a2"): "held"}))
    assert [r.source for r in receipts] == ["scanner", "scanner"]
    assert [r.verdict.subject for r in receipts] == ["scanner:a1", "scanner:a2"]


def test_the_default_receipt_is_the_triads():
    store = Records({(SOURCE, "a1"): "held"})
    (receipt,) = admit_with_receipts([A], lambda: None, store, ResubmissionGuard())
    assert receipt.source == SOURCE and receipt.verdict.subject == f"{SOURCE}:a1"


def test_admit_candidates_passes_the_source_through():
    store = Records({("scanner", "a1"): "held", ("scanner", "a2"): "held"})
    assert admit_candidates([A, B], lambda: None, store, ResubmissionGuard(), source="scanner") == [A, B]
    assert set(store.asked) == {"scanner"}


def test_use_and_recheck_ask_under_the_receipts_source_and_honour_a_later_erasure():
    store = Records({("scanner", "a1"): "held", ("scanner", "a2"): "held"})
    first, second = _admit(store)
    assert use(first, store) is A
    store.answers[("scanner", "a2")] = "erased"
    assert recheck(second, store).outcome is GateOutcome.TERMINAL_BREACH
    with pytest.raises(UnrecordedTriadOutput):
        use(second, store)
    assert use(first, store) is A


def test_a_scanner_receipt_cannot_be_passed_off_as_the_triads():
    store = Records({("scanner", "a1"): "held", (SOURCE, "a1"): "held"})
    (receipt,) = _admit(store, items=[A])
    moved = dataclasses.replace(receipt, source=SOURCE)
    assert recheck(moved, store).outcome is GateOutcome.TERMINAL_BREACH
    assert recheck(receipt, store).outcome is GateOutcome.PASS


def test_a_receipt_with_a_bad_source_is_a_breach_not_a_crash():
    store = Records({("scanner", "a1"): "held"})
    (receipt,) = _admit(store, items=[A])
    for bad in ("", None):
        forged = dataclasses.replace(receipt, source=bad)
        assert recheck(forged, store).outcome is GateOutcome.TERMINAL_BREACH


def test_old_two_argument_receipts_still_build():
    store = Records({(SOURCE, "a1"): "held"})
    (receipt,) = admit_with_receipts([A], lambda: None, store, ResubmissionGuard())
    assert AdmissionReceipt(receipt.output, receipt.verdict).source == SOURCE

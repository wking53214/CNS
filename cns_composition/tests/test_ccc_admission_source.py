"""The CCC record gate takes the source it asks about (Step 1): the Triad stays the default, and another advisory
source is judged under its own name, with its own stamp, and its verdicts bind to it alone."""

import pytest
from cns.gate import GateOutcome

from cns_composition.ccc_admission import (
    GATE_NAME,
    SOURCE,
    CccRecordGate,
    TriadOutput,
    handoff_stamp,
    text_digest,
)

KEY = b"k" * 32
ITEM = TriadOutput(candidate_id="c1", text="The config exposes a secret.")


class Records:
    """A stand-in store that records what it was asked and answers per source."""

    def __init__(self, answers, stamps=None):
        self.answers, self.shown, self.asked = answers, stamps or {}, []

    def status(self, source, candidate_id, text_digest):
        self.asked.append((source, candidate_id, text_digest))
        return self.answers.get(source, "absent")

    def stamps(self, source, candidate_id, text_digest):
        return self.shown.get(source, ())


def test_the_default_source_is_the_triad_and_nothing_about_it_changes():
    store = Records({SOURCE: "held"})
    result = CccRecordGate(store).check(ITEM)
    assert result.outcome is GateOutcome.PASS
    assert store.asked == [(SOURCE, "c1", text_digest(ITEM.text))]
    assert result.subject == f"{SOURCE}:c1"


def test_another_source_is_asked_about_under_its_own_name():
    store = Records({"scanner": "held"})
    result = CccRecordGate(store, source="scanner").check(ITEM)
    assert result.outcome is GateOutcome.PASS
    assert store.asked == [("scanner", "c1", text_digest(ITEM.text))]
    assert result.subject == "scanner:c1" and result.gate == GATE_NAME


def test_a_record_held_for_the_triad_does_not_admit_the_same_item_for_another_source():
    store = Records({SOURCE: "held"})
    assert CccRecordGate(store, source="scanner").check(ITEM).outcome is GateOutcome.RETRY


def test_a_verdict_binds_to_its_own_source_only():
    store = Records({SOURCE: "held", "scanner": "held"})
    triad = CccRecordGate(store).check(ITEM)
    scanner = CccRecordGate(store, source="scanner").check(ITEM)
    assert triad.subject_digest != scanner.subject_digest


def test_the_stamp_is_checked_for_the_source_the_gate_names():
    mine = handoff_stamp(KEY, source="scanner", candidate_id="c1", text_digest=text_digest(ITEM.text))
    triads = handoff_stamp(KEY, source=SOURCE, candidate_id="c1", text_digest=text_digest(ITEM.text))
    good = Records({"scanner": "held"}, {"scanner": (mine,)})
    wrong = Records({"scanner": "held"}, {"scanner": (triads,)})
    assert CccRecordGate(good, attestation_key=KEY, source="scanner").check(ITEM).outcome is GateOutcome.PASS
    breach = CccRecordGate(wrong, attestation_key=KEY, source="scanner").check(ITEM)
    assert breach.outcome is GateOutcome.TERMINAL_BREACH and "stamp" in breach.reason


@pytest.mark.parametrize("bad", ["", None, 7, b"scanner"])
def test_a_source_must_be_a_non_empty_string(bad):
    with pytest.raises(ValueError, match="source"):
        CccRecordGate(Records({}), source=bad)

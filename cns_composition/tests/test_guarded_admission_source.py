"""The guarded door takes the source too (Step 2): the resubmission guard counts per source, so one source's
retries never spend another's cap."""

import pytest
from cns.gate import GateOutcome

from cns_composition.ccc_admission import SOURCE, TriadOutput, UnrecordedTriadOutput
from cns_composition.guarded_admission import GuardedCccRecordGate, guarded_admit
from cns_composition.resubmission import ResubmissionGuard

ITEM = TriadOutput(candidate_id="c1", text="The config exposes a secret.")


class Records:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def status(self, source, candidate_id, text_digest):
        self.asked.append(source)
        return self.answers.get(source, "absent")


def test_the_guarded_door_asks_about_the_named_source():
    store = Records({"scanner": "held"})
    assert guarded_admit(ITEM, store, ResubmissionGuard(), source="scanner") is ITEM
    assert store.asked == ["scanner"]


def test_the_default_is_still_the_triad():
    store = Records({SOURCE: "held"})
    assert guarded_admit(ITEM, store, ResubmissionGuard()) is ITEM
    assert store.asked == [SOURCE]


def test_the_verdict_names_the_source():
    gate = GuardedCccRecordGate(Records({"scanner": "held"}), ResubmissionGuard(), source="scanner")
    assert gate.check(ITEM).subject == "scanner:c1"


def test_one_sources_retries_do_not_spend_anothers_cap():
    guard = ResubmissionGuard(max_unchanged=2)
    scanner = GuardedCccRecordGate(Records({}), guard, source="scanner")
    linter = GuardedCccRecordGate(Records({}), guard, source="linter")
    outcomes = [scanner.check(ITEM).outcome for _ in range(3)]
    assert outcomes[-1] is GateOutcome.TERMINAL_BREACH
    assert linter.check(ITEM).outcome is GateOutcome.RETRY


def test_a_refusal_for_a_named_source_raises_the_same_way():
    with pytest.raises(UnrecordedTriadOutput):
        guarded_admit(ITEM, Records({"scanner": "erased"}), ResubmissionGuard(), source="scanner")

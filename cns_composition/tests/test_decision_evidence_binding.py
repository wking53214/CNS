"""Candidate to evidence to subject to digest to verdict to decision to root: what each link proves and what it does not.

A matching digest relates a verdict to the bytes or structured object that were hashed. It does not say the object is
authentic, complete, clinically valid or authorized. Those belong to the repository that produces or validates the
evidence. The attacks below are the ones a digest CAN catch; the GAP tests at the end are the ones it cannot, written
as assertions so the day one closes it, the test says so.
"""

import dataclasses
import math

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition.decision_guard import DecisionGuard
from cns_composition.gate_chain import run_chain
from cns_composition.super_gate import Judged, SuperGate, _root

A, OM = GatePosition.ALPHA, GatePosition.OMEGA
PASS, BREACH = GateOutcome.PASS, GateOutcome.TERMINAL_BREACH


class Judge:
    """Binds its PASS to the subject and digest it computes from what it was handed, at the moment it was handed it."""

    def __init__(self, name, position, subject="invoice-1"):
        self.name, self.position, self._subject = name, position, subject

    def check(self, candidate):
        return GateResult(gate=self.name, position=self.position, outcome=PASS, reason="ok",
                          subject=self._subject, subject_digest=subject_digest(dict(candidate)))


def read_binding(subject="invoice-1"):
    return lambda candidate: (subject, subject_digest(dict(candidate)))


def read_doc(candidate):
    return Judged("invoice-1", subject_digest(dict(candidate)))


def strict(candidates, **kw):
    seats = [("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))]
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge"), strict_binding=True,
                     binding_of={"Governance_Gateway:door": read_binding(), "DIT:judge": read_binding()}, **kw)
    return gate.decide(candidates)


TRUE = {"amount": "412.00", "payee": "plumber"}
INFLATED = {"amount": "4120.00", "payee": "plumber"}


# ------------------------------------------------------------------ verdict to candidate: what a digest does catch

def test_a_verdict_binds_the_content_it_was_issued_for_and_not_content_altered_afterwards():
    result = Judge("door", A).check(TRUE)
    assert result.binds("invoice-1", subject_digest(TRUE))
    assert not result.binds("invoice-1", subject_digest({**TRUE, "amount": "9999.00"}))


def test_a_different_candidate_under_a_reused_subject_name_does_not_match_the_verdict():
    result = Judge("door", A).check(TRUE)
    assert not result.binds("invoice-1", subject_digest(INFLATED))


def test_a_digest_reused_under_another_subject_name_does_not_match_the_verdict():
    result = Judge("door", A).check(TRUE)
    assert not result.binds("invoice-2", result.subject_digest)


def test_evidence_changed_after_binding_no_longer_matches_what_the_verdict_recorded():
    evidence = {"lines": ["a", "b"], "total": 2}
    recorded = subject_digest(evidence)
    evidence["lines"].append("c")
    assert subject_digest(evidence) != recorded


def test_a_super_gate_under_strict_binding_refuses_a_gate_that_judged_other_content_than_it_was_handed():
    class Stale(Judge):
        def check(self, candidate):
            return super().check(TRUE)  # judges the true invoice whatever it is given

    seats = [("Governance_Gateway", Stale("door", A)), ("DIT", Judge("judge", OM))]
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge"), strict_binding=True,
                     binding_of={"Governance_Gateway:door": read_binding(), "DIT:judge": read_binding()})
    decision = gate.decide({"Governance_Gateway:door": INFLATED, "DIT:judge": INFLATED})
    assert decision.outcome is BREACH and not decision.allowed
    assert any("bound to something other than this candidate" in r.reason for r in decision.run.results)


def test_a_candidate_edited_between_the_digest_and_the_decision_is_a_breach():
    """The gate hashes the candidate, then something edits it before the reader looks again."""
    class Editing(Judge):
        def check(self, candidate):
            result = super().check(candidate)
            candidate["amount"] = "4120.00"
            return result

    seats = [("Governance_Gateway", Editing("door", A)), ("DIT", Judge("judge", OM))]
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge"), strict_binding=True,
                     binding_of={"Governance_Gateway:door": read_binding(), "DIT:judge": read_binding()})
    decision = gate.decide({"Governance_Gateway:door": dict(TRUE), "DIT:judge": dict(TRUE)})
    assert decision.outcome is BREACH and not decision.allowed


def test_a_substituted_candidate_for_one_seat_is_caught_by_the_agreement_check_as_well():
    seats = [("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))]
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge", "CNS:same_subject"),
                     same_subject={"Governance_Gateway:door": read_doc, "DIT:judge": read_doc})
    decision = gate.decide({"Governance_Gateway:door": TRUE, "DIT:judge": INFLATED})
    assert decision.outcome is BREACH and decision.subject is None
    assert [r.gate for r in decision.run.blocking()] == ["same_subject"]


# ------------------------------------------------------ malformed and empty evidence is not quietly accepted

@pytest.mark.parametrize("bad", [{"x": math.nan}, {"x": math.inf}, {"x": b"bytes"}, {"x": {1, 2}}, {1: "a"}])
def test_evidence_that_cannot_be_described_unambiguously_cannot_be_bound(bad):
    with pytest.raises(TypeError):
        subject_digest(bad)


def test_a_gate_whose_binding_raises_on_malformed_evidence_is_a_breach_and_not_a_pass():
    class Raising(Judge):
        def check(self, candidate):
            return super().check({"x": math.nan})

    run = run_chain([(Raising("door", A), TRUE)], [(Judge("judge", OM), TRUE)])
    assert run.outcome is BREACH and not run.omega_ran
    assert run.results[0].bound() is False


def test_empty_evidence_hashes_to_a_value_that_is_not_the_digest_of_any_real_document():
    empty = subject_digest({})
    assert empty != subject_digest(TRUE)
    assert not Judge("door", A).check(TRUE).binds("invoice-1", empty)


@pytest.mark.parametrize("seen", [Judged("", "abc"), Judged("doc", ""), "no reading"])
def test_a_reading_that_names_no_document_is_a_breach_never_a_match(seen):
    seats = [("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))]
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge", "CNS:same_subject"),
                     same_subject={"Governance_Gateway:door": lambda c: seen, "DIT:judge": lambda c: seen})
    decision = gate.decide({"Governance_Gateway:door": TRUE, "DIT:judge": TRUE})
    assert decision.outcome is BREACH and not decision.allowed


# ----------------------------------------- the decision root is recomputed, and no stored value stands in for it

def good():
    seats = [("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))]
    return SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge", "CNS:same_subject"),
                     same_subject={"Governance_Gateway:door": read_doc, "DIT:judge": read_doc}
                     ).decide({"Governance_Gateway:door": TRUE, "DIT:judge": TRUE})


def test_a_stored_root_that_was_not_computed_from_the_verdicts_binds_nothing():
    decision = good()
    forged = dataclasses.replace(decision, root="0" * 64)
    assert not forged.binds(forged.root) and not forged.binds(decision.root) and not forged.issued


def test_a_root_taken_from_another_decision_does_not_bind_this_one():
    one = good()
    other = SuperGate([("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))],
                      required=("Governance_Gateway:door", "DIT:judge")
                      ).decide({"Governance_Gateway:door": INFLATED, "DIT:judge": INFLATED})
    assert one.root != other.root
    assert not one.binds(other.root) and not other.binds(one.root)


def test_changing_the_order_or_the_membership_of_the_seats_moves_the_root_so_the_old_root_no_longer_binds():
    decision = good()
    reordered = dataclasses.replace(decision, seats=tuple(reversed(decision.seats)))
    assert not reordered.binds(decision.root) and not reordered.issued
    shorter = dataclasses.replace(decision, seats=decision.seats[1:])
    assert not shorter.binds(decision.root) and not shorter.issued


def test_a_verdict_swapped_inside_the_decision_moves_the_root():
    decision = good()
    bent = decision.run.results[0]
    swapped = (dataclasses.replace(bent, subject_digest=subject_digest(INFLATED)),) + decision.run.results[1:]
    edited = dataclasses.replace(decision, run=dataclasses.replace(decision.run, results=swapped))
    assert not edited.binds(decision.root) and not edited.issued
    assert edited.root == decision.root, "the stored value was left alone, which is exactly why it is recomputed"
    assert edited.root != _root(edited.seats, edited.run.results)


def test_a_root_recomputed_over_edited_verdicts_binds_but_the_decision_is_still_not_issued():
    decision = good()
    swapped = (dataclasses.replace(decision.run.results[0], subject_digest=subject_digest(INFLATED)),) \
        + decision.run.results[1:]
    edited = dataclasses.replace(decision, run=dataclasses.replace(decision.run, results=swapped),
                                 root=_root(decision.seats, swapped))
    assert edited.binds(edited.root) and not edited.issued
    with pytest.raises(ValueError, match="not issued"):
        DecisionGuard(read_doc).authorize(edited)


# -------------------------------------- strict binding is something a guard can ask the decision whether it had

def test_a_decision_records_whether_every_seat_was_checked_against_its_own_candidate():
    assert strict({"Governance_Gateway:door": TRUE, "DIT:judge": TRUE}).strict_binding is True
    assert good().strict_binding is False


def test_a_guard_that_requires_strict_binding_refuses_a_decision_that_did_not_check_its_seats():
    with pytest.raises(ValueError, match="strict binding"):
        DecisionGuard(read_doc, require_strict_binding=True).authorize(good())


def test_a_guard_that_requires_strict_binding_accepts_one_that_did():
    seats = [("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))]
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge", "CNS:same_subject"),
                     same_subject={"Governance_Gateway:door": read_doc, "DIT:judge": read_doc},
                     strict_binding=True, binding_of={"Governance_Gateway:door": read_binding(),
                                                      "DIT:judge": read_binding()})
    decision = gate.decide({"Governance_Gateway:door": TRUE, "DIT:judge": TRUE})
    assert decision.strict_binding and decision.allowed
    guard = DecisionGuard(read_doc, require_strict_binding=True)
    guard.authorize(decision)
    assert guard.authorized


def test_claiming_strict_binding_by_hand_voids_the_proof():
    claimed = dataclasses.replace(good(), strict_binding=True)
    assert not claimed.issued
    with pytest.raises(ValueError, match="not issued"):
        DecisionGuard(read_doc, require_strict_binding=True).authorize(claimed)


def test_the_flag_does_not_move_any_root():
    plain = good()
    again = dataclasses.replace(plain, strict_binding=True)
    assert plain.root == again.root and plain.binds(again.root)


# ----------------------------------------------- what a matching digest does not say, recorded so it cannot rot

def test_GAP_internally_consistent_but_forged_evidence_is_allowed_because_a_digest_is_integrity_and_not_authenticity():
    """The evidence is invented; the gate hashed what it was given; every link matches. Whether the evidence is real
    is for the repository that produced it (HERALD signs, TIE pins, Conservation_Kernel checks)."""
    forged = {"amount": "1.00", "payee": "nobody", "source": "made up by the caller"}
    decision = strict({"Governance_Gateway:door": forged, "DIT:judge": forged})
    assert decision.allowed and decision.strict_binding


def test_GAP_a_verdict_from_a_gate_that_passes_what_it_should_not_has_a_perfectly_good_digest():
    """A digest says what a gate judged, not that it judged well."""
    seats = [("Governance_Gateway", Judge("door", A)), ("DIT", Judge("judge", OM))]
    decision = SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge")
                         ).decide({"Governance_Gateway:door": {"amount": "-1"}, "DIT:judge": {"amount": "-1"}})
    assert decision.allowed and all(r.bound() for r in decision.run.results)

"""decision_guard: a one-use permission tied to an approved decision and the document it judged."""

import pytest
from cns.gate import GateOutcome, GatePosition

from cns_composition.decision_guard import DecisionGuard
from cns_composition.super_gate import Judged, SuperGate
from cns_composition.tests.test_super_gate import FakeGate, reads, roster

A, OM = GatePosition.ALPHA, GatePosition.OMEGA
DOOR, JUDGE = "Governance_Gateway:door", "DIT:judge"


def decision(door=GateOutcome.PASS, same=True):
    gate = FakeGate("door", A, door)
    judge = FakeGate("judge", OM)
    seats = [("Governance_Gateway", gate), ("DIT", judge)]
    given = {DOOR: ("doc-1", "abc"), JUDGE: ("doc-1", "abc" if same else "other")}
    return SuperGate(seats, required=(DOOR, JUDGE, "CNS:same_subject"),
                     same_subject={DOOR: reads, JUDGE: reads}).decide(given)


def guard():
    return DecisionGuard(lambda artifact: Judged(*artifact))


def test_a_new_guard_permits_nothing():
    g = guard()
    assert not g.authorized and g(("doc-1", "abc")) is False and not g.spent


def test_an_approved_decision_opens_it_for_the_document_it_judged_and_only_once():
    g = guard()
    g.authorize(decision())
    assert g.authorized
    assert g(("doc-1", "abc")) is True and g.spent
    assert g(("doc-1", "abc")) is False


def test_another_document_is_refused_and_does_not_spend_the_permission():
    g = guard()
    g.authorize(decision())
    assert g(("doc-1", "different content")) is False
    assert g(("doc-2", "abc")) is False
    assert not g.spent
    assert g(("doc-1", "abc")) is True


@pytest.mark.parametrize("outcome,same", [(GateOutcome.TERMINAL_BREACH, True), (GateOutcome.PASS, False)])
def test_a_refused_decision_cannot_authorize(outcome, same):
    g = guard()
    with pytest.raises(ValueError, match="not a go"):
        g.authorize(decision(door=outcome, same=same))
    assert not g.authorized and g(("doc-1", "abc")) is False


def test_a_decision_with_no_recorded_subject_cannot_authorize():
    _, _, plain = roster()
    plain_decision = plain.decide({"Governance_Gateway:door": "request", "DIT:judge": "text"})
    assert plain_decision.allowed
    g = guard()
    with pytest.raises(ValueError, match="records no subject"):
        g.authorize(plain_decision)


def test_a_decision_whose_root_no_longer_matches_its_verdicts_cannot_authorize():
    import dataclasses
    forged = dataclasses.replace(decision(), root="0" * 64)
    with pytest.raises(ValueError, match="root does not match"):
        guard().authorize(forged)


def test_one_guard_serves_one_decision():
    g = guard()
    g.authorize(decision())
    with pytest.raises(ValueError, match="already authorized"):
        g.authorize(decision())


def test_a_reader_that_raises_or_returns_the_wrong_thing_never_permits():
    def boom(_artifact):
        raise RuntimeError("cannot read")

    for reader in (boom, lambda _a: ("doc-1", "abc"), lambda _a: None):
        g = DecisionGuard(reader)
        g.authorize(decision())
        assert g("anything") is False and not g.spent


def test_the_reader_must_be_callable():
    with pytest.raises(ValueError, match="subject_of"):
        DecisionGuard("not callable")


# ------------------------------------------------- only a SuperGate can issue a decision

import dataclasses  # noqa: E402

from cns_composition.gate_chain import ChainRun  # noqa: E402
from cns_composition.super_gate import Decision  # noqa: E402


def test_a_decision_the_super_gate_issued_says_so():
    assert decision().issued is True


def test_a_decision_copied_field_by_field_is_not_issued_and_cannot_authorize():
    real = decision()
    copy = Decision(run=real.run, seats=real.seats, root=real.root, subject=real.subject)
    assert copy.allowed and not copy.issued
    g = guard()
    with pytest.raises(ValueError, match="not issued"):
        g.authorize(copy)
    assert not g.authorized and g(("doc-1", "abc")) is False


def test_a_decision_with_no_gate_ever_run_is_not_issued():
    from cns.gate import GateResult, subject_digest
    from cns_composition.super_gate import _root
    seats = ("Governance_Gateway:door",)
    results = (GateResult(gate="door", position=A, outcome=GateOutcome.PASS, reason="trust me",
                          subject="door", subject_digest=subject_digest({"x": 1})),)
    run = ChainRun(results=results, outcome=GateOutcome.PASS, omega_ran=True, complete=True)
    made_up = Decision(run=run, seats=seats, root=_root(seats, results), subject=Judged("doc-1", "abc"))
    assert made_up.allowed and not made_up.issued
    with pytest.raises(ValueError, match="not issued"):
        guard().authorize(made_up)


@pytest.mark.parametrize("edit", [
    lambda d: dataclasses.replace(d, subject=Judged("doc-1", "other")),
    lambda d: dataclasses.replace(d, run=dataclasses.replace(d.run, outcome=GateOutcome.TERMINAL_BREACH)),
    lambda d: dataclasses.replace(d, run=dataclasses.replace(d.run, complete=False)),
    lambda d: dataclasses.replace(d, run=dataclasses.replace(d.run, omega_ran=False)),
    lambda d: dataclasses.replace(d, root="0" * 64),
    lambda d: dataclasses.replace(d, proof=""),
])
def test_editing_an_issued_decision_after_issue_voids_the_proof(edit):
    assert decision().issued and not edit(decision()).issued


def test_a_decision_from_a_refused_roster_is_issued_but_still_cannot_authorize():
    refused = decision(door=GateOutcome.TERMINAL_BREACH)
    assert refused.issued and not refused.allowed
    with pytest.raises(ValueError, match="not a go"):
        guard().authorize(refused)


def test_swapping_a_verdict_inside_an_issued_decision_voids_it():
    real = decision()
    swapped = dataclasses.replace(real.run, results=(real.run.results[0],) + real.run.results[:1] + real.run.results[2:])
    assert not dataclasses.replace(real, run=swapped).issued

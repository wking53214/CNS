"""decision_guard: a one-use permission tied to an approved decision and the document it judged."""

import threading

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


# ------------------------------------------------------------ one decision, one action, in time

class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def timed_decision(clock, ttl=None, door=GateOutcome.PASS):
    gate, judge = FakeGate("door", A, door), FakeGate("judge", OM)
    seats = [("Governance_Gateway", gate), ("DIT", judge)]
    given = {DOOR: ("doc-1", "abc"), JUDGE: ("doc-1", "abc")}
    return SuperGate(seats, required=(DOOR, JUDGE, "CNS:same_subject"), same_subject={DOOR: reads, JUDGE: reads},
                     clock=clock).decide(given, ttl=ttl)


def test_one_approval_opens_exactly_one_of_five_fresh_guards():
    approval = decision()
    opened = []
    for _ in range(5):
        g = guard()
        try:
            g.authorize(approval)
            opened.append(g)
        except ValueError as refused:
            assert "already authorized a guard" in str(refused)
            assert not g.authorized and g(("doc-1", "abc")) is False
    assert len(opened) == 1 and opened[0](("doc-1", "abc")) is True


def test_guards_racing_for_one_decision_cannot_both_win():
    approval = decision()
    won, barrier = [], threading.Barrier(16)

    def race():
        g = guard()
        barrier.wait()
        try:
            g.authorize(approval)
            won.append(g)
        except ValueError:
            pass

    threads = [threading.Thread(target=race) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(won) == 1


def test_every_decision_has_its_own_nonce_and_a_new_decision_opens_a_new_guard():
    first, second = decision(), decision()
    assert first.nonce and second.nonce and first.nonce != second.nonce
    guard().authorize(first)
    guard().authorize(second)


def test_the_decision_records_when_it_was_issued_and_when_it_stops_counting():
    clock = Clock(1000.0)
    assert (timed_decision(clock).issued_at, timed_decision(clock).expires_at) == (1000.0, None)
    assert timed_decision(clock, ttl=60).expires_at == 1060.0


def test_an_expired_decision_cannot_authorize_anything():
    clock = Clock(1000.0)
    approval = timed_decision(clock, ttl=60)
    clock.now = 1060.0
    g = DecisionGuard(lambda artifact: Judged(*artifact), clock=clock)
    with pytest.raises(ValueError, match="expired"):
        g.authorize(approval)
    assert not g.authorized


def test_a_decision_one_second_before_it_expires_still_authorizes():
    clock = Clock(1000.0)
    approval = timed_decision(clock, ttl=60)
    clock.now = 1059.0
    g = DecisionGuard(lambda artifact: Judged(*artifact), clock=clock)
    g.authorize(approval)
    assert g(("doc-1", "abc")) is True


def test_a_permission_that_expires_after_authorize_is_refused_and_not_spent():
    clock = Clock(1000.0)
    g = DecisionGuard(lambda artifact: Judged(*artifact), clock=clock)
    g.authorize(timed_decision(clock, ttl=60))
    clock.now = 1061.0
    assert g(("doc-1", "abc")) is False and not g.spent


def test_a_decision_with_no_ttl_does_not_expire():
    clock = Clock(1000.0)
    g = DecisionGuard(lambda artifact: Judged(*artifact), clock=clock)
    g.authorize(timed_decision(clock))
    clock.now = 1e12
    assert g(("doc-1", "abc")) is True


@pytest.mark.parametrize("edit", [
    lambda d: dataclasses.replace(d, nonce="0" * 32),
    lambda d: dataclasses.replace(d, issued_at=d.issued_at + 1),
    lambda d: dataclasses.replace(d, expires_at=9e12),
    lambda d: dataclasses.replace(d, expires_at=None),
])
def test_editing_the_nonce_or_the_times_after_issue_voids_the_proof(edit):
    clock = Clock(1000.0)
    original = timed_decision(clock, ttl=60)
    assert original.issued and not edit(original).issued


@pytest.mark.parametrize("ttl", [0, -1, True, "60", float("nan")])
def test_a_ttl_that_is_not_a_positive_number_is_refused_before_any_gate_runs(ttl):
    gate = FakeGate("door", A)
    seats = [("Governance_Gateway", gate), ("DIT", FakeGate("judge", OM))]
    with pytest.raises(ValueError, match="ttl"):
        SuperGate(seats, required=(DOOR, JUDGE)).decide({DOOR: "a", JUDGE: "b"}, ttl=ttl)
    assert gate.seen == []


def test_a_clock_must_be_a_function():
    with pytest.raises(ValueError, match="clock"):
        DecisionGuard(lambda a: Judged(*a), clock=5)
    with pytest.raises(ValueError, match="clock"):
        SuperGate([("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM))],
                  required=(DOOR, JUDGE), clock="now")


# -- bound to a seat's verdict: the same document is not enough -------------------------------------------------------

from cns.gate import subject_digest  # noqa: E402


def door_binding(candidate):
    """What FakeGate binds its verdict to for `candidate`: the (subject, digest) a guard must check."""
    return "door", subject_digest({"candidate": candidate})


def seat_guard(seat=DOOR, binding_of=door_binding):
    # The document is read from the first two parts, so a candidate can carry a third part that the document
    # check does not see: same source, same text, and a different object.
    return DecisionGuard(lambda artifact: Judged(artifact[0], artifact[1]), seat=seat, binding_of=binding_of)


def test_a_seat_bound_guard_opens_for_the_exact_object_that_seat_judged_and_only_once():
    g = seat_guard()
    g.authorize(decision())
    assert g(("doc-1", "abc")) is True and g.spent
    assert g(("doc-1", "abc")) is False


def test_the_same_document_but_another_object_is_refused_and_does_not_spend_the_permission():
    g = seat_guard()
    g.authorize(decision())
    assert g(("doc-1", "abc", "a different object")) is False
    assert not g.spent
    assert g(("doc-1", "abc")) is True


def test_the_same_guard_without_a_seat_cannot_tell_those_two_objects_apart():
    """The weakness the seat closes, stated as a fact: the document check alone opens for either."""
    g = DecisionGuard(lambda artifact: Judged(artifact[0], artifact[1]))
    g.authorize(decision())
    assert g(("doc-1", "abc", "a different object")) is True


def test_a_binding_reader_that_raises_never_permits():
    def boom(candidate):
        raise RuntimeError("cannot read")
    g = seat_guard(binding_of=boom)
    g.authorize(decision())
    assert g(("doc-1", "abc")) is False and not g.spent


@pytest.mark.parametrize("answer", [None, "door", ("door",), ("door", "x", "y"), ["door", "x"]])
def test_a_binding_reader_that_answers_the_wrong_shape_never_permits(answer):
    g = seat_guard(binding_of=lambda candidate: answer)
    g.authorize(decision())
    assert g(("doc-1", "abc")) is False


def test_a_seat_that_is_not_on_the_roster_cannot_authorize_and_spends_nothing():
    decided = decision()
    g = seat_guard(seat="Conservation_Kernel:root_admission")
    with pytest.raises(ValueError, match="has no seat"):
        g.authorize(decided)
    assert not g.authorized and g(("doc-1", "abc")) is False
    seat_guard().authorize(decided)  # the refusal did not spend the decision's nonce


def test_a_gate_name_two_seats_share_leaves_no_one_verdict_to_bind_to():
    seats = [("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("door", OM))]
    keys = ("Governance_Gateway:door", "DIT:door")
    decided = SuperGate(seats, required=(*keys, "CNS:same_subject"), same_subject={k: reads for k in keys}).decide(
        {k: ("doc-1", "abc") for k in keys})
    assert decided.allowed
    with pytest.raises(ValueError, match="2 verdicts named door"):
        seat_guard(seat="Governance_Gateway:door").authorize(decided)


@pytest.mark.parametrize("kwargs", [{"seat": DOOR}, {"binding_of": door_binding}])
def test_a_seat_and_its_binding_reader_go_together(kwargs):
    with pytest.raises(ValueError, match="go together"):
        DecisionGuard(lambda artifact: Judged(*artifact), **kwargs)


@pytest.mark.parametrize("seat", ["door", ":door", "Governance_Gateway:", 7])
def test_a_seat_must_be_named_as_repository_and_gate(seat):
    with pytest.raises(ValueError, match="repository:gate"):
        DecisionGuard(lambda artifact: Judged(*artifact), seat=seat, binding_of=door_binding)


# -- bound to a roster: a short roster of gates that pass anything cannot open the guard -------------------------------

def guard_requiring(*seats):
    return DecisionGuard(lambda artifact: Judged(*artifact), required_seats=seats)


def test_a_decision_whose_roster_seats_every_required_seat_authorizes():
    g = guard_requiring(DOOR, JUDGE, "CNS:same_subject")
    g.authorize(decision())
    assert g(("doc-1", "abc")) is True


def test_a_decision_from_a_roster_missing_a_required_seat_cannot_authorize_and_spends_nothing():
    decided = decision()
    g = guard_requiring(DOOR, JUDGE, "Conservation_Kernel:root_admission")
    with pytest.raises(ValueError, match="lacks required seat.*Conservation_Kernel:root_admission"):
        g.authorize(decided)
    assert not g.authorized and g(("doc-1", "abc")) is False
    guard_requiring(DOOR).authorize(decided)  # the refusal did not spend the decision's nonce


def test_a_short_roster_that_passes_anything_cannot_open_a_guard_that_requires_the_real_roster():
    weak = SuperGate([("Governance_Gateway", FakeGate("a", A)), ("DIT", FakeGate("o", OM))],
                     required=("Governance_Gateway:a",), same_subject={"Governance_Gateway:a": reads, "DIT:o": reads})
    decided = weak.decide({"Governance_Gateway:a": ("doc-1", "abc"), "DIT:o": ("doc-1", "abc")})
    assert decided.allowed and decided.issued
    with pytest.raises(ValueError, match="lacks required seat"):
        guard_requiring(DOOR, JUDGE, "CNS:same_subject").authorize(decided)


@pytest.mark.parametrize("seats", [("a", "a"), ("",), (7,)])
def test_required_seats_must_be_distinct_non_empty_names(seats):
    with pytest.raises(ValueError, match="required_seats"):
        guard_requiring(*seats)


# -- one use means one yes, even when callers arrive together ---------------------------------------------------------

def test_many_callers_at_once_get_exactly_one_yes_from_a_one_use_permission():
    import time

    def slow_reader(artifact):
        time.sleep(0.002)  # widens the window between "not spent yet" and "spent now"
        return Judged(*artifact)

    for _ in range(20):
        g = DecisionGuard(slow_reader)
        g.authorize(decision())
        answers, ready = [], threading.Barrier(8)

        def knock():
            ready.wait()
            answers.append(g(("doc-1", "abc")))

        threads = [threading.Thread(target=knock) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert answers.count(True) == 1 and g.spent

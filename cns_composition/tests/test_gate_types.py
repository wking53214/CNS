"""gate_types: a roster can say what kind of gate stands behind a seat's name.

A seat's name says which repository and gate it is meant to be, and a roster that reuses the names with other gates
looked identical. `gate_types` maps seats to a predicate the builder supplies (an isinstance check on the real gate class,
for example) and the super gate refuses to be built if a seated gate fails it. A decision records whether every seat was
checked this way (`gate_types_checked`), the proof covers it, and a guard can require it (`require_gate_types`), so a
roster that simply leaves the check out cannot open that guard. It stops substitution by name, not hostile code in the
same process, which can still make an object pass an isinstance check.
"""

import dataclasses

import pytest
from cns.gate import GatePosition

from cns_composition.decision_guard import DecisionGuard
from cns_composition.super_gate import Judged, SuperGate
from cns_composition.tests.test_super_gate import FakeGate, reads

A, OM = GatePosition.ALPHA, GatePosition.OMEGA
DOOR, JUDGE = "Governance_Gateway:door", "DIT:judge"


class RealDoor(FakeGate):
    pass


class RealJudge(FakeGate):
    pass


def roster(door=None, judge=None, **kwargs):
    seats = [("Governance_Gateway", door or RealDoor("door", A)), ("DIT", judge or RealJudge("judge", OM))]
    return SuperGate(seats, required=(DOOR, JUDGE, "CNS:same_subject"), same_subject={DOOR: reads, JUDGE: reads}, **kwargs)


ALL = {DOOR: lambda gate: isinstance(gate, RealDoor), JUDGE: lambda gate: isinstance(gate, RealJudge)}
GIVEN = {DOOR: ("doc-1", "abc"), JUDGE: ("doc-1", "abc")}


def test_a_roster_whose_gates_pass_their_predicates_is_built():
    assert roster(gate_types=ALL).seats == ("CNS:same_subject", DOOR, JUDGE)


def test_a_gate_that_is_not_the_kind_the_seat_names_refuses_the_roster():
    with pytest.raises(ValueError, match=r"Governance_Gateway:door.*not one the roster accepts"):
        roster(door=FakeGate("door", A), gate_types=ALL)


def test_a_predicate_that_raises_or_answers_loosely_never_accepts():
    def boom(gate):
        raise RuntimeError("cannot say")
    for predicate in (boom, lambda g: 1, lambda g: None, lambda g: "yes"):
        with pytest.raises(ValueError, match="not one the roster accepts"):
            roster(gate_types={**ALL, DOOR: predicate})


def test_a_predicate_for_a_seat_that_is_not_on_the_roster_or_that_is_added_by_the_super_gate_is_refused():
    with pytest.raises(ValueError, match="not on the roster"):
        roster(gate_types={**ALL, "Nowhere:gate": lambda g: True})
    with pytest.raises(ValueError, match="not on the roster"):
        roster(gate_types={**ALL, "CNS:same_subject": lambda g: True})


def test_a_predicate_that_is_not_callable_is_refused():
    with pytest.raises(ValueError, match="gate_types"):
        roster(gate_types={**ALL, DOOR: "RealDoor"})


def test_without_gate_types_a_roster_is_built_as_before_and_its_decisions_say_nothing_was_checked():
    plain = roster(door=FakeGate("door", A))
    assert plain.decide(GIVEN).gate_types_checked is False


def test_a_decision_records_that_every_seat_was_checked_only_when_every_seat_was():
    assert roster(gate_types=ALL).decide(GIVEN).gate_types_checked is True
    assert roster(gate_types={DOOR: ALL[DOOR]}).decide(GIVEN).gate_types_checked is False


def test_the_fact_is_covered_by_the_proof_so_it_cannot_be_edited_after_issue():
    unchecked = roster(gate_types={DOOR: ALL[DOOR]}).decide(GIVEN)
    edited = dataclasses.replace(unchecked, gate_types_checked=True)
    assert unchecked.issued and not edited.issued


def guard(**kwargs):
    return DecisionGuard(lambda artifact: Judged(*artifact), **kwargs)


def test_a_guard_that_requires_gate_types_refuses_a_roster_that_left_them_out_and_spends_nothing():
    plain = roster(door=FakeGate("door", A)).decide(GIVEN)
    g = guard(require_gate_types=True)
    with pytest.raises(ValueError, match="gate types"):
        g.authorize(plain)
    partial = roster(gate_types={DOOR: ALL[DOOR]}).decide(GIVEN)
    with pytest.raises(ValueError, match="gate types"):
        g.authorize(partial)
    assert not g.authorized


def test_a_guard_that_requires_gate_types_opens_for_a_roster_that_checked_every_seat():
    g = guard(require_gate_types=True)
    g.authorize(roster(gate_types=ALL).decide(GIVEN))
    assert g(("doc-1", "abc")) is True


def test_a_guard_that_does_not_ask_opens_for_either():
    g = guard()
    g.authorize(roster(door=FakeGate("door", A)).decide(GIVEN))
    assert g(("doc-1", "abc")) is True

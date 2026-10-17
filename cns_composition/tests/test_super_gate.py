"""super_gate: a decision on the whole roster or on none of it."""

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition.super_gate import Decision, MissingCandidate, SuperGate

A, OM = GatePosition.ALPHA, GatePosition.OMEGA
PASS, RETRY, BREACH = GateOutcome.PASS, GateOutcome.RETRY, GateOutcome.TERMINAL_BREACH


class FakeGate:
    """Answers `outcome` for anything. `bind=False` makes it answer without recording what it judged."""

    def __init__(self, name, position, outcome=PASS, bind=True):
        self.name, self.position, self._outcome, self._bind = name, position, outcome, bind
        self.seen = []

    def check(self, candidate):
        self.seen.append(candidate)
        subject = self.name if self._bind else ""
        digest = subject_digest({"candidate": candidate}) if self._bind else ""
        return GateResult(gate=self.name, position=self.position, outcome=self._outcome,
                          reason=f"{self.name} says {self._outcome.value}", subject=subject, subject_digest=digest)


def roster(**kw):
    door = FakeGate("door", A, kw.get("door", PASS), kw.get("door_bind", True))
    judge = FakeGate("judge", OM, kw.get("judge", PASS), kw.get("judge_bind", True))
    return door, judge, SuperGate([("Governance_Gateway", door), ("DIT", judge)])


GOOD = {"Governance_Gateway:door": "request", "DIT:judge": "text"}


# ------------------------------------------------------------ building the roster

def test_an_empty_roster_decides_nothing():
    with pytest.raises(ValueError, match="decides nothing"):
        SuperGate([])


def test_a_gate_at_an_end_its_repository_does_not_declare_is_refused_at_construction():
    with pytest.raises(ValueError, match="DIT declares omega, not alpha"):
        SuperGate([("DIT", FakeGate("judge", A)), ("Governance_Gateway", FakeGate("door", A))])


def test_a_repository_with_no_row_is_refused():
    with pytest.raises(KeyError):
        SuperGate([("Nowhere", FakeGate("g", A))])


def test_a_seat_listed_twice_is_refused():
    with pytest.raises(ValueError, match="appears twice"):
        SuperGate([("Governance_Gateway", FakeGate("door", A)), ("Governance_Gateway", FakeGate("door", A)),
                   ("DIT", FakeGate("judge", OM))])


@pytest.mark.parametrize("seats, missing", [
    ([("Governance_Gateway", FakeGate("door", A))], "omega"),
    ([("DIT", FakeGate("judge", OM))], "alpha"),
])
def test_a_roster_with_only_one_end_is_refused_unless_the_caller_says_it_knows(seats, missing):
    with pytest.raises(ValueError, match=f"no {missing} gate"):
        SuperGate(seats)
    assert SuperGate(seats, require_complete=False).seats


def test_the_seats_are_named_repository_then_gate_in_roster_order():
    _, _, gate = roster()
    assert gate.seats == ("Governance_Gateway:door", "DIT:judge")


# ------------------------------------------------------------ deciding

def test_every_gate_passing_and_binding_is_a_go():
    door, judge, gate = roster()
    decision = gate.decide(GOOD)
    assert decision.allowed and decision.outcome is PASS and decision.reasons() == ()
    assert door.seen == ["request"] and judge.seen == ["text"]


def test_a_seat_with_no_candidate_is_a_breach_and_not_a_skipped_gate():
    door, judge, gate = roster()
    decision = gate.decide({"DIT:judge": "text"})
    assert not decision.allowed and decision.outcome is BREACH
    assert door.seen == [] and judge.seen == []          # alpha refused, so omega never ran
    assert any("MissingCandidate" in line for line in decision.reasons())


def test_a_missing_omega_candidate_is_a_breach_too():
    _, _, gate = roster()
    decision = gate.decide({"Governance_Gateway:door": "request"})
    assert not decision.allowed and decision.outcome is BREACH


def test_a_candidate_for_a_seat_that_is_not_on_the_roster_is_an_error_before_anything_runs():
    door, judge, gate = roster()
    with pytest.raises(ValueError, match="DIT:judg"):
        gate.decide({**GOOD, "DIT:judg": "typo"})
    assert door.seen == [] and judge.seen == []


@pytest.mark.parametrize("kw, outcome", [({"door": RETRY}, RETRY), ({"judge": RETRY}, RETRY),
                                         ({"door": BREACH}, BREACH), ({"judge": BREACH}, BREACH)])
def test_any_gate_that_objects_stops_the_decision(kw, outcome):
    decision = roster(**kw)[2].decide(GOOD)
    assert not decision.allowed and decision.outcome is outcome and decision.reasons()


def test_an_alpha_refusal_means_omega_never_runs_and_says_so():
    _, judge, gate = roster(door=BREACH)
    decision = gate.decide(GOOD)
    assert judge.seen == [] and not decision.run.omega_ran
    assert "the omega gates did not run because an alpha gate refused" in decision.reasons()


@pytest.mark.parametrize("kw", [{"door_bind": False}, {"judge_bind": False}])
def test_a_pass_that_does_not_record_what_it_judged_is_not_a_go(kw):
    decision = roster(**kw)[2].decide(GOOD)
    assert decision.outcome is PASS and not decision.allowed
    assert any("does not record what it judged" in line for line in decision.reasons())


def test_a_gate_that_raises_is_a_breach_and_not_a_pass():
    class Raises(FakeGate):
        def check(self, candidate):
            raise RuntimeError("boom")
    gate = SuperGate([("Governance_Gateway", FakeGate("door", A)), ("DIT", Raises("judge", OM))])
    decision = gate.decide(GOOD)
    assert not decision.allowed and decision.outcome is BREACH


def test_a_roster_the_caller_allowed_to_be_incomplete_never_says_go():
    gate = SuperGate([("Governance_Gateway", FakeGate("door", A))], require_complete=False)
    decision = gate.decide({"Governance_Gateway:door": "request"})
    assert decision.outcome is PASS and not decision.allowed


def test_a_lazy_omega_candidate_is_not_built_when_alpha_refuses():
    from cns_composition.gate_chain import Lazy
    built = []
    _, _, gate = roster(door=BREACH)
    gate.decide({"Governance_Gateway:door": "request", "DIT:judge": Lazy(lambda: built.append(1) or "text")})
    assert built == []


# ------------------------------------------------------------ the root

def test_the_root_is_stable_for_the_same_decision_and_differs_when_anything_differs():
    base = roster()[2].decide(GOOD).root
    assert base == roster()[2].decide(GOOD).root and len(base) == 64
    assert base != roster()[2].decide({**GOOD, "DIT:judge": "other text"}).root       # a candidate changed
    assert base != roster(judge=RETRY)[2].decide(GOOD).root                          # an outcome changed
    other = SuperGate([("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM)),
                       ("GEMS", FakeGate("artifact", OM))])
    assert base != other.decide({**GOOD, "GEMS:artifact": "x"}).root                 # the roster changed


def test_the_root_pins_the_roster_even_when_the_verdicts_are_the_same():
    """An alpha refusal stops omega, so a roster with one more omega gate gives the same verdicts."""
    short = roster(door=BREACH)[2].decide(GOOD)
    longer = SuperGate([("Governance_Gateway", FakeGate("door", A, BREACH)), ("DIT", FakeGate("judge", OM)),
                        ("GEMS", FakeGate("artifact", OM))]).decide({**GOOD, "GEMS:artifact": "x"})
    assert [r.gate for r in short.run.results] == [r.gate for r in longer.run.results]
    assert short.root != longer.root


def test_an_approval_binds_only_the_decision_it_was_issued_for():
    decision = roster()[2].decide(GOOD)
    other = roster()[2].decide({**GOOD, "DIT:judge": "other text"})
    assert decision.binds(decision.root) and not decision.binds(other.root)
    assert not decision.binds("") and isinstance(decision, Decision)


def test_a_missing_candidate_error_names_the_seat():
    assert str(MissingCandidate("DIT:judge")) == "DIT:judge"

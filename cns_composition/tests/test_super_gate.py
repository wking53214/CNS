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
    return door, judge, policy_gate([("Governance_Gateway", door), ("DIT", judge)])


def policy_gate(seats, **kwargs):
    required = tuple(f"{repo}:{gate.name}" for repo, gate in seats)
    return SuperGate(seats, required=required, **kwargs)


GOOD = {"Governance_Gateway:door": "request", "DIT:judge": "text"}


# ------------------------------------------------------------ building the roster

def test_an_empty_roster_decides_nothing():
    with pytest.raises(ValueError, match="decides nothing"):
        policy_gate([])


def test_required_roster_cannot_be_omitted_or_empty():
    seats = [("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM))]
    with pytest.raises(TypeError, match="required"):
        SuperGate(seats)
    with pytest.raises(ValueError, match="at least one"):
        SuperGate(seats, required=())


def test_a_gate_at_an_end_its_repository_does_not_declare_is_refused_at_construction():
    with pytest.raises(ValueError, match="DIT declares omega, not alpha"):
        policy_gate([("DIT", FakeGate("judge", A)), ("Governance_Gateway", FakeGate("door", A))])


def test_a_repository_with_no_row_is_refused():
    with pytest.raises(KeyError):
        policy_gate([("Nowhere", FakeGate("g", A))])


def test_a_seat_listed_twice_is_refused():
    seats = [("Governance_Gateway", FakeGate("door", A)), ("Governance_Gateway", FakeGate("door", A)),
             ("DIT", FakeGate("judge", OM))]
    with pytest.raises(ValueError, match="appears twice"):
        SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge"))


@pytest.mark.parametrize("seats, missing", [
    ([("Governance_Gateway", FakeGate("door", A))], "omega"),
    ([("DIT", FakeGate("judge", OM))], "alpha"),
])
def test_a_roster_with_only_one_end_is_refused_unless_the_caller_says_it_knows(seats, missing):
    with pytest.raises(ValueError, match=f"no {missing} gate"):
        policy_gate(seats)
    assert policy_gate(seats, require_complete=False).seats


def test_the_seats_are_named_repository_then_gate_in_roster_order():
    _, _, gate = roster()
    assert gate.seats == ("Governance_Gateway:door", "DIT:judge")


def test_a_roster_missing_a_required_seat_is_refused_at_construction():
    seats = [("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM))]
    with pytest.raises(ValueError, match="DIT:identity"):
        SuperGate(seats, required=("DIT:identity",))
    assert SuperGate(seats, required=("DIT:judge",)).seats == ("Governance_Gateway:door", "DIT:judge")


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
    gate = policy_gate([("Governance_Gateway", FakeGate("door", A)), ("DIT", Raises("judge", OM))])
    decision = gate.decide(GOOD)
    assert not decision.allowed and decision.outcome is BREACH


def test_a_roster_the_caller_allowed_to_be_incomplete_never_says_go():
    gate = policy_gate([("Governance_Gateway", FakeGate("door", A))], require_complete=False)
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
    other = policy_gate([("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM)),
                       ("GEMS", FakeGate("artifact", OM))])
    assert base != other.decide({**GOOD, "GEMS:artifact": "x"}).root                 # the roster changed


def test_the_root_pins_the_roster_even_when_the_verdicts_are_the_same():
    """An alpha refusal stops omega, so a roster with one more omega gate gives the same verdicts."""
    short = roster(door=BREACH)[2].decide(GOOD)
    longer = policy_gate([("Governance_Gateway", FakeGate("door", A, BREACH)), ("DIT", FakeGate("judge", OM)),
                        ("GEMS", FakeGate("artifact", OM))]).decide({**GOOD, "GEMS:artifact": "x"})
    assert [r.gate for r in short.run.results] == [r.gate for r in longer.run.results]
    assert short.root != longer.root


def test_an_approval_binds_only_the_decision_it_was_issued_for():
    decision = roster()[2].decide(GOOD)
    other = roster()[2].decide({**GOOD, "DIT:judge": "other text"})
    assert decision.binds(decision.root) and not decision.binds(other.root)
    assert not decision.binds("") and isinstance(decision, Decision)


def test_a_decision_binds_only_the_root_recomputed_from_its_own_verdicts():
    real = roster()[2].decide(GOOD)
    forged = Decision(run=real.run, seats=real.seats, root="f" * 64)
    assert real.binds(real.root)
    assert not forged.binds("f" * 64) and not forged.binds(real.root)


def test_a_missing_candidate_error_names_the_seat():
    assert str(MissingCandidate("DIT:judge")) == "DIT:judge"


# ------------------------------------------------------------ the same subject

from cns_composition.gate_chain import Lazy
from cns_composition.super_gate import Judged, SubjectAgreement

SUBJECT = "CNS:same_subject"


def reads(candidate):
    """Candidates in these tests are (identity, digest) pairs."""
    return Judged(*candidate)


def subject_roster(**kw):
    door = FakeGate("door", A)
    judge = FakeGate("judge", OM)
    seats = [("Governance_Gateway", door), ("DIT", judge)]
    both = {"Governance_Gateway:door": reads, "DIT:judge": reads}
    required = ("Governance_Gateway:door", "DIT:judge", SUBJECT)
    return door, judge, SuperGate(seats, required=required, same_subject=kw.get("same_subject", both))


def test_seats_that_read_the_same_subject_are_allowed_and_the_agreement_is_a_bound_seat_of_the_roster():
    _, _, gate = subject_roster()
    assert gate.seats == (SUBJECT, "Governance_Gateway:door", "DIT:judge")
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-1", "abc")})
    assert decision.allowed and decision.outcome is PASS
    agreement = decision.run.results[0]
    assert agreement.gate == "same_subject" and agreement.position is A and agreement.outcome is PASS
    assert agreement.binds("same_subject", subject_digest({"identity": "doc-1", "digest": "abc",
                                                           "seats": ["DIT:judge", "Governance_Gateway:door"]}))
    assert decision.binds(decision.root)


def test_a_different_document_identity_is_refused_at_alpha_and_the_omega_gates_do_not_run():
    door, judge, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-7", "abc")})
    assert not decision.allowed and decision.outcome is BREACH and not decision.run.omega_ran
    assert judge.seen == []
    assert "different subjects" in decision.reasons()[0] and "doc-1" in decision.reasons()[0] and "doc-7" in decision.reasons()[0]


def test_the_same_identity_with_different_content_is_refused():
    _, _, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "412"), "DIT:judge": ("doc-1", "4120")})
    assert not decision.allowed and decision.outcome is BREACH
    assert [r.gate for r in decision.run.blocking()] == ["same_subject"]


def test_a_refusal_for_a_different_subject_is_itself_bound_to_what_each_seat_said():
    _, _, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "a"), "DIT:judge": ("doc-2", "b")})
    refusal = decision.run.results[0]
    assert refusal.bound() and refusal.binds("same_subject", subject_digest(
        {"views": {"Governance_Gateway:door": ["doc-1", "a"], "DIT:judge": ["doc-2", "b"]}}))


def test_a_named_seat_with_no_candidate_is_refused_by_the_comparison_as_well_as_by_the_seat():
    _, _, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc")})
    assert not decision.allowed and decision.outcome is BREACH
    assert any("DIT:judge: has no candidate" in line for line in decision.reasons())


@pytest.mark.parametrize("reader, why", [
    (lambda c: (_ for _ in ()).throw(KeyError("x")), "could not be read (KeyError)"),
    (lambda c: ("doc-1", "abc"), "does not name a document identity"),          # not a Judged
    (lambda c: Judged("", "abc"), "does not name a document identity"),         # nothing named
    (lambda c: Judged("doc-1", ""), "does not name a document identity"),
])
def test_a_seat_that_cannot_be_read_is_a_breach_never_a_skipped_comparison(reader, why):
    _, _, gate = subject_roster(same_subject={"Governance_Gateway:door": reads, "DIT:judge": reader})
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-1", "abc")})
    assert not decision.allowed and decision.outcome is BREACH
    assert any(why in line for line in decision.reasons())


def test_a_lazy_candidate_for_a_named_seat_is_built_once_and_the_gate_judges_what_was_compared():
    door, judge, gate = subject_roster()
    built = []

    def build():
        built.append(1)
        return ("doc-1", "abc")

    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": Lazy(build)})
    assert decision.allowed and len(built) == 1 and judge.seen == [("doc-1", "abc")]


def test_a_lazy_candidate_that_cannot_be_built_is_a_breach_for_the_comparison_and_for_its_own_seat():
    _, judge, gate = subject_roster()

    def build():
        raise RuntimeError("no")

    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": Lazy(build)})
    assert not decision.allowed and decision.outcome is BREACH
    assert decision.run.omega_ran is False and judge.seen == []
    assert any("could not be read (RuntimeError)" in line for line in decision.reasons())


def test_the_agreement_seat_cannot_be_supplied_by_the_caller():
    _, _, gate = subject_roster()
    with pytest.raises(ValueError, match="built by the super gate"):
        gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-1", "abc"), SUBJECT: {}})


def test_same_subject_needs_two_seats_that_are_on_the_roster_and_readable():
    seats = [("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM))]
    required = ("Governance_Gateway:door", "DIT:judge")
    with pytest.raises(ValueError, match="at least two seats"):
        SuperGate(seats, required=required, same_subject={"DIT:judge": reads})
    with pytest.raises(ValueError, match="at least two seats"):
        SuperGate(seats, required=required, same_subject={})
    with pytest.raises(ValueError, match="not on the roster"):
        SuperGate(seats, required=required, same_subject={"DIT:judge": reads, "DIT:other": reads})
    with pytest.raises(ValueError, match="function that reads"):
        SuperGate(seats, required=required, same_subject={"DIT:judge": reads, "Governance_Gateway:door": "doc"})


def test_requiring_the_agreement_seat_means_dropping_same_subject_is_refused_at_construction():
    seats = [("Governance_Gateway", FakeGate("door", A)), ("DIT", FakeGate("judge", OM))]
    with pytest.raises(ValueError, match="lacks required seat.*same_subject"):
        SuperGate(seats, required=("Governance_Gateway:door", "DIT:judge", SUBJECT))


def test_the_agreement_seat_does_not_stand_in_for_a_missing_alpha_gate():
    seats = [("DIT", FakeGate("judge", OM)), ("GEMS", FakeGate("maker", OM))]
    with pytest.raises(ValueError, match="no alpha gate"):
        SuperGate(seats, required=("DIT:judge", "GEMS:maker"), same_subject={"DIT:judge": reads, "GEMS:maker": reads})


def test_the_comparison_gate_alone_refuses_a_candidate_that_is_not_a_reading():
    gate = SubjectAgreement()
    assert gate.check("nothing").outcome is BREACH and gate.check({}).outcome is BREACH


# ------------------------------------------------- the decision remembers the agreed subject

def test_a_passing_decision_records_the_one_subject_the_seats_agreed_on():
    _, _, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-1", "abc")})
    assert decision.allowed and decision.subject == Judged("doc-1", "abc")


def test_a_refused_decision_records_no_subject():
    _, _, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-1", "other")})
    assert not decision.allowed and decision.subject is None


def test_a_roster_without_same_subject_records_no_subject():
    _, _, gate = roster()
    decision = gate.decide(GOOD)
    assert decision.allowed and decision.subject is None


def test_the_recorded_subject_is_the_one_the_agreement_verdict_bound():
    _, _, gate = subject_roster()
    decision = gate.decide({"Governance_Gateway:door": ("doc-1", "abc"), "DIT:judge": ("doc-1", "abc")})
    agreement = decision.run.results[0]
    assert agreement.binds("same_subject", subject_digest({"identity": decision.subject.identity,
                                                           "digest": decision.subject.digest,
                                                           "seats": ["DIT:judge", "Governance_Gateway:door"]}))

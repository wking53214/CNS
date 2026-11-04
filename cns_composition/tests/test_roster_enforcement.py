"""Roster enforcement, adversarially: a complete decision is one the consumer can hold to a roster it set itself.

`SuperGate(required=...)` stops a roster from being built without the seats the caller named. It cannot stop the
same caller from naming fewer. What the party that ACTS on a decision can do is pin the roster it expects, in its own
file, and refuse a decision that lacks one of those seats. These tests are the attacks on that boundary. The expected
roster below is written out by hand and is never built from the gates it is checked against: a roster checked against
itself passes with a gate missing, because whatever is missing is missing from both.

What this does NOT show, stated as assertions where the gap is real: a name on the roster is not the code behind it.
"""

import dataclasses

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition.decision_guard import DecisionGuard
from cns_composition.gate_chain import ChainRun
from cns_composition.super_gate import Decision, Judged, SuperGate, _root

A, OM = GatePosition.ALPHA, GatePosition.OMEGA
PASS, RETRY, BREACH = GateOutcome.PASS, GateOutcome.RETRY, GateOutcome.TERMINAL_BREACH

#: Policy, written by hand, in the file of the party that acts. Deliberately not derived from any seat list below.
EXPECTED = ("Governance_Gateway:door", "DGK:perimeter", "DIT:judge")
DOC = ("doc-1", "true-content")


class Seat:
    def __init__(self, name, position, outcome=PASS):
        self.name, self.position, self._outcome = name, position, outcome

    def check(self, candidate):
        return GateResult(gate=self.name, position=self.position, outcome=self._outcome, reason=self.name,
                          subject=self.name, subject_digest=subject_digest({"candidate": list(candidate)}))


def read(candidate):
    return Judged(*candidate)


def seats_for(*names):
    table = {"door": ("Governance_Gateway", Seat("door", A)), "perimeter": ("DGK", Seat("perimeter", A)),
             "judge": ("DIT", Seat("judge", OM))}
    return [table[n] for n in names]


def keys_for(*names):
    table = {"door": "Governance_Gateway:door", "perimeter": "DGK:perimeter", "judge": "DIT:judge"}
    return {table[n]: DOC for n in names}


def gate_for(*names, required=None, **kw):
    """A SuperGate over the named seats. `required` defaults to the seats themselves, which is the weak setup."""
    seats = seats_for(*names)
    return SuperGate(seats, required=required if required is not None else tuple(keys_for(*names)),
                     same_subject={k: read for k in keys_for(*names)}, **kw)


def full(**kw):
    return gate_for("door", "perimeter", "judge", required=EXPECTED + ("CNS:same_subject",), **kw)


# -------------------------------------------------------------- the roster cannot be built short of what it names

def test_a_whole_mandatory_seat_missing_from_the_submitted_roster_is_refused():
    with pytest.raises(ValueError, match="DGK:perimeter"):
        gate_for("door", "judge", required=EXPECTED)


def test_a_mandatory_seat_with_no_candidate_is_a_breach_and_not_a_skip():
    decision = full().decide({k: v for k, v in keys_for("door", "judge").items()})
    assert decision.outcome is BREACH and not decision.allowed
    assert any("MissingCandidate" in r.reason for r in decision.run.results)


def test_a_seat_submitted_twice_is_refused_however_the_required_list_reads():
    seats = seats_for("door", "perimeter", "judge") + seats_for("perimeter")
    with pytest.raises(ValueError, match="appears twice"):
        SuperGate(seats, required=EXPECTED)


def test_a_gate_that_stands_at_the_other_end_from_its_repository_is_refused():
    wrong = [("Governance_Gateway", Seat("door", A)), ("DGK", Seat("perimeter", OM)), ("DIT", Seat("judge", OM))]
    with pytest.raises(ValueError, match="DGK declares alpha, not omega"):
        SuperGate(wrong, required=EXPECTED)


def test_an_empty_roster_and_an_empty_required_list_are_each_refused():
    with pytest.raises(ValueError, match="decides nothing"):
        SuperGate([], required=EXPECTED)
    with pytest.raises(ValueError, match="at least one"):
        SuperGate(seats_for("door", "judge"), required=())


def test_reordering_the_seats_keeps_every_gate_and_moves_the_root():
    one = SuperGate(seats_for("door", "perimeter", "judge"), required=EXPECTED)
    two = SuperGate(seats_for("perimeter", "door", "judge"), required=EXPECTED)
    d1, d2 = one.decide(keys_for("door", "perimeter", "judge")), two.decide(keys_for("door", "perimeter", "judge"))
    assert d1.allowed and d2.allowed
    assert set(d1.seats) == set(d2.seats) and d1.seats != d2.seats
    assert d1.root != d2.root


def test_the_required_list_and_seat_list_handed_in_cannot_be_edited_into_a_weaker_roster_afterwards():
    seats, required = seats_for("door", "perimeter", "judge"), list(EXPECTED)
    gate = SuperGate(seats, required=required)
    seats.pop(1)
    required.pop(1)
    decision = gate.decide(keys_for("door", "perimeter", "judge"))
    assert gate.seats == EXPECTED and decision.seats == EXPECTED and decision.allowed
    assert gate.decide(keys_for("door", "judge")).outcome is BREACH


# ------------------------------------------- the party that acts holds the decision to a roster it set itself

def weak_decision():
    """The caller being judged builds a SMALLER roster and a matching `required`; every check it chose passes."""
    gate = gate_for("door", "judge", required=("Governance_Gateway:door", "DIT:judge", "CNS:same_subject"))
    decision = gate.decide(keys_for("door", "judge"))
    assert decision.allowed and decision.issued and decision.subject == Judged(*DOC)
    return decision


def test_a_caller_supplied_weaker_roster_is_refused_by_a_guard_that_pins_the_expected_roster():
    guard = DecisionGuard(read, expected_seats=EXPECTED + ("CNS:same_subject",))
    with pytest.raises(ValueError, match="DGK:perimeter"):
        guard.authorize(weak_decision())
    assert not guard.authorized and guard(DOC) is False


def test_the_same_weaker_decision_opens_a_guard_that_does_not_pin_a_roster_which_is_why_pinning_exists():
    guard = DecisionGuard(read)
    guard.authorize(weak_decision())
    assert guard.authorized and guard.expected_seats is None


def test_a_guard_pinned_to_the_roster_accepts_the_full_roster_once():
    decision = full().decide(keys_for("door", "perimeter", "judge"))
    guard = DecisionGuard(read, expected_seats=EXPECTED)
    guard.authorize(decision)
    assert guard(DOC) is True and guard(DOC) is False
    assert guard.expected_seats == EXPECTED


def test_a_refusal_for_a_missing_seat_does_not_spend_the_decision():
    decision = full().decide(keys_for("door", "perimeter", "judge"))
    with pytest.raises(ValueError, match="DIT:other"):
        DecisionGuard(read, expected_seats=EXPECTED + ("DIT:other",)).authorize(decision)
    ok = DecisionGuard(read, expected_seats=EXPECTED)
    ok.authorize(decision)
    assert ok.authorized


def test_seats_beyond_the_expected_roster_do_not_weaken_it():
    decision = full().decide(keys_for("door", "perimeter", "judge"))
    guard = DecisionGuard(read, expected_seats=("Governance_Gateway:door", "DIT:judge"))
    guard.authorize(decision)
    assert guard.authorized


@pytest.mark.parametrize("bad", [(), [], ("",), ("a:b", "a:b"), (3,), "Governance_Gateway:door"])
def test_an_expected_roster_that_is_empty_or_malformed_is_refused_at_construction(bad):
    with pytest.raises(ValueError):
        DecisionGuard(read, expected_seats=bad)


# --------------------------------------- a verdict for every seat: `allowed` does not rest on the stored fields alone

def test_a_decision_with_no_verdict_for_one_of_its_seats_is_not_allowed():
    decision = full().decide(keys_for("door", "perimeter", "judge"))
    kept = tuple(r for r in decision.run.results if r.gate != "perimeter")
    stripped = dataclasses.replace(decision, run=dataclasses.replace(decision.run, results=kept),
                                   root=_root(decision.seats, kept))
    assert stripped.binds(stripped.root), "the root was recomputed over what is left, so it binds"
    assert not stripped.issued
    assert not stripped.allowed
    assert any("do not match" in line for line in stripped.reasons())


def test_a_verdict_for_a_gate_that_is_not_a_seat_is_not_allowed():
    decision = full().decide(keys_for("door", "perimeter", "judge"))
    extra = decision.run.results + (GateResult(gate="rubber_stamp", position=OM, outcome=PASS, reason="x",
                                               subject="s", subject_digest=subject_digest({"k": 1})),)
    padded = dataclasses.replace(decision, run=dataclasses.replace(decision.run, results=extra),
                                 root=_root(decision.seats, extra))
    assert not padded.allowed


def test_an_untouched_issued_decision_is_still_allowed_with_a_verdict_per_seat():
    decision = full().decide(keys_for("door", "perimeter", "judge"))
    assert len(decision.run.results) == len(decision.seats) and decision.allowed and decision.issued


# ------------------------------------------------------------------ a partial assessment is not a complete decision

def partial():
    seats = seats_for("door", "perimeter")
    gate = SuperGate(seats, required=("Governance_Gateway:door", "DGK:perimeter"), require_complete=False)
    return gate.decide(keys_for("door", "perimeter"))


def test_a_deliberately_partial_assessment_runs_and_is_visibly_not_a_decision():
    decision = partial()
    assert decision.outcome is PASS, "every gate it holds passed"
    assert decision.run.complete is False
    assert decision.allowed is False


def test_a_partial_assessment_says_why_it_is_not_a_go():
    assert any("partial" in line for line in partial().reasons())


def test_a_partial_assessment_cannot_open_a_guard_even_one_that_pins_exactly_its_seats():
    guard = DecisionGuard(read, expected_seats=("Governance_Gateway:door", "DGK:perimeter"))
    with pytest.raises(ValueError, match="partial"):
        guard.authorize(partial())


def test_calling_a_partial_assessment_complete_by_hand_voids_its_proof():
    decision = partial()
    claimed = dataclasses.replace(decision, run=dataclasses.replace(decision.run, complete=True, omega_ran=True))
    assert not claimed.issued
    guard = DecisionGuard(read)
    with pytest.raises(ValueError):
        guard.authorize(claimed)


def test_a_hand_built_decision_that_claims_a_full_roster_it_never_ran_is_not_issued():
    seats = EXPECTED
    results = tuple(GateResult(gate=s.split(":")[1], position=A if s != "DIT:judge" else OM, outcome=PASS,
                               reason="trust me", subject="s", subject_digest=subject_digest({"k": s}))
                    for s in seats)
    run = ChainRun(results=results, outcome=PASS, omega_ran=True, complete=True)
    made = Decision(run=run, seats=seats, root=_root(seats, results), subject=Judged(*DOC))
    assert made.allowed and not made.issued
    with pytest.raises(ValueError, match="not issued"):
        DecisionGuard(read, expected_seats=EXPECTED).authorize(made)


# --------------------------------------------------------- the decision is for one context, and says which

CTX = {"action": "ingest", "tenant": "t-1", "policy": "2026-11-01"}


def decided_in(context):
    return full().decide(keys_for("door", "perimeter", "judge"), context=context)


def test_a_decision_made_for_one_context_cannot_open_a_guard_for_another():
    decision = decided_in(CTX)
    with pytest.raises(ValueError, match="context"):
        DecisionGuard(read, expected_context={**CTX, "action": "delete"}).authorize(decision)
    with pytest.raises(ValueError, match="context"):
        DecisionGuard(read, expected_context={**CTX, "tenant": "t-2"}).authorize(decision)


def test_a_decision_made_for_the_expected_context_opens_the_guard():
    guard = DecisionGuard(read, expected_context=dict(reversed(list(CTX.items()))))
    guard.authorize(decided_in(CTX))
    assert guard(DOC) is True


def test_a_decision_with_no_context_cannot_open_a_guard_that_requires_one():
    with pytest.raises(ValueError, match="context"):
        DecisionGuard(read, expected_context=CTX).authorize(decided_in(None))


def test_a_context_the_guard_did_not_ask_for_does_not_stop_it():
    guard = DecisionGuard(read)
    guard.authorize(decided_in(CTX))
    assert guard.authorized


def test_the_context_is_in_the_root_only_when_given_so_every_existing_root_is_unchanged():
    plain, with_ctx = decided_in(None), decided_in(CTX)
    legacy = subject_digest({"seats": list(plain.seats), "verdicts": [
        {"gate": r.gate, "position": r.position.value, "outcome": r.outcome.value, "subject": r.subject,
         "digest": r.subject_digest} for r in plain.run.results]})
    assert plain.root == legacy and plain.context_digest == ""
    assert with_ctx.root != plain.root and with_ctx.context_digest == subject_digest(CTX)
    assert with_ctx.binds(with_ctx.root) and not with_ctx.binds(plain.root)


def test_editing_the_context_after_issue_voids_the_proof_and_the_root():
    decision = decided_in(CTX)
    moved = dataclasses.replace(decision, context_digest=subject_digest({**CTX, "action": "delete"}))
    assert not moved.issued and not moved.binds(moved.root)
    cleared = dataclasses.replace(decision, context_digest="")
    assert not cleared.issued and not cleared.binds(cleared.root)


@pytest.mark.parametrize("bad", [{}, {"": "x"}, {"a": ""}, {"a": 1}, ["a"], "tenant"])
def test_a_context_that_binds_nothing_or_is_malformed_is_refused_before_any_gate_runs(bad):
    gate = full()
    with pytest.raises(ValueError, match="context"):
        gate.decide(keys_for("door", "perimeter", "judge"), context=bad)


def test_the_expected_context_must_be_well_formed_at_construction():
    with pytest.raises(ValueError, match="context"):
        DecisionGuard(read, expected_context={})


# ------------------------------------------------------------ what this layer cannot do, stated so it cannot rot

def test_GAP_a_lenient_gate_under_a_required_name_is_a_full_roster_because_a_roster_names_seats_and_not_code():
    """The roster binds the NAME of a seat. The code that fills it is whatever the process loaded. Closing this takes
    a package pin and an install the caller cannot replace, which is the deployment's, not this layer's."""
    class Lenient:
        def __init__(self, name, position):
            self.name, self.position = name, position

        def check(self, candidate):
            return GateResult(gate=self.name, position=self.position, outcome=PASS, reason="always",
                              subject=self.name, subject_digest=subject_digest({"k": "constant"}))

    swapped = [("Governance_Gateway", Lenient("door", A)), ("DGK", Lenient("perimeter", A)),
               ("DIT", Lenient("judge", OM))]
    decision = SuperGate(swapped, required=EXPECTED + ("CNS:same_subject",),
                         same_subject={k: read for k in EXPECTED}).decide(keys_for("door", "perimeter", "judge"))
    assert decision.allowed and decision.issued
    guard = DecisionGuard(read, expected_seats=EXPECTED)
    guard.authorize(decision)
    assert guard.authorized, "pinning names does not pin code; this opens, and that is the recorded limit"


def test_GAP_equal_inputs_give_equal_roots_so_a_root_is_what_was_decided_and_not_when():
    one = full().decide(keys_for("door", "perimeter", "judge"))
    two = full().decide(keys_for("door", "perimeter", "judge"))
    assert one.root == two.root and one.nonce != two.nonce

"""The chain runner and the roster refuse a verdict that is not a GateOutcome, an empty decision, and a partial run."""

import dataclasses

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition.gate_chain import ChainRun, run_chain
from cns_composition.repo_gates import run_repo_chain
from cns_composition.super_gate import Decision, SuperGate

A, OM = GatePosition.ALPHA, GatePosition.OMEGA
PASS = GateOutcome.PASS


class Gate:
    def __init__(self, name, position, outcome=PASS):
        self.name, self.position, self._outcome = name, position, outcome

    def check(self, candidate):
        return GateResult(gate=self.name, position=self.position, outcome=self._outcome, reason="r",
                          subject=self.name, subject_digest=subject_digest({"c": str(candidate)}))


@pytest.mark.parametrize("odd", ["terminal_breach", "pass", None, 7])
def test_run_chain_turns_a_verdict_that_is_not_an_outcome_into_a_breach_naming_the_gate(odd):
    run = run_chain([(Gate("door", A, odd), "x")], [(Gate("judge", OM), "y")])
    assert run.outcome is GateOutcome.TERMINAL_BREACH and not run.omega_ran
    assert "not a GateOutcome" in run.results[0].reason and not run.results[0].bound()


def test_run_repo_chain_does_the_same():
    run = run_repo_chain([("Governance_Gateway", Gate("door", A, "terminal_breach"), "x"),
                          ("DIT", Gate("judge", OM), "y")])
    assert run.outcome is GateOutcome.TERMINAL_BREACH


def test_a_super_gate_decision_with_such_a_gate_is_not_allowed_and_does_not_crash():
    gate = SuperGate([("Governance_Gateway", Gate("door", A, "terminal_breach")), ("DIT", Gate("judge", OM))],
                     required=("Governance_Gateway:door", "DIT:judge"))
    decision = gate.decide({"Governance_Gateway:door": "x", "DIT:judge": "y"})
    assert decision.outcome is GateOutcome.TERMINAL_BREACH and not decision.allowed and decision.issued


def test_a_decision_with_no_seats_and_no_verdicts_is_not_allowed_however_it_is_flagged():
    empty = Decision(run=ChainRun(results=(), outcome=PASS, omega_ran=True, complete=True), seats=(), root="")
    assert not empty.allowed
    assert empty.reasons(), "and it says why"


def test_a_decision_with_seats_and_no_verdicts_is_not_allowed():
    real = SuperGate([("Governance_Gateway", Gate("door", A)), ("DIT", Gate("judge", OM))],
                     required=("Governance_Gateway:door", "DIT:judge")
                     ).decide({"Governance_Gateway:door": "x", "DIT:judge": "y"})
    hollow = dataclasses.replace(real, run=dataclasses.replace(real.run, results=()))
    assert not hollow.allowed


def test_a_partial_decision_says_so_and_a_complete_one_does_not():
    seats = [("Governance_Gateway", Gate("door", A))]
    partial = SuperGate(seats, required=("Governance_Gateway:door",), require_complete=False
                        ).decide({"Governance_Gateway:door": "x"})
    full = SuperGate(seats + [("DIT", Gate("judge", OM))], required=("Governance_Gateway:door", "DIT:judge")
                     ).decide({"Governance_Gateway:door": "x", "DIT:judge": "y"})
    assert partial.partial is True and partial.outcome is PASS and not partial.allowed
    assert full.partial is False and full.allowed

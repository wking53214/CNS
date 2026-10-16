"""run_chain: the gates of a chain run on real candidates and resolve fail-closed.

The gates here are small stand-ins that satisfy ``cns.gate.Gate``. CNS imports no repository, so the
repositories' own gates are exercised by their own suites and, together, by the live check recorded
in the commit that added this module.
"""

import pytest
from cns.gate import Gate, GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition.gate_chain import ChainRun, Lazy, run_chain

A, O = GatePosition.ALPHA, GatePosition.OMEGA
PASS, RETRY, BREACH = GateOutcome.PASS, GateOutcome.RETRY, GateOutcome.TERMINAL_BREACH


class FakeGate:
    """Answers `outcome` for anything, and counts what it was asked."""

    def __init__(self, name, position, outcome=PASS, *, answer_position=None, bound=True):
        self.name, self.position = name, position
        self._outcome, self._answer_position, self._bound = outcome, answer_position, bound
        self.seen = []

    def check(self, candidate):
        self.seen.append(candidate)
        content = {"candidate": candidate}
        return GateResult(
            gate=self.name, position=self._answer_position or self.position, outcome=self._outcome,
            reason=f"{self.name} says {self._outcome.value}",
            subject="x" if self._bound else "", subject_digest=subject_digest(content) if self._bound else "")


class Raises:
    name, position = "boom", A

    def check(self, candidate):
        raise RuntimeError("secret detail that must not be echoed")


class ReturnsJunk:
    def __init__(self, value):
        self.name, self.position, self._value = "junk", O, value

    def check(self, candidate):
        return self._value


def test_the_stand_ins_satisfy_the_gate_protocol():
    assert isinstance(FakeGate("g", A), Gate)


def test_a_clean_chain_runs_alpha_then_omega_and_passes():
    a1, a2, o = FakeGate("a1", A), FakeGate("a2", A), FakeGate("o", O)
    run = run_chain([(a1, 1), (a2, 2)], [(o, 3)])
    assert isinstance(run, ChainRun)
    assert [r.gate for r in run.results] == ["a1", "a2", "o"]
    assert run.outcome is PASS and run.omega_ran and run.complete
    assert run.unbound() == () and run.blocking() == ()
    assert (a1.seen, a2.seen, o.seen) == ([1], [2], [3])


def test_an_alpha_breach_means_omega_never_runs():
    o = FakeGate("o", O)
    run = run_chain([(FakeGate("a", A, BREACH), 1)], [(o, 2)])
    assert run.outcome is BREACH and not run.omega_ran and o.seen == []
    assert [r.gate for r in run.blocking()] == ["a"]


def test_an_alpha_retry_also_stops_the_work():
    o = FakeGate("o", O)
    run = run_chain([(FakeGate("a", A, RETRY), 1)], [(o, 2)])
    assert run.outcome is RETRY and not run.omega_ran and o.seen == []


def test_a_later_breach_is_not_hidden_behind_an_earlier_retry():
    first, second = FakeGate("first", A, RETRY), FakeGate("second", A, BREACH)
    run = run_chain([(first, 1), (second, 2)], [(FakeGate("o", O), 3)])
    assert first.seen == [1] and second.seen == [2]
    assert run.outcome is BREACH and len(run.results) == 2


def test_an_omega_verdict_decides_after_alpha_passes():
    assert run_chain([(FakeGate("a", A), 1)], [(FakeGate("o", O, BREACH), 2)]).outcome is BREACH
    assert run_chain([(FakeGate("a", A), 1)], [(FakeGate("o", O, RETRY), 2)]).outcome is RETRY


def test_the_same_gate_may_judge_many_candidates():
    g = FakeGate("finding", A)
    run = run_chain([(g, "f1"), (g, "f2"), (g, "f3")], [(FakeGate("o", O), 0)])
    assert g.seen == ["f1", "f2", "f3"] and len(run.results) == 4 and run.outcome is PASS


def test_a_lazy_candidate_is_built_only_when_its_turn_comes():
    built = []
    lazy = Lazy(lambda: built.append(1) or "made")
    o = FakeGate("o", O)
    refused = run_chain([(FakeGate("a", A, BREACH), 1)], [(o, lazy)])
    assert built == [] and not refused.omega_ran
    ok = run_chain([(FakeGate("a", A), 1)], [(o, lazy)])
    assert built == [1] and o.seen == ["made"] and ok.outcome is PASS


def test_a_lazy_candidate_that_cannot_be_built_is_a_recorded_breach():
    def fail():
        raise OSError("disk detail")

    run = run_chain([(FakeGate("a", A), 1)], [(FakeGate("o", O), Lazy(fail))])
    assert run.outcome is BREACH and "OSError" in run.results[-1].reason
    assert "disk detail" not in run.results[-1].reason


def test_a_gate_that_raises_is_a_breach_naming_it_and_not_an_exception():
    run = run_chain([(Raises(), 1)], [(FakeGate("o", O), 2)])
    only = run.results[0]
    assert only.gate == "boom" and only.outcome is BREACH and not only.bound()
    assert "RuntimeError" in only.reason and "secret detail" not in only.reason
    assert run.outcome is BREACH and not run.omega_ran


@pytest.mark.parametrize("junk", [None, "pass", 1, {"outcome": "pass"}, True])
def test_a_gate_that_returns_something_else_is_a_breach(junk):
    run = run_chain([(FakeGate("a", A), 1)], [(ReturnsJunk(junk), 2)])
    assert run.outcome is BREACH and "not a GateResult" in run.results[-1].reason
    assert not run.results[-1].bound()


def test_a_gate_that_answers_at_the_wrong_end_is_a_breach():
    run = run_chain([(FakeGate("a", A, answer_position=O), 1)], [(FakeGate("o", O), 2)])
    assert run.outcome is BREACH and "wrong end" in run.results[0].reason


def test_a_gate_in_the_wrong_slot_is_refused_before_anything_runs():
    misplaced, other = FakeGate("late", O), FakeGate("a", A)
    with pytest.raises(ValueError, match="wrong slot"):
        run_chain([(other, 1), (misplaced, 2)], [(FakeGate("o", O), 3)])
    assert other.seen == [] and misplaced.seen == []


def test_an_empty_chain_is_refused():
    with pytest.raises(ValueError, match="no gates"):
        run_chain([], [], require_complete=False)
    with pytest.raises(ValueError):
        run_chain()


@pytest.mark.parametrize("alpha,omega,missing", [
    ([(FakeGate("a", A), 1)], [], "omega"),
    ([], [(FakeGate("o", O), 1)], "alpha")])
def test_a_one_ended_chain_is_refused_unless_the_caller_says_so(alpha, omega, missing):
    with pytest.raises(ValueError, match=f"no {missing} gate"):
        run_chain(alpha, omega)


def test_a_one_ended_chain_can_run_when_allowed_and_says_it_is_incomplete():
    run = run_chain([], [(FakeGate("o", O), 1)], require_complete=False)
    assert run.outcome is PASS and run.complete is False and run.omega_ran


def test_unbound_verdicts_are_reported_not_hidden():
    run = run_chain([(FakeGate("a", A, bound=False), 1)], [(FakeGate("o", O), 2)])
    assert run.outcome is PASS and run.unbound() == ("a",)


def test_a_pass_requires_that_nothing_objected_anywhere():
    gates = [(FakeGate(f"a{i}", A), i) for i in range(5)]
    assert run_chain(gates, [(FakeGate("o", O), 9)]).outcome is PASS
    gates[3] = (FakeGate("a3", A, RETRY), 3)
    assert run_chain(gates, [(FakeGate("o", O), 9)]).outcome is RETRY

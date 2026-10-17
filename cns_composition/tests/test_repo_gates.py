"""repo_gates: a repository's gate stands only at the ends the repository declares."""

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from cns_composition import repo_gates
from cns_composition.repo_gates import ENDS, Lazy, ends_of, run_repo_chain

A, O = GatePosition.ALPHA, GatePosition.OMEGA
PASS, RETRY, BREACH = GateOutcome.PASS, GateOutcome.RETRY, GateOutcome.TERMINAL_BREACH


class FakeGate:
    """Stands in for a repository's gate: answers `outcome` for anything and counts what it was asked."""

    def __init__(self, name, position, outcome=PASS, answer_position=None):
        self.name, self.position = name, position
        self._outcome, self._answer = outcome, answer_position
        self.seen = []

    def check(self, candidate):
        self.seen.append(candidate)
        return GateResult(gate=self.name, position=self._answer or self.position, outcome=self._outcome,
                          reason=f"{self.name} says {self._outcome.value}", subject=self.name,
                          subject_digest=subject_digest({"candidate": candidate}))


def test_every_row_names_a_nonempty_set_of_real_ends():
    assert ENDS and all(ends and ends <= {A, O} for ends in ENDS.values())


def test_the_doors_stand_at_alpha_the_judges_at_omega_and_two_repos_have_both():
    assert ends_of("Governance_Gateway") == {A}
    assert ends_of("DIT") == {O} and ends_of("GEMS") == {O}
    assert ends_of("Conservation_Kernel") == {A, O} and ends_of("fortress-kernel") == {A, O}
    assert ends_of("PERCEIVE") == {A, O} and ends_of("HERALD") == {A, O}


def test_an_unknown_repository_has_no_ends():
    with pytest.raises(KeyError, match="add its row first"):
        ends_of("Nowhere")


def test_a_door_and_a_judge_from_two_repositories_make_a_complete_chain():
    door, judge = FakeGate("gateway", A), FakeGate("dit", O)
    run = run_repo_chain([("Governance_Gateway", door, {"id": 1}), ("DIT", judge, "text")])
    assert run.outcome is PASS and run.complete and run.omega_ran
    assert [r.gate for r in run.results] == ["gateway", "dit"]
    assert door.seen == [{"id": 1}] and judge.seen == ["text"]


def test_steps_given_out_of_order_still_run_alpha_first():
    door, judge = FakeGate("gateway", A), FakeGate("dit", O)
    run = run_repo_chain([("DIT", judge, "t"), ("Governance_Gateway", door, "c")])
    assert [r.gate for r in run.results] == ["gateway", "dit"]


def test_a_gate_that_moved_to_an_end_its_repository_does_not_declare_is_refused_before_anything_runs():
    door, moved = FakeGate("gateway", A), FakeGate("dit", A)
    with pytest.raises(ValueError, match=r"dit \(DIT declares omega, not alpha\)"):
        run_repo_chain([("Governance_Gateway", door, "c"), ("DIT", moved, "t")])
    assert door.seen == [] and moved.seen == []


def test_a_door_filed_as_a_judge_is_refused_and_every_wrong_gate_is_named_at_once():
    bad_door, bad_judge = FakeGate("gateway", O), FakeGate("gems", A)
    with pytest.raises(ValueError) as caught:
        run_repo_chain([("Governance_Gateway", bad_door, 1), ("GEMS", bad_judge, 2)])
    text = str(caught.value)
    assert "gateway (Governance_Gateway declares alpha, not omega)" in text
    assert "gems (GEMS declares omega, not alpha)" in text


@pytest.mark.parametrize("repo", ["Conservation_Kernel", "fortress-kernel", "PERCEIVE", "HERALD"])
def test_a_repository_with_both_ends_may_seat_a_gate_at_each(repo):
    low, high = FakeGate("low", A), FakeGate("high", O)
    run = run_repo_chain([(repo, low, 1), (repo, high, 2)])
    assert run.complete and run.outcome is PASS


def test_an_unknown_repository_is_refused_before_anything_runs():
    known = FakeGate("dit", O)
    with pytest.raises(KeyError):
        run_repo_chain([("DIT", known, "t"), ("Nowhere", FakeGate("x", A), "c")])
    assert known.seen == []


def test_a_refusing_alpha_gate_stops_the_omega_gate_from_running():
    door, judge = FakeGate("gateway", A, BREACH), FakeGate("dit", O)
    run = run_repo_chain([("Governance_Gateway", door, "c"), ("DIT", judge, "t")])
    assert run.outcome is BREACH and not run.omega_ran and judge.seen == []


def test_a_lazy_candidate_is_not_built_when_alpha_already_refused():
    built = []
    door = FakeGate("gateway", A, RETRY)
    run = run_repo_chain([("Governance_Gateway", door, "c"),
                          ("DIT", FakeGate("dit", O), Lazy(lambda: built.append(1) or "t"))])
    assert run.outcome is RETRY and built == []


def test_a_chain_with_one_end_is_refused_unless_the_caller_says_so():
    with pytest.raises(ValueError, match="stratum"):
        run_repo_chain([("DIT", FakeGate("dit", O), "t")])
    assert run_repo_chain([("DIT", FakeGate("dit", O), "t")], require_complete=False).outcome is PASS


def test_a_gate_that_answers_at_the_wrong_end_is_still_a_breach():
    liar = FakeGate("gateway", A, answer_position=O)
    run = run_repo_chain([("Governance_Gateway", liar, "c"), ("DIT", FakeGate("dit", O), "t")])
    assert run.outcome is BREACH and "wrong end" in run.results[0].reason


def test_the_module_imports_no_repository():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(repo_gates))
    roots = {n.module.split(".")[0] if isinstance(n, ast.ImportFrom) and n.module else a.name.split(".")[0]
             for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in getattr(n, "names", [None])
             if not (isinstance(n, ast.ImportFrom) and n.level)}
    assert roots <= {"__future__", "typing", "cns"}

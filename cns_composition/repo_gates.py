"""repo_gates: seat the gates that repositories ship at the ends they promise, then run the chain.

WHY THIS EXISTS

Each repository that connects to CNS ships a gate and says, in its own connector, which end of a decision it
belongs to: the Governance_Gateway is an admission door (ALPHA), DIT judges text on its way out (OMEGA),
Conservation_Kernel and fortress-kernel have a gate at each end, PERCEIVE lets the caller choose. `run_chain`
runs any gates it is given, and it already refuses a gate whose own `position` disagrees with its slot. What
it cannot know is what a repository PROMISED. A gate that quietly moves to the other end in a later release
still agrees with itself, and a chain built from it is wrong without any check noticing.

This module holds the promise, one row per repository, and refuses to seat a gate at an end its repository
does not declare. It is the CNS side of the connection: CNS imports no repository (the gates are handed in),
and it is the only place that says which repository's gate may stand where.

WHAT IT DOES NOT DO

It does not judge anything. The verdicts are the gates' own, bound by them with `cns.gate.subject_digest`.
It does not know a gate's name: a repository may name its gates as it likes. It adds one thing to `run_chain`,
which is that every gate is attributed to a repository and checked against that repository's declared ends.

KEEPING THE TABLE TRUE

The ends below are read from each repository's connector. When a repository changes its gate's end, this row
and that repository's connector change in the same breath, or this module refuses the gate. That refusal is
the point.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Mapping, Tuple

from cns.gate import Gate, GatePosition

from .gate_chain import ChainRun, Lazy, run_chain  # Lazy is re-exported for callers

__all__ = ["ENDS", "Lazy", "ends_of", "run_repo_chain"]

_A, _O = GatePosition.ALPHA, GatePosition.OMEGA

#: repository -> the ends its gate(s) may stand at, from its own connector.
ENDS: Mapping[str, FrozenSet[GatePosition]] = {
    "Governance_Gateway": frozenset({_A}),        # the admission door
    "DIT": frozenset({_O}),                       # judges text on its way out
    "GEMS": frozenset({_O}),                      # judges an artifact it produced
    "Conservation_Kernel": frozenset({_A, _O}),   # root admission at ALPHA, a transformation at OMEGA
    "fortress-kernel": frozenset({_A, _O}),       # numeric_safety and mandate at ALPHA, invariants and audit_chain at OMEGA
    "PERCEIVE": frozenset({_A, _O}),              # the caller picks the end
}

#: A step: the repository the gate came from, the gate, and the candidate it judges.
Step = Tuple[str, Gate, object]


def ends_of(repo: str) -> FrozenSet[GatePosition]:
    """The ends `repo`'s gate may stand at. Raises KeyError for a repository this module does not know."""
    try:
        return ENDS[repo]
    except KeyError:
        raise KeyError(f"{repo!r} has no declared gate ends in repo_gates; add its row first") from None


def run_repo_chain(steps: Iterable[Step], *, require_complete: bool = True) -> ChainRun:
    """Run a chain of gates from named repositories, refusing any gate its repository does not declare.

    Raises ValueError, before anything runs, for a gate that stands at an end its repository does not
    declare, and KeyError for a repository with no row. Otherwise it is `run_chain`: ALPHA gates first,
    OMEGA only if every ALPHA passed.
    """
    alpha: List[Tuple[Gate, object]] = []
    omega: List[Tuple[Gate, object]] = []
    wrong: Dict[str, str] = {}
    for repo, gate, candidate in steps:
        allowed = ends_of(repo)
        position = gate.position
        if position not in allowed:
            wrong[getattr(gate, "name", "") or type(gate).__name__] = (
                f"{repo} declares {'/'.join(sorted(p.value for p in allowed))}, not {position.value}")
            continue
        (alpha if position is _A else omega).append((gate, candidate))
    if wrong:
        raise ValueError("gate(s) at an end their repository does not declare, refusing to run: "
                         + "; ".join(f"{name} ({why})" for name, why in sorted(wrong.items())))
    return run_chain(alpha, omega, require_complete=require_complete)


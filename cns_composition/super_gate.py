"""super_gate: the one place that says go.

WHY THIS EXISTS

`run_repo_chain` runs the gates it is given. That leaves two ways for a decision to go through with a gate
missing: the caller never put the gate in the chain, or put it in and never handed it a candidate. A caller
that wants a decision from "all the gates" has to remember all of them, every time. This module holds the
roster once. A `SuperGate` is built from named repository gates, refuses at construction any gate its
repository does not declare at that end, and from then on a decision is made on the whole roster or not at
all:

  A seat with no candidate is a TERMINAL_BREACH, not a skipped gate. A caller cannot leave a gate out of a
    decision by leaving its candidate out. A candidate for a seat that does not exist is an error, so a typo
    cannot silently drop a gate either.
  `allowed` is True only when every verdict is PASS, every verdict records what it judged, both ends ran, and
    both ends are on the roster. A pass that binds to nothing is not a go.
  `root` is one digest over the whole decision (the roster, then each verdict's gate, end, outcome and what it
    bound), so a single approval can be tied to the entire run and not to one gate.

It adds no judgment. The verdicts are the gates' own, run by `run_repo_chain`, resolved fail-closed by
`cns.gate.resolve`. It imports no repository: the gates are handed in.

REPLACES composition-engine

composition-engine routed a subject through systems by declared outcome model and read only the last step's
outcome (see gate_chain: a breach in the middle was lost if the last gate passed). Its one adapter and its
vocabulary table already have CNS-side equivalents in `compose_library` and `adapters`. What it never had was a
single control point that cannot be talked out of a gate, which is this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Tuple

from cns.gate import Gate, GateOutcome, GatePosition, GateResult, subject_digest

from .gate_chain import ChainRun, Lazy
from .repo_gates import ends_of, run_repo_chain

__all__ = ["Decision", "MissingCandidate", "SuperGate"]

#: A seat on the roster: the repository the gate came from, and the gate.
Seat = Tuple[str, Gate]


class MissingCandidate(Exception):
    """A seat on the roster was given nothing to judge."""


def _key(repo: str, gate: Gate) -> str:
    return f"{repo}:{getattr(gate, 'name', '') or type(gate).__name__}"


def _no_candidate(key: str):
    def build() -> object:
        raise MissingCandidate(key)
    return Lazy(build)


@dataclass(frozen=True)
class Decision:
    """What the roster decided, and the proof of it."""

    run: ChainRun
    #: The seats of the roster, in order, as `repository:gate`.
    seats: Tuple[str, ...]
    #: One digest over the roster and every verdict.
    root: str

    @property
    def outcome(self) -> GateOutcome:
        return self.run.outcome

    @property
    def allowed(self) -> bool:
        """True only for a complete, all-PASS decision in which every verdict records what it judged."""
        return (self.run.outcome is GateOutcome.PASS and self.run.omega_ran and self.run.complete
                and not self.run.unbound())

    def reasons(self) -> Tuple[str, ...]:
        """Why not, one line per verdict that stopped it or does not record what it judged."""
        lines = [f"{r.gate} ({r.position.value}): {r.reason or r.outcome.value}" for r in self.run.blocking()]
        lines += [f"{name}: its verdict does not record what it judged" for name in self.run.unbound()]
        if not self.run.omega_ran:
            lines.append("the omega gates did not run because an alpha gate refused")
        return tuple(lines)

    def binds(self, root: str) -> bool:
        """Whether an approval carrying `root` was issued for exactly this decision."""
        return root == self.root


def _verdict(r: GateResult) -> Mapping[str, object]:
    return {"gate": r.gate, "position": r.position.value, "outcome": r.outcome.value,
            "subject": r.subject, "digest": r.subject_digest}


class SuperGate:
    """A roster of repository gates that decides on all of them or on none.

    Raises ValueError at construction for a gate at an end its repository does not declare, a duplicate seat,
    a roster that is not complete (no ALPHA gate, or no OMEGA gate) unless `require_complete=False`, a
    roster missing any seat named in `required`, and an empty roster. KeyError for a repository with no row
    in `repo_gates`.
    """

    def __init__(self, seats: Iterable[Seat], *, require_complete: bool = True,
                 required: Iterable[str] = ()) -> None:
        self._seats: Tuple[Seat, ...] = tuple(seats)
        self._require_complete = require_complete
        if not self._seats:
            raise ValueError("a roster with no gates decides nothing")
        keys = [_key(repo, gate) for repo, gate in self._seats]
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:
            raise ValueError("a seat appears twice: " + ", ".join(twice))
        for repo, gate in self._seats:
            allowed = ends_of(repo)
            if gate.position not in allowed:
                raise ValueError(f"{_key(repo, gate)}: {repo} declares "
                                 f"{'/'.join(sorted(p.value for p in allowed))}, not {gate.position.value}")
        ends = {gate.position for _, gate in self._seats}
        if require_complete and ends != {GatePosition.ALPHA, GatePosition.OMEGA}:
            missing = "alpha" if GatePosition.ALPHA not in ends else "omega"
            raise ValueError(f"the roster has no {missing} gate, so it is a stratum and not a complete gate; "
                             "pass require_complete=False if that is intended")
        self._keys = tuple(keys)
        missing = sorted(set(required) - set(keys))
        if missing:
            raise ValueError("the roster lacks required seat(s), refusing to decide without them: "
                             + ", ".join(missing))

    @property
    def seats(self) -> Tuple[str, ...]:
        return self._keys

    def decide(self, candidates: Mapping[str, object]) -> Decision:
        """Decide on the whole roster. `candidates` maps each seat (`repository:gate`) to what it judges.

        A candidate may be `Lazy`. A seat with no entry is a TERMINAL_BREACH. An entry for no seat is a
        ValueError, before any gate runs.
        """
        unknown = sorted(set(candidates) - set(self._keys))
        if unknown:
            raise ValueError("candidates for seats that are not on the roster: " + ", ".join(unknown))
        steps = [(repo, gate, candidates[key] if key in candidates else _no_candidate(key))
                 for (repo, gate), key in zip(self._seats, self._keys)]
        run = run_repo_chain(steps, require_complete=self._require_complete)
        root = subject_digest({"seats": list(self._keys), "verdicts": [_verdict(r) for r in run.results]})
        return Decision(run=run, seats=self._keys, root=root)

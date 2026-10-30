"""run_chain: run the gates of a CNS chain on real candidates and resolve them.

WHY THIS EXISTS

The repositories each ship a gate (``cns.gate.Gate``) that answers one question in its own
vocabulary and binds its verdict to what it judged: ghost_tools' finding gate, SWIZZLE's proof and
attack gates, ASSAY's answer-key gate, the Judge, and others. Nothing here called them. ``cns.gate``
defines what a chain is and how verdicts resolve; it runs nothing, because running is behaviour and
the shapes package holds none. This is the behaviour, written against ``cns.gate`` alone, so it
imports no repository: any object with a ``name``, a ``position`` and a ``check`` can be a gate.

WHY NOT LibraryComposer

``LibraryComposer.compose`` canonicalizes only the LAST step's outcome. A gate in the middle of a
path that breaches is lost if the final gate passes. A chain must resolve every verdict it
collected, so this module does that with ``cns.gate.resolve`` and does not go through the composer.

THE RULES (each one is a test)

  Every ALPHA gate runs, in order. A later TERMINAL_BREACH must not hide behind an earlier RETRY.
  OMEGA gates run only if every ALPHA gate passed. An ALPHA refusal means the work never starts, so
    there is no result for an OMEGA gate to judge.
  A candidate may be ``Lazy``: built only when its gate's turn comes, so an OMEGA candidate that
    costs something to make (a run of attacks) is not made when ALPHA already refused.
  A gate that raises, returns something that is not a ``GateResult``, or answers at a different end
    than the one it declares, becomes a TERMINAL_BREACH naming the gate. It is recorded unbound,
    because it judged nothing. It is never a pass and never an exception that ends the run early.
  A gate in the wrong slot is a programming error, refused before anything runs
    (``GateChain.misplaced``).
  An empty chain, or one with only one end, is refused unless the caller says it knows
    (``require_complete=False``). A chain with an empty ALPHA end is a stratum, not a gate.

The verdicts are bound by the gates themselves (``cns.gate.subject_digest``). This module records
them and reports which are unbound; it does not judge content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Tuple

from cns.gate import (
    Gate,
    GateChain,
    GateOutcome,
    GatePosition,
    GateResult,
    resolve,
    unbound,
)

__all__ = ["ChainRun", "Lazy", "run_chain"]

#: A gate and the candidate it is to judge.
Step = Tuple[Gate, object]


@dataclass(frozen=True)
class Lazy:
    """A candidate built only when its gate's turn comes."""

    build: Callable[[], object]


@dataclass(frozen=True)
class ChainRun:
    """Every verdict a chain produced, in the order its gates ran, and what they resolve to."""

    results: Tuple[GateResult, ...]
    outcome: GateOutcome
    #: Whether the OMEGA gates ran. False means an ALPHA gate refused, so there was nothing to judge.
    omega_ran: bool
    #: Whether both ends of the chain were populated.
    complete: bool

    def unbound(self) -> Tuple[str, ...]:
        """Names of verdicts that do not record what they judged."""
        return unbound(self.results)

    def blocking(self) -> Tuple[GateResult, ...]:
        """The verdicts that stopped the request."""
        return tuple(r for r in self.results if r.blocking())


def _breach(gate: Gate, position: GatePosition, reason: str) -> GateResult:
    """A refusal for a gate that could not answer. Unbound: it judged nothing."""
    name = getattr(gate, "name", "") or type(gate).__name__
    return GateResult(gate=name, position=position, outcome=GateOutcome.TERMINAL_BREACH, reason=reason)


def _check(gate: Gate, candidate: object) -> GateResult:
    position = gate.position
    name = getattr(gate, "name", "") or type(gate).__name__
    try:
        subject = candidate.build() if isinstance(candidate, Lazy) else candidate
        result = gate.check(subject)
    except Exception as exc:  # a gate that cannot answer is a breach, whatever it raised
        return _breach(gate, position, f"{name} raised {type(exc).__name__} and could not answer; "
                                       "a gate that cannot answer is never read as a pass")
    if not isinstance(result, GateResult):
        return _breach(gate, position, f"{name} returned {type(result).__name__}, not a GateResult; "
                                       "an answer that is not a verdict is never read as a pass")
    if result.position is not position:
        return _breach(gate, position, f"{name} declares {position.value} but answered at "
                                       f"{result.position.value}; a verdict from the wrong end is refused")
    if result.gate != name:
        return _breach(gate, position, f"{name} answered as {result.gate!r}; a verdict that does not name the "
                                       "gate seated for it is refused")
    return result


def run_chain(
    alpha: Iterable[Step] = (),
    omega: Iterable[Step] = (),
    *,
    require_complete: bool = True,
) -> ChainRun:
    """Run ``alpha`` then, if every one passed, ``omega``, and resolve all the verdicts.

    ``alpha`` and ``omega`` are sequences of ``(gate, candidate)``. The same gate may appear more
    than once with different candidates (a finding gate, once per finding).
    """
    first, second = tuple(alpha), tuple(omega)
    chain = GateChain(alpha=tuple(g for g, _ in first), omega=tuple(g for g, _ in second))
    wrong = chain.misplaced()
    if wrong:
        raise ValueError(f"gates are in the wrong slot, refusing to run: {', '.join(wrong)}")
    if require_complete and not chain.complete():
        missing = "alpha" if not first else "omega"
        raise ValueError(
            f"the chain has no {missing} gate, so it is a stratum and not a complete gate; "
            "pass require_complete=False if that is intended"
        )
    if not first and not second:
        raise ValueError("a chain with no gates judges nothing")

    results = [_check(g, c) for g, c in first]
    omega_ran = not any(r.blocking() for r in results)
    if omega_ran:
        results.extend(_check(g, c) for g, c in second)
    return ChainRun(
        results=tuple(results),
        outcome=resolve(results),
        omega_ran=omega_ran,
        complete=chain.complete(),
    )

"""CONFIDENTIAL. Trade secret of William King (wking53214). Recorded 2026-09-11.
See README.md. Do not copy, publish, vendor, or disclose.

cns.gate: the ordered two-ended decision contract.

WHY THIS EXISTS

The library's governing constraint is a gate with two ends and a position.
It was derived on 2026-03-25 and recorded in the design archive at
18:55:45Z in its final form: an origin condition evaluated **before**
execution, an outcome condition evaluated **on the result**, and a failing
query aborted rather than repaired.

The argument for the position, made 36 minutes earlier at 18:19:44Z, is the
load-bearing part and it is an engineering argument. A constraint evaluated
last is a filter, and a sufficiently motivated caller finds a way to
"technically comply" with a filter while pursuing its own agenda. A
constraint evaluated first is a precondition, and nothing downstream exists
until it passes. Order is not presentation here; it is the whole mechanism.

WHAT WENT WRONG, MEASURED 2026-09-12

No repository in the library implements both ends. Four carry an authority
precondition that denies (OBSERVE, Ecology, GSA-815, GSA) with a three-term
deny list standing in for the outcome end. One carries a genuinely good
outcome stratum with a terminal-breach refusal and no precondition at all
(DIT). Five carry gate vocabulary and neither end. In the one repository
holding both, the two sit roughly 2,400 lines apart in different layers and
nothing establishes that they run on the same request.

That did not happen by decision. No record in the archive revokes the
constraint; it is present through 2026-07-06. What happened is that the
ordering lived only as a convention inside four files, and a repository
written later inherited whichever half its own source happened to carry. By
2026-07-06 the constraint is described in the archive as scrubbing text
fields: a gate that aborted a query had become a gate that cleans a string,
with no decision recorded against it.

Convention cannot carry an invariant across twenty repositories. A type can.

WHAT THIS MODULE DOES ABOUT IT

`GatePosition` makes the end a gate runs at a **declared property of the
gate** rather than a fact about where somebody happened to call it.
`GateChain` gives the two ends separate fields, so a chain cannot silently
hold an outcome gate in its precondition slot, and `GateChain.misplaced`
reads its own fields and says which gates are in the wrong slot.

`resolve` fixes the failure precedence once, here, instead of in each
consumer: any terminal breach wins, then any retry, and PASS only when
nothing objected. Fail-closed is a property of the contract, not a habit
each repo has to remember.

This module carries shapes and pure functions of them, like the rest of the
package. Running the gates is the consumer's, and so is deciding what each
gate inspects. The contract says only that there are two ends, which end
each gate belongs to, and what a mixture of verdicts means.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Tuple, runtime_checkable

from cns.rowenum import RowEnum

__all__ = [
    "GatePosition",
    "GateOutcome",
    "GateResult",
    "Gate",
    "GateChain",
    "resolve",
]


class GatePosition(RowEnum):
    """Which end of the decision a gate belongs to.

    ALPHA runs before execution and its failure means the work never
    starts. OMEGA runs on the produced result and its failure means the
    result does not leave.
    """

    ALPHA = 'alpha'
    OMEGA = 'omega'


class GateOutcome(RowEnum):
    """A verdict, in increasing order of finality.

    RETRY and TERMINAL_BREACH are deliberately distinct. A retryable
    rejection may be re-rendered with an instructional delta; a terminal
    breach is the abort the original constraint specified, and no delta
    repairs it.
    """

    PASS = 'pass'
    RETRY = 'retry'
    TERMINAL_BREACH = 'terminal_breach'


@dataclass(frozen=True, slots=True)
class GateResult:
    """One gate's verdict on one candidate.

    `reason` is for the audit record and for the delta a RETRY invites. It
    is not optional in practice: a refusal a caller cannot explain is a
    refusal its own author will later delete.
    """

    gate: str
    position: GatePosition
    outcome: GateOutcome
    reason: str = ""

    def blocking(self) -> bool:
        """Whether this verdict stops the request. Reads only its own fields."""
        return self.outcome is not GateOutcome.PASS


@runtime_checkable
class Gate(Protocol):
    """What every gate in either end exposes. The predicate is the repo's own.

    `position` is part of the interface on purpose. A gate that does not
    declare which end it belongs to is the defect this module exists to
    end, because it is the shape that let an outcome-only stratum be
    mistaken for a complete gate.
    """

    name: str
    position: GatePosition

    def check(self, candidate: object) -> GateResult: ...


@dataclass(frozen=True, slots=True)
class GateChain:
    """The two ends of one decision, as separate fields.

    Separate fields rather than one ordered sequence, because a single list
    records the order somebody wrote it in and this records which end each
    gate is for. A consumer runs `alpha` to completion before the work
    begins and `omega` on the result; a chain with an empty `alpha` is a
    stratum, not a gate, and `complete` says so.
    """

    alpha: Tuple[Gate, ...] = ()
    omega: Tuple[Gate, ...] = ()

    def complete(self) -> bool:
        """Whether both ends are populated. Reads only its own fields."""
        return bool(self.alpha) and bool(self.omega)

    def misplaced(self) -> Tuple[str, ...]:
        """Names of gates sitting in the slot for the other end.

        A gate declares its position and a chain assigns it a slot. When
        those disagree the chain is wrong, and this is what a consumer's
        own test asserts is empty.
        """
        wrong = [g.name for g in self.alpha if g.position is not GatePosition.ALPHA]
        wrong += [g.name for g in self.omega if g.position is not GatePosition.OMEGA]
        return tuple(wrong)


def resolve(results: Iterable[GateResult]) -> GateOutcome:
    """The decision a set of verdicts adds up to, resolved fail-closed.

    Any terminal breach decides the whole set, then any retry, and PASS
    only when nothing objected. An empty set is PASS, which is correct:
    the caller ran no gates and this function does not invent a refusal it
    has no evidence for. A chain that should have had gates is caught by
    `GateChain.complete`, which is a different question asked earlier.
    """
    outcome = GateOutcome.PASS
    for r in results:
        if r.outcome is GateOutcome.TERMINAL_BREACH:
            return GateOutcome.TERMINAL_BREACH
        if r.outcome is GateOutcome.RETRY:
            outcome = GateOutcome.RETRY
    return outcome

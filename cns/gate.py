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

BINDING A VERDICT TO WHAT IT JUDGED

Added in 1.2.0, after HERALD was read. Everything above models the verdict
and nothing modelled the thing judged, so a `GateResult` could be built by
hand and pointed at anything, or lifted off the payload it was issued for
and reused on a different one. A gate that cannot be transplanted is worth
more than a gate that merely exists.

HERALD had already solved this for itself: its `GateDecision` is MAC-signed
over the claim's content and `verify_against` raises rather than return a
verdict that does not match. That is the right design and this is the part
of it that belongs in a shared contract.

`subject` names what was judged. `subject_digest` is a canonical digest of
its content, computed by `subject_digest()` here so that every consumer
computes it the same way; a digest each repo derives its own way does not
cross a repository boundary, which is the only reason to put it here.
`GateResult.binds` answers whether a verdict was issued against exactly
this content, and `unbound` names the verdicts in a set that carry no
binding at all, for a consumer that wants to require one.

**This is tamper-evidence, not tamper-proofing, and the distinction is not
a quibble.** A digest detects a verdict transplanted onto different content
and content that drifted after a verdict was issued. It does not detect an
adversary who recomputes the digest, because there is no secret here and
there cannot be: a key is state and configuration, and this package holds
neither. A consumer needing that adds a MAC over these fields, which is
exactly what HERALD does.

This module carries shapes and pure functions of them, like the rest of the
package. Running the gates is the consumer's, and so is deciding what each
gate inspects. The contract says only that there are two ends, which end
each gate belongs to, what a verdict is bound to, and what a mixture of
verdicts means.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence, Tuple, runtime_checkable

from cns.rowenum import RowEnum

__all__ = [
    "GatePosition",
    "GateOutcome",
    "GateResult",
    "Gate",
    "GateChain",
    "resolve",
    "subject_digest",
    "unbound",
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
    subject: str = ""
    subject_digest: str = ""

    def blocking(self) -> bool:
        """Whether this verdict stops the request. Reads only its own fields."""
        return self.outcome is not GateOutcome.PASS

    def bound(self) -> bool:
        """Whether this verdict records what it judged. Reads only its own fields."""
        return bool(self.subject) and bool(self.subject_digest)

    def binds(self, subject: str, digest: str) -> bool:
        """Whether this verdict was issued against exactly this content.

        An unbound verdict binds to nothing, including to empty arguments.
        Returning True there would make every hand-built `GateResult` pass
        a check whose whole purpose is to catch hand-built ones.
        """
        return self.bound() and self.subject == subject and self.subject_digest == digest


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


def _canonical(value: Any) -> str:
    """A length-prefixed rendering of restricted content, injective by design.

    Not JSON. `json` is forbidden in this package on purpose -- serialization
    is the consumer's job and `tests/test_graph.py` enforces it -- and a
    digest needs something stronger than JSON anyway. Length prefixes make
    the encoding unambiguous without escaping, so no two distinct inputs can
    render alike: `{"ab": "c"}` and `{"a": "bc"}` are the kind of collision
    a separator-based format has to escape its way out of and this one
    cannot have.

    `float` is supported with a pinned rendering, added in 1.3.0. An earlier
    version refused it, on the reasoning that shortest-repr is where
    canonical encodings stop agreeing. Reading the first real consumer
    settled it the other way: HERALD's sealed content carries `confidence`
    and every deduction's `delta` as floats, so a contract that refuses
    them is a contract that repo cannot adopt, and the contract was the
    thing that was wrong.

    `repr` is shortest-roundtrip on every CPython this package supports and
    identical across them, which the test suite checks on all four rather
    than assumes. The three genuine hazards are handled rather than hoped
    about: `-0.0` normalises to `0.0` (they are equal and must not digest
    differently), and NaN and the infinities are refused, because they are
    not values a verdict can meaningfully be bound to and JSON cannot
    render them without leaving the standard.
    """
    if value is None:
        return "n:"
    if isinstance(value, bool):
        # Before int: bool is a subclass of int, and True would render as 1.
        return "b:1" if value else "b:0"
    if isinstance(value, int):
        return f"i:{value}:"
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise TypeError(
                "cannot bind a verdict to NaN or an infinity")
        if value == 0.0:
            value = 0.0  # collapses -0.0, which compares equal to it
        return f"f:{value!r}:"
    if isinstance(value, str):
        return f"s:{len(value)}:{value}"
    if isinstance(value, Mapping):
        items = sorted((str(k) for k in value.keys()))
        if len(set(items)) != len(items):
            raise TypeError("mapping keys collide once stringified")
        body = "".join(_canonical(k) + _canonical(value[k]) for k in items)
        return f"d:{len(items)}:{body}"
    if isinstance(value, (list, tuple)) or (
            isinstance(value, Sequence) and not isinstance(value, (str, bytes))):
        body = "".join(_canonical(v) for v in value)
        return f"l:{len(value)}:{body}"
    raise TypeError(
        f"cannot bind a verdict to {type(value).__name__}; use str, int, "
        f"float, bool, None, or a mapping or sequence of those")


def subject_digest(content: Mapping[str, object]) -> str:
    """Canonical digest of judged content, identical in every consumer.

    SHA-256 over `_canonical`. Canonical matters more than convenient here:
    two repositories that hash the same claim differently cannot check each
    other's verdicts, and that is the only reason this function belongs in a
    shared package rather than in each caller.

    A `TypeError` from here means a gate tried to bind a verdict to content
    it cannot describe unambiguously. That is a defect in the gate, not a
    case to paper over.
    """
    return hashlib.sha256(_canonical(content).encode("utf-8")).hexdigest()


def unbound(results: Iterable[GateResult]) -> Tuple[str, ...]:
    """Names of verdicts that do not record what they judged.

    For a consumer that requires binding: assert this is empty, the same
    way `GateChain.misplaced` is asserted empty. It is a separate question
    from `resolve`, which decides what a set of verdicts means and is not
    the place to also adjudicate whether they are well-formed.
    """
    return tuple(r.gate for r in results if not r.bound())

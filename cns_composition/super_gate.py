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
  Seats that judge one thing can be required to judge the same thing. Each verdict is bound to what its own gate
    judged, and nothing else makes two gates judge the same document: a gate can pass the true invoice while its
    neighbour passes an inflated one, and every verdict is bound and PASS. `same_subject` names those seats and, for
    each, how to read from its candidate WHICH document it is about and the digest of that document's content. A
    built-in gate, `CNS:same_subject`, runs first and refuses the decision unless every named seat reads the same
    identity and the same digest. It only compares what the extractors read, so an extractor is policy: write it
    beside the required roster, where it is reviewed with it.
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

import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Mapping, Optional, Tuple, cast

from cns.gate import Gate, GateOutcome, GatePosition, GateResult, subject_digest

from .gate_chain import ChainRun, Lazy
from .repo_gates import ends_of, run_repo_chain

__all__ = ["BindingOf", "Decision", "Judged", "MissingCandidate", "SubjectAgreement", "SuperGate"]

#: Process-local key. Only `SuperGate.decide` uses it, to prove it issued a Decision. It is never exported, written
#: or logged. Like HERALD's issuer key it proves origin only inside this process: a proof means nothing to another
#: process, and code in this process that is willing to read a private name can still reach it.
_ISSUER_KEY: bytes = secrets.token_bytes(32)

#: A seat on the roster: the repository the gate came from, and the gate.
Seat = Tuple[str, Gate]


class MissingCandidate(Exception):
    """A seat on the roster was given nothing to judge."""


@dataclass(frozen=True)
class Judged:
    """What a candidate is about: which document, and the digest of that document's content."""

    identity: str
    digest: str


#: How to read what a seat's candidate is about.
SubjectOf = Callable[[object], Judged]

#: How to read what a seat's verdict must be bound to for this candidate: the (subject, digest) a PASS must carry.
BindingOf = Callable[[object], Tuple[str, str]]

#: The seat the super gate adds when `same_subject` is given.
SUBJECT_REPO, SUBJECT_GATE = "CNS", "same_subject"
SUBJECT_SEAT = f"{SUBJECT_REPO}:{SUBJECT_GATE}"
UNCHANGED_GATE = f"{SUBJECT_REPO}:unchanged"


class SubjectAgreement:
    """ALPHA gate: every seat that was read judged the same document identity and the same content digest.

    Its candidate is the mapping the super gate builds, seat to `Judged` or to the reason the seat could not be
    read. A seat that cannot be read is a TERMINAL_BREACH, never a skipped comparison.
    """

    name = SUBJECT_GATE
    position = GatePosition.ALPHA

    def check(self, candidate: object) -> GateResult:
        def verdict(outcome: GateOutcome, reason: str, bound: Optional[Mapping[str, object]] = None) -> GateResult:
            return GateResult(gate=self.name, position=self.position, outcome=outcome, reason=reason,
                              subject=self.name if bound is not None else "",
                              subject_digest=subject_digest(bound) if bound is not None else "")

        if not isinstance(candidate, Mapping) or not candidate:
            return verdict(GateOutcome.TERMINAL_BREACH, "no seats were read, so there is nothing to compare")
        unread = {seat: why for seat, why in candidate.items() if not isinstance(why, Judged)}
        if unread:
            return verdict(GateOutcome.TERMINAL_BREACH, "; ".join(f"{seat}: {why}" for seat, why in sorted(unread.items())))
        views = {seat: [j.identity, j.digest] for seat, j in candidate.items()}
        groups: dict = {}
        for seat, j in candidate.items():
            groups.setdefault((j.identity, j.digest), []).append(seat)
        if len(groups) > 1:
            said = "; ".join(f"{', '.join(sorted(seats))} judged {identity} ({digest[:12]})"
                             for (identity, digest), seats in sorted(groups.items()))
            return verdict(GateOutcome.TERMINAL_BREACH, "the seats judged different subjects: " + said, {"views": views})
        (identity, digest), seats = next(iter(groups.items()))
        return verdict(GateOutcome.PASS, f"{len(seats)} seats judged the same subject, {identity}",
                       {"identity": identity, "digest": digest, "seats": sorted(seats)})


class _Once:
    """A Lazy candidate's build, run once: the comparison and the gate see the same object."""

    def __init__(self, build: Callable[[], object]) -> None:
        self._build = build
        self._done = False
        self._value: object = None
        self._error: Optional[Exception] = None

    def __call__(self) -> object:
        if not self._done:
            try:
                self._value = self._build()
            except Exception as exc:  # kept, and raised again for the gate that asks next
                self._error = exc
            self._done = True
        if self._error is not None:
            raise self._error
        return self._value


class _Bound:
    """A seated gate whose PASS must be bound to what its reader says this candidate is, not to anything at all."""

    def __init__(self, gate: Gate, binding_of: BindingOf) -> None:
        self.name = getattr(gate, "name", "") or type(gate).__name__
        self.position = gate.position
        self._gate, self._binding_of = gate, binding_of

    def check(self, candidate: object) -> GateResult:
        result = self._gate.check(candidate)
        if not isinstance(result, GateResult) or result.outcome is not GateOutcome.PASS:
            return result  # not a pass: nothing to lift, and the chain refuses a wrong answer type itself
        try:
            subject, digest = self._binding_of(candidate)
            matches = result.binds(subject, digest)
        except Exception as exc:  # a reader that cannot say what this is leaves the pass unproven
            return self._breach(result, f"what this candidate is could not be read ({type(exc).__name__})")
        if not matches:
            return self._breach(result, "its verdict is bound to something other than this candidate")
        return result

    def _breach(self, result: GateResult, why: str) -> GateResult:
        return GateResult(gate=result.gate, position=result.position, outcome=GateOutcome.TERMINAL_BREACH,
                          reason=f"{self.name} passed but {why}; a pass for other content is never read as a pass "
                                 "for this")


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
    #: The one document every `same_subject` seat judged, when the roster has that check and the decision passed.
    #: The `CNS:same_subject` verdict binds it, so `root` covers it. None otherwise, never a guess.
    subject: Optional[Judged] = None
    #: Proof that `SuperGate.decide` issued this decision, over everything `allowed` and the guard rely on. Empty
    #: for a decision built any other way. See `issued`.
    proof: str = ""

    @property
    def issued(self) -> bool:
        """Whether `SuperGate.decide` issued exactly this decision in this process. A decision written by hand,
        copied field by field, or edited after issue is not. `allowed` does not ask this; anything that acts on a
        decision (the `DecisionGuard`) should."""
        return (bool(self.proof) and self.binds(self.root)
                and hmac.compare_digest(self.proof, _proof(self.run, self.root, self.subject)))

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
        return root == self.root == _root(self.seats, self.run.results)


def _proof(run: ChainRun, root: str, subject: Optional[Judged]) -> str:
    """HMAC over what a decision's `allowed` turns on: the root (roster and every verdict), the run's own
    outcome and flags, and the agreed subject."""
    body = subject_digest({"root": root, "outcome": run.outcome.value, "omega_ran": run.omega_ran,
                           "complete": run.complete,
                           "subject": [subject.identity, subject.digest] if subject is not None else None})
    return hmac.new(_ISSUER_KEY, body.encode("utf-8"), hashlib.sha256).hexdigest()


def _root(seats: Tuple[str, ...], results: Tuple[GateResult, ...]) -> str:
    """One digest over the roster and every verdict, recomputed wherever a root is checked."""
    return subject_digest({"seats": list(seats), "verdicts": [_verdict(r) for r in results]})


def _verdict(r: GateResult) -> Mapping[str, object]:
    return {"gate": r.gate, "position": r.position.value, "outcome": r.outcome.value,
            "subject": r.subject, "digest": r.subject_digest}


class SuperGate:
    """A roster of repository gates that decides on all of them or none of it.

    The caller must provide a non-empty required roster from policy/configuration
    independent of candidates passed to decide. This API makes omission explicit;
    it cannot authenticate who supplied the policy configuration.

    `same_subject` maps two or more seats to a reader of what each one's candidate is about (a `Judged`). The
    super gate then adds `CNS:same_subject` as the first ALPHA seat, built from those candidates, and the decision
    is refused unless they all agree. Add `CNS:same_subject` to `required` so dropping `same_subject` is refused
    too. A candidate for a named seat that is `Lazy` is built when the comparison runs, once.

    `binding_of` maps seats to a reader of what that seat's verdict must be bound to for the candidate it was given,
    as (subject, digest). A PASS bound to anything else is a breach, so a gate that ignores its input cannot pass it
    with an unrelated fingerprint. With `strict_binding=True` every seat must have a reader.

    Raises ValueError for invalid or incomplete rosters and KeyError for a
    repository with no row in repo_gates.
    """

    def __init__(self, seats: Iterable[Seat], *, required: Iterable[str],
                 require_complete: bool = True, same_subject: Optional[Mapping[str, SubjectOf]] = None,
                 binding_of: Optional[Mapping[str, BindingOf]] = None, strict_binding: bool = False) -> None:
        self._seats: Tuple[Seat, ...] = tuple(seats)
        self._require_complete = require_complete
        if not self._seats:
            raise ValueError("a roster with no gates decides nothing")
        required_keys = tuple(required)
        if not required_keys:
            raise ValueError("required must name at least one policy-required seat")
        if any(not isinstance(key, str) or not key for key in required_keys):
            raise ValueError("required seat names must be non-empty strings")
        if len(set(required_keys)) != len(required_keys):
            raise ValueError("required contains a duplicate seat")
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
            absent = "alpha" if GatePosition.ALPHA not in ends else "omega"
            raise ValueError(f"the roster has no {absent} gate, so it is a stratum and not a complete gate; "
                             "pass require_complete=False if that is intended")
        self._subject_of = dict(same_subject) if same_subject is not None else {}
        if same_subject is not None:
            if len(self._subject_of) < 2:
                raise ValueError("same_subject must name at least two seats; one seat agrees with itself")
            if any(not callable(of) for of in self._subject_of.values()):
                raise ValueError("same_subject must map each seat to a function that reads its subject")
            off = sorted(set(self._subject_of) - set(keys))
            if off:
                raise ValueError("same_subject names seat(s) not on the roster: " + ", ".join(off))
            if SUBJECT_SEAT in keys:
                raise ValueError(f"{SUBJECT_SEAT} is added by the super gate and cannot be seated by hand")
            # Added after the completeness check above, so it never stands in for a real ALPHA gate.
            self._seats = ((SUBJECT_REPO, SubjectAgreement()),) + self._seats
            keys = [SUBJECT_SEAT] + keys
        self._keys = tuple(keys)
        self._binding_of = dict(binding_of) if binding_of is not None else {}
        if any(not callable(of) for of in self._binding_of.values()):
            raise ValueError("binding_of must map each seat to a function that reads what its verdict must bind")
        off = sorted(set(self._binding_of) - set(keys) - {SUBJECT_SEAT})
        if off or SUBJECT_SEAT in self._binding_of:
            raise ValueError("binding_of names seat(s) not on the roster or added by the super gate: "
                             + ", ".join(off or [SUBJECT_SEAT]))
        self._strict_binding = strict_binding
        if strict_binding:
            unread = sorted(set(keys) - {SUBJECT_SEAT} - set(self._binding_of))
            if unread:
                raise ValueError("strict_binding needs a binding reader for every seat; none for: "
                                 + ", ".join(unread))
        missing = sorted(set(required_keys) - set(keys))
        if missing:
            raise ValueError("the roster lacks required seat(s), refusing to decide without them: "
                             + ", ".join(missing))

    @property
    def seats(self) -> Tuple[str, ...]:
        return self._keys

    def _read_subjects(self, given: Mapping[str, object]) -> Mapping[str, object]:
        """Each named seat's subject, or the reason it could not be read."""
        views: dict = {}
        for key, subject_of in self._subject_of.items():
            if key not in given:
                views[key] = "has no candidate, so there is nothing to compare"
                continue
            try:
                candidate = given[key]
                seen = subject_of(candidate.build() if isinstance(candidate, Lazy) else candidate)
            except Exception as exc:  # a seat that cannot be read is a breach, whatever it raised
                views[key] = f"its subject could not be read ({type(exc).__name__})"
                continue
            if not (isinstance(seen, Judged) and isinstance(seen.identity, str) and isinstance(seen.digest, str)
                    and seen.identity and seen.digest):
                views[key] = "its subject does not name a document identity and a content digest"
                continue
            views[key] = seen
        return views

    def decide(self, candidates: Mapping[str, object]) -> Decision:
        """Decide on the whole roster. `candidates` maps each seat (`repository:gate`) to what it judges.

        A candidate may be `Lazy`. A seat with no entry is a TERMINAL_BREACH. An entry for no seat is a
        ValueError, before any gate runs.
        """
        unknown = sorted(set(candidates) - set(self._keys))
        if unknown:
            raise ValueError("candidates for seats that are not on the roster: " + ", ".join(unknown))
        if self._subject_of and SUBJECT_SEAT in candidates:
            raise ValueError(f"{SUBJECT_SEAT} is built by the super gate from the other candidates, not supplied")
        given = dict(candidates)
        if self._subject_of:
            for key in self._subject_of:
                seat = given.get(key)
                if isinstance(seat, Lazy):
                    given[key] = Lazy(_Once(seat.build))
            views = _Once(lambda: self._read_subjects(given))
            given[SUBJECT_SEAT] = Lazy(views)
        steps = [(repo, _Bound(gate, self._binding_of[key]) if key in self._binding_of else gate,
                  given[key] if key in given else _no_candidate(key))
                 for (repo, gate), key in zip(self._seats, self._keys)]
        run = run_repo_chain(steps, require_complete=self._require_complete)
        subject: Optional[Judged] = None
        if self._subject_of and run.outcome is GateOutcome.PASS:
            # Every gate ran, so the readings were taken; this is the agreement the gate passed, not a second reading.
            read = set(cast(Mapping[str, object], views()).values())
            only = next(iter(read)) if len(read) == 1 else None
            if isinstance(only, Judged):
                subject = only
        if subject is not None:
            # A gate may have edited a shared candidate after the comparison and before a later gate judged it. Read
            # every seat again, now that all the gates have run, and refuse the decision unless nothing moved.
            if set(cast(Mapping[str, object], self._read_subjects(given)).values()) != {subject}:
                changed = GateResult(
                    gate=UNCHANGED_GATE, position=GatePosition.OMEGA, outcome=GateOutcome.TERMINAL_BREACH,
                    reason="a candidate changed while the gates were running, so the verdicts do not describe "
                           "what it is now")
                run = replace(run, results=run.results + (changed,), outcome=GateOutcome.TERMINAL_BREACH)
                subject = None
        root = _root(self._keys, run.results)
        return Decision(run=run, seats=self._keys, root=root, subject=subject, proof=_proof(run, root, subject))

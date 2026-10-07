"""The resubmission guard: a retry must come back changed, or stop.

WHY THIS EXISTS

`cns.gate.GateOutcome.RETRY` says a rejected candidate "may be re-rendered
with an instructional delta". Nothing in the library checks that it was. A
caller can resubmit exactly what was refused, forever, and every gate will
judge it fresh each time. A caller can also swing between two versions (A,
then B, then A again), which looks like progress on every single step and is
a loop over three.

This module is the check. It remembers what each subject was submitted as and
judges each new submission against that history:

    first submission              PASS             nothing to compare yet
    changed since the last one    PASS             a delta arrived
    unchanged, under the cap      PASS             allowed; see below
    unchanged, at the cap         TERMINAL_BREACH  resubmitted unchanged too often
    an earlier version again      TERMINAL_BREACH  oscillation (A, B, A)

WHY SOME UNCHANGED RESUBMISSIONS ARE ALLOWED

Not every RETRY asks for different content. `ccc_admission` answers RETRY when
CCC has not recorded an item yet: the remedy is to hand the session to CCC
and ask again with exactly the same text. The world changed, not the
candidate. Refusing every unchanged resubmission would break that flow, so an
unchanged resubmission is allowed `max_unchanged - 1` times in a row and the
next one is refused. A changed submission resets the count.

WHAT IT REMEMBERS, AND FOR HOW LONG

A subject's history is the content digests of its accepted submissions, in
order. A refused submission is not recorded, so refusing it again is
deterministic: resubmitting the same refused content is refused the same way.

Memory is bounded in two directions, because an unbounded history is the
defect DIT's 2026-07-07 audit recorded for its own loop guard. Each subject
keeps at most `max_history` digests (oscillation back to a version older than
that is not detected), and at most `max_subjects` subjects are held; the
least recently judged one is forgotten first and starts fresh if it returns.
`forget(subject)` clears one subject on purpose, for a caller whose work on
it is finished.

The guard holds state, so it lives here rather than in `cns`, whose rows
never mutate themselves. It is an ALPHA gate: it runs before the work, and
its verdict is bound to the subject and the exact content digest it judged.

PROVENANCE

Ported from innovation_os, `src/innovation_os/retry_guard/engine.py`
(`RetryGuardEngine`), at commit 08470f1, ahead of that repository's
retirement. Kept: unchanged attempts allowed up to a cap (its
`max_retries=3` default), and a return to an earlier version flagged as a
cycle. Changed: innovation_os keyed an attempt on six fields of its own
vocabulary (artifact hash, branch, parent, decision state, evidence id and
version); here the caller names the subject and supplies one content digest,
and folds whatever it considers "the evidence" into that digest with
`cns.gate.subject_digest`. Not carried: innovation_os's fingerprint also
hashed a retry counter that its own repetition check did not pass, so the
two could disagree; the digest here is content only.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

__all__ = [
    "GATE_NAME",
    "Resubmission",
    "ResubmissionGuard",
]

#: The name every verdict from this gate carries.
GATE_NAME = "cns.resubmission"


@dataclass(frozen=True)
class Resubmission:
    """One submission of a subject: what it is, and a digest of its content.

    `subject` is the caller's stable name for the thing being retried (a
    candidate id, a request key). `content_digest` is a digest of everything
    the caller counts as having to change for a retry to be a real retry,
    normally `cns.gate.subject_digest` of that content.
    """

    subject: str
    content_digest: str

    def __post_init__(self) -> None:
        for name in ("subject", "content_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Resubmission.{name} must be a non-empty string")


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    return value


class ResubmissionGuard:
    """ALPHA gate: a resubmission must change, within a cap, and never go back."""

    name = GATE_NAME
    position = GatePosition.ALPHA

    def __init__(self, max_unchanged: int = 3, max_history: int = 64,
                 max_subjects: int = 10_000) -> None:
        self.max_unchanged = _positive_int("max_unchanged", max_unchanged)
        self.max_history = _positive_int("max_history", max_history)
        self.max_subjects = _positive_int("max_subjects", max_subjects)
        self._history: OrderedDict[str, list[str]] = OrderedDict()

    def check(self, candidate: object) -> GateResult:
        """Judge one submission and, unless it is refused, remember it."""
        if not isinstance(candidate, Resubmission):
            raise TypeError(
                f"ResubmissionGuard judges a Resubmission; got {type(candidate).__name__}")
        history = self._history.get(candidate.subject, [])
        outcome, reason = self._judge(history, candidate.content_digest)
        if outcome is GateOutcome.PASS:
            self._remember(candidate.subject, history, candidate.content_digest)
        elif candidate.subject in self._history:
            self._history.move_to_end(candidate.subject)
        return GateResult(
            gate=GATE_NAME,
            position=GatePosition.ALPHA,
            outcome=outcome,
            reason=reason,
            subject=candidate.subject,
            subject_digest=subject_digest({
                "subject": candidate.subject,
                "content_digest": candidate.content_digest,
            }),
        )

    def forget(self, subject: str) -> None:
        """Clear one subject's history. Unknown subjects are ignored."""
        self._history.pop(subject, None)

    def attempts(self, subject: str) -> int:
        """How many accepted submissions are remembered for a subject."""
        return len(self._history.get(subject, ()))

    def _judge(self, history: list[str], digest: str):
        if not history:
            return GateOutcome.PASS, "first submission"
        if digest == history[-1]:
            unchanged = 0
            for earlier in reversed(history):
                if earlier != digest:
                    break
                unchanged += 1
            if unchanged >= self.max_unchanged:
                return (GateOutcome.TERMINAL_BREACH,
                        (f"resubmitted unchanged {unchanged + 1} times in a row "
                         f"(limit {self.max_unchanged}); a retry must come back changed"))
            return (GateOutcome.PASS,
                    f"unchanged resubmission {unchanged + 1} of {self.max_unchanged} allowed")
        if digest in history:
            return (GateOutcome.TERMINAL_BREACH,
                    ("oscillation: this content matches an earlier submission, "
                     "not the most recent one"))
        return GateOutcome.PASS, "changed since the last submission"

    def _remember(self, subject: str, history: list[str], digest: str) -> None:
        updated = (history + [digest])[-self.max_history:]
        self._history[subject] = updated
        self._history.move_to_end(subject)
        while len(self._history) > self.max_subjects:
            self._history.popitem(last=False)

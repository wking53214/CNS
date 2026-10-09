"""No CCC record, no use, with the resubmission guard in front (guarded_admission).

WHY THIS EXISTS

`ccc_admission` answers RETRY when CCC has not recorded a Triad output yet.
The remedy is to hand the session to CCC and ask again with the same text.
Nothing stopped that loop, so the same text could come back forever.

This module puts the resubmission guard in front of the CCC check. An
unchanged resubmission is allowed up to the guard's cap, then refused. A
return to an earlier version is refused as oscillation.

ORDER

The guard runs first. If it refuses, CCC is not asked at all. If it passes,
the CCC check decides exactly as it does without the guard. The guard records
every submission it passes, including ones CCC then answers RETRY to. That
record is what lets it count unchanged retries.

The guard is a required argument. A guard created fresh for each call would
never reach its cap, so the caller must keep one guard for as long as the
retries it should count.
"""

from __future__ import annotations

from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

from .ccc_admission import (
    SOURCE,
    CccRecordGate,
    RecordLookup,
    TriadOutput,
    UnrecordedTriadOutput,
    text_digest,
)
from .resubmission import Resubmission, ResubmissionGuard

__all__ = [
    "GuardedCccRecordGate",
    "guarded_admit",
]


class GuardedCccRecordGate:
    """ALPHA gate: the resubmission guard, then CCC's record check."""

    position = GatePosition.ALPHA

    def __init__(self, lookup: RecordLookup, guard: ResubmissionGuard) -> None:
        if not isinstance(guard, ResubmissionGuard):
            raise TypeError(
                "GuardedCccRecordGate needs a ResubmissionGuard; "
                f"got {type(guard).__name__}."
            )
        self._record_gate = CccRecordGate(lookup)
        self._guard = guard

    def check(self, candidate: object) -> GateResult:
        if not isinstance(candidate, TriadOutput):
            raise TypeError(
                "GuardedCccRecordGate judges a TriadOutput; "
                f"got {type(candidate).__name__}"
            )
        submission = Resubmission(
            subject=f"{SOURCE}:{candidate.candidate_id}",
            content_digest=subject_digest(
                {"text_digest": text_digest(candidate.text)}
            ),
        )
        verdict = self._guard.check(submission)
        if verdict.outcome is not GateOutcome.PASS:
            return verdict
        return self._record_gate.check(candidate)


def guarded_admit(
    output: TriadOutput, lookup: RecordLookup, guard: ResubmissionGuard
) -> TriadOutput:
    """The door, with the resubmission guard in front. Raises unless it passes."""
    result = GuardedCccRecordGate(lookup, guard).check(output)
    if result.outcome is not GateOutcome.PASS:
        raise UnrecordedTriadOutput(result)
    return output

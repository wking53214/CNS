"""The retry loop for Triad output entering CNS (triad_admission).

WHY THIS EXISTS

Triad output reaches CNS through the guarded admission door. When CCC has not
recorded an item yet, the door answers RETRY, and the remedy is to hand the
session to CCC and ask again. This module is that loop.

WHO WIRES WHAT

This module imports neither Triad-42 nor CCC. The caller passes in:

- `hand_off`: a function with no arguments that records the session with CCC.
  The caller builds it from Triad-42's handoff and the CCC system it holds.
- `lookup`: CCC's record lookup, as for `ccc_admission`.
- `guard`: one ResubmissionGuard, kept for as long as the retries should be
  counted.

TERMINATION

Each retry resubmits the same text, so the guard counts it. Once the guard's
cap is reached it refuses with TERMINAL_BREACH, and this loop stops. The loop
has no separate counter, so it cannot run longer than the guard allows.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from cns.gate import GateOutcome

from .guarded_admission import guarded_admit
from .ccc_admission import RecordLookup, TriadOutput, UnrecordedTriadOutput
from .resubmission import ResubmissionGuard

__all__ = ["admit_candidates"]


def admit_candidates(
    candidates: Iterable[TriadOutput],
    hand_off: Callable[[], None],
    lookup: RecordLookup,
    guard: ResubmissionGuard,
) -> list[TriadOutput]:
    """Admit each candidate in order, handing off and retrying on RETRY.

    Returns the admitted candidates in input order. Raises UnrecordedTriadOutput
    on the first candidate refused for any reason other than RETRY, and any
    exception from `hand_off` propagates unchanged.
    """
    if not callable(hand_off):
        raise TypeError(
            f"admit_candidates needs a hand_off function; got {type(hand_off).__name__}"
        )
    admitted: list[TriadOutput] = []
    for candidate in candidates:
        while True:
            try:
                admitted.append(guarded_admit(candidate, lookup, guard))
                break
            except UnrecordedTriadOutput as refused:
                if refused.result.outcome is not GateOutcome.RETRY:
                    raise
                hand_off()
    return admitted

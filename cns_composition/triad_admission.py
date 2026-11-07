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

RECEIPTS: ADMITTED IS NOT FOREVER

`admit_candidates` returns plain items, so an item a human erased in CCC after
it was admitted kept being used: nothing asked again. `admit_with_receipts`
returns an `AdmissionReceipt` per item instead, carrying the verdict that
admitted it, and `use(receipt, lookup)` asks CCC again at the moment of use and
returns the item only if it still passes (with the same key, if one was used).
`recheck` is the same question without raising. The recheck is the guarantee;
the receipt only says what was admitted and why.

TERMINATION

Each retry resubmits the same text, so the guard counts it. Once the guard's
cap is reached it refuses with TERMINAL_BREACH, and this loop stops. The loop
has no separate counter, so it cannot run longer than the guard allows.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Optional

from cns.gate import GateOutcome, GateResult, subject_digest

from .guarded_admission import GuardedCccRecordGate
from .ccc_admission import (
    SOURCE,
    CccRecordGate,
    RecordLookup,
    TriadOutput,
    UnrecordedTriadOutput,
    text_digest,
)
from .resubmission import ResubmissionGuard

__all__ = ["AdmissionReceipt", "admit_candidates", "admit_with_receipts", "recheck", "use"]


@dataclass(frozen=True)
class AdmissionReceipt:
    """One admitted item and the verdict that admitted it. Not a permission: `use` asks CCC again."""

    output: TriadOutput
    verdict: GateResult


def _binds(receipt: AdmissionReceipt) -> bool:
    output = receipt.output
    return receipt.verdict.outcome is GateOutcome.PASS and receipt.verdict.binds(
        f"{SOURCE}:{output.candidate_id}",
        subject_digest({"source": SOURCE, "candidate_id": output.candidate_id,
                        "text_digest": text_digest(output.text)}))


def admit_with_receipts(
    candidates: Iterable[TriadOutput],
    hand_off: Callable[[], None],
    lookup: RecordLookup,
    guard: ResubmissionGuard,
    *,
    attestation_key: Optional[bytes] = None,
) -> list[AdmissionReceipt]:
    """Admit each candidate in order, handing off and retrying on RETRY, and return a receipt for each.

    Raises UnrecordedTriadOutput on the first candidate refused for any reason other than RETRY, and any
    exception from `hand_off` propagates unchanged.
    """
    if not callable(hand_off):
        raise TypeError(
            f"admit_candidates needs a hand_off function; got {type(hand_off).__name__}"
        )
    gate = GuardedCccRecordGate(lookup, guard, attestation_key=attestation_key)
    receipts: list[AdmissionReceipt] = []
    for candidate in candidates:
        while True:
            result = gate.check(candidate)
            if result.outcome is GateOutcome.PASS:
                receipts.append(AdmissionReceipt(candidate, result))
                break
            if result.outcome is not GateOutcome.RETRY:
                raise UnrecordedTriadOutput(result)
            hand_off()
    return receipts


def admit_candidates(
    candidates: Iterable[TriadOutput],
    hand_off: Callable[[], None],
    lookup: RecordLookup,
    guard: ResubmissionGuard,
    *,
    attestation_key: Optional[bytes] = None,
) -> list[TriadOutput]:
    """Admit each candidate in order, handing off and retrying on RETRY.

    Returns the admitted candidates in input order. Raises UnrecordedTriadOutput
    on the first candidate refused for any reason other than RETRY, and any
    exception from `hand_off` propagates unchanged. `admit_with_receipts` is the
    same, with a receipt per item that `use` can check again later.
    """
    return [receipt.output for receipt in admit_with_receipts(
        candidates, hand_off, lookup, guard, attestation_key=attestation_key)]


def recheck(receipt: AdmissionReceipt, lookup: RecordLookup, *,
            attestation_key: Optional[bytes] = None) -> GateResult:
    """Ask CCC again about an admitted item. A receipt whose verdict is not a PASS bound to its own item is a
    TERMINAL_BREACH without asking: it was not issued by an admission."""
    if not isinstance(receipt, AdmissionReceipt):
        raise TypeError(f"recheck takes an AdmissionReceipt; got {type(receipt).__name__}")
    gate = CccRecordGate(lookup, attestation_key=attestation_key)
    if not _binds(receipt):
        return GateResult(gate=gate.name, position=gate.position, outcome=GateOutcome.TERMINAL_BREACH,
                          reason="the receipt's verdict is not a pass bound to its own item, so it admitted nothing")
    return gate.check(receipt.output)


def use(receipt: AdmissionReceipt, lookup: RecordLookup, *, attestation_key: Optional[bytes] = None) -> TriadOutput:
    """The item, if CCC still holds it now. Raises UnrecordedTriadOutput otherwise (erased since admission, for
    example)."""
    result = recheck(receipt, lookup, attestation_key=attestation_key)
    if result.outcome is not GateOutcome.PASS:
        raise UnrecordedTriadOutput(result)
    return receipt.output

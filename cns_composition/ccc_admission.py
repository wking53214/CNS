"""CONFIDENTIAL. Trade secret of William King (wking53214). Recorded 2026-10-06.
See README.md. Do not copy, publish, vendor, or disclose.

No CCC record, no use: the door Triad output passes through to enter CNS.

WHY THIS EXISTS

The Triad governance design ("amended B") has three rules. The Triad thinks,
CCC remembers and guards, humans decide:

1. The Triad holds zero authority. That is hard-wired in Triad-42 itself.
2. No CCC record, no use. When Triad output is used inside the library, the
   integration point refuses it unless CCC has recorded it.
3. No shadow records outside CCC.

This module is rule 2, and it lives here rather than in the Triad because the
Triad must stay standalone. The integration point is the one place that knows
both sides exist.

HOW IT KEEPS RULE 3

CNS asks and CCC answers. CNS never reads CCC's store and keeps no copy of
what CCC holds: it is handed an object with one method, `status`, and asks it
one question per item. CCC ships that object (`ccc.record_status.MachineRecords`),
so only CCC knows how CCC keeps records. Nothing here caches an answer.

WHAT THE CHECK DOES

A piece of Triad output arrives as a `TriadOutput`: the candidate id the Triad
gave it and its text. The gate fingerprints the text the same way the Triad's
handoff and CCC both do (SHA-256 of the UTF-8 text) and asks CCC what it holds
for that source, id and fingerprint. The answer decides the verdict:

    held       PASS             CCC recorded exactly this text
    absent     RETRY            not recorded yet; hand the session to CCC, then
                                ask again. Blocking either way.
    altered    TERMINAL_BREACH  CCC recorded this item with different text, so
                                what arrived is not what was recorded
    erased     TERMINAL_BREACH  a human erased it; nothing brings it back
    redacted   TERMINAL_BREACH  a human redacted it
    anything   TERMINAL_BREACH  an answer this module does not recognise is
    else                        never read as permission

The gate sits at the ALPHA end: it runs before the output is used, so a
refusal means the use never starts. Its verdict is bound to what it judged
(source, candidate id and fingerprint), so it cannot be lifted onto a
different item.

Failure is loud. A missing lookup is refused when the gate is built, an
exception from CCC propagates (it is never turned into a PASS), and `admit`
raises rather than return output the gate did not pass.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

__all__ = [
    "GATE_NAME",
    "SOURCE",
    "CccRecordGate",
    "RecordLookup",
    "TriadOutput",
    "UnrecordedTriadOutput",
    "admit",
    "text_digest",
]

#: The machine identity the Triad records under in CCC (triad42.ccc_handoff).
SOURCE = "triad42"

#: The name every verdict from this gate carries.
GATE_NAME = "ccc.record_required"

_VERDICTS = {
    "held": (GateOutcome.PASS, "recorded in CCC with exactly this text"),
    "absent": (GateOutcome.RETRY,
               "no CCC record of this Triad output; hand the session to CCC, then retry"),
    "altered": (GateOutcome.TERMINAL_BREACH,
                "CCC recorded this item with different text; what arrived is not what was recorded"),
    "erased": (GateOutcome.TERMINAL_BREACH, "a human erased this item in CCC"),
    "redacted": (GateOutcome.TERMINAL_BREACH, "a human redacted this item in CCC"),
}


@runtime_checkable
class RecordLookup(Protocol):
    """The one question CNS asks CCC. `ccc.record_status.MachineRecords` answers it."""

    def status(self, source: str, candidate_id: str, text_digest: str) -> str: ...


def text_digest(text: str) -> str:
    """The fingerprint the Triad's handoff and CCC both compute for an item's text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TriadOutput:
    """One piece of Triad output asking to be used."""

    candidate_id: str
    text: str

    def __post_init__(self) -> None:
        for name in ("candidate_id", "text"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"TriadOutput.{name} must be a non-empty string")


class UnrecordedTriadOutput(RuntimeError):
    """Raised by `admit` when the gate did not pass. Carries the verdict."""

    def __init__(self, result: GateResult) -> None:
        super().__init__(f"{result.outcome.value}: {result.reason}")
        self.result = result


class CccRecordGate:
    """ALPHA gate: Triad output is refused unless CCC holds a record of it."""

    name = GATE_NAME
    position = GatePosition.ALPHA

    def __init__(self, lookup: RecordLookup) -> None:
        if not isinstance(lookup, RecordLookup):
            raise TypeError(
                "CccRecordGate needs CCC's record lookup "
                "(ccc.record_status.MachineRecords); got "
                f"{type(lookup).__name__}. Without CCC, Triad output is not used."
            )
        self._lookup = lookup

    def check(self, candidate: object) -> GateResult:
        if not isinstance(candidate, TriadOutput):
            raise TypeError(
                f"CccRecordGate judges a TriadOutput; got {type(candidate).__name__}")
        digest = text_digest(candidate.text)
        answer = self._lookup.status(SOURCE, candidate.candidate_id, digest)
        outcome, reason = _VERDICTS.get(
            answer if isinstance(answer, str) else "",
            (GateOutcome.TERMINAL_BREACH,
             f"unrecognised answer from CCC ({answer!r}); not read as permission"),
        )
        return GateResult(
            gate=GATE_NAME,
            position=GatePosition.ALPHA,
            outcome=outcome,
            reason=reason,
            subject=f"{SOURCE}:{candidate.candidate_id}",
            subject_digest=subject_digest({
                "source": SOURCE,
                "candidate_id": candidate.candidate_id,
                "text_digest": digest,
            }),
        )


def admit(output: TriadOutput, lookup: RecordLookup) -> TriadOutput:
    """The door. Returns `output` only if CCC holds it; raises otherwise."""
    result = CccRecordGate(lookup).check(output)
    if result.outcome is not GateOutcome.PASS:
        raise UnrecordedTriadOutput(result)
    return output

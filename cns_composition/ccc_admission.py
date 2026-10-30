"""No CCC record, no use: the door Triad output passes through to enter CNS.

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
    rejected   TERMINAL_BREACH  a human rejected this text
    superseded TERMINAL_BREACH  CCC holds a newer version; this text is the old one
    unattested TERMINAL_BREACH  the lookup checks the handoff's stamp, and no
                                record of this item carries a valid one
    anything   TERMINAL_BREACH  an answer this module does not recognise is
    else                        never read as permission

The gate sits at the ALPHA end: it runs before the output is used, so a
refusal means the use never starts. Its verdict is bound to what it judged
(source, candidate id and fingerprint), so it cannot be lifted onto a
different item.

Failure is loud. A missing lookup is refused when the gate is built, an
exception from CCC propagates (it is never turned into a PASS), and `admit`
raises rather than return output the gate did not pass.

CHECKING THE STAMP HERE, NOT ONLY IN THE STORE

The caller hands the gate its lookup, so a stand-in that simply answers
"held" was believed. Given `attestation_key`, the gate does not take "held" on
the store's word: it asks the lookup for the stamps the handoff wrote on the
matching records (`stamps`, which `ccc.record_status.MachineRecords` shows) and
checks one of them itself, with `handoff_stamp` and the caller's key. A store
that cannot show a stamp that verifies is a TERMINAL_BREACH, whatever it
answered. `handoff_stamp` is CCC's `attest` formula; both repositories test
against `contracts/handoff-stamp-vectors.json`, so neither can drift alone.
Whoever holds the key can stamp; this proves the handoff (or a key holder)
wrote the record, not that the text is true.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest

__all__ = [
    "GATE_NAME",
    "SOURCE",
    "CccRecordGate",
    "RecordLookup",
    "TriadOutput",
    "UnrecordedTriadOutput",
    "StampLookup",
    "admit",
    "handoff_stamp",
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
    "rejected": (GateOutcome.TERMINAL_BREACH, "a human rejected this text in CCC"),
    "superseded": (GateOutcome.TERMINAL_BREACH,
                   "CCC holds a newer version of this item; this text is the old one"),
    "unattested": (GateOutcome.TERMINAL_BREACH,
                   "no CCC record of this item carries the handoff's stamp; an unstamped record is never "
                   "read as permission"),
}


@runtime_checkable
class RecordLookup(Protocol):
    """The one question CNS asks CCC. `ccc.record_status.MachineRecords` answers it."""

    def status(self, source: str, candidate_id: str, text_digest: str) -> str: ...


@runtime_checkable
class StampLookup(Protocol):
    """A lookup that also shows the stamps the handoff wrote on the records matching one item."""

    def stamps(self, source: str, candidate_id: str, text_digest: str) -> Sequence[str]: ...


_MIN_KEY_BYTES = 16


def _require_key(key: object) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or len(key) < _MIN_KEY_BYTES:
        raise ValueError(f"attestation_key must be at least {_MIN_KEY_BYTES} bytes")
    return bytes(key)


def handoff_stamp(key: bytes, *, source: str, candidate_id: str, text_digest: str) -> str:
    """The stamp a handoff writes on a CCC record (CCC's `attest`): HMAC-SHA256, untruncated, over
    ["ccc.handoff.v1", source, candidate_id, text_digest] as compact JSON. See contracts/handoff-stamp-vectors.json."""
    message = json.dumps(["ccc.handoff.v1", source, candidate_id, text_digest], separators=(",", ":"))
    return hmac.new(_require_key(key), message.encode("utf-8"), hashlib.sha256).hexdigest()


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

    def __init__(self, lookup: RecordLookup, *, attestation_key: Optional[bytes] = None) -> None:
        if not isinstance(lookup, RecordLookup):
            raise TypeError(
                "CccRecordGate needs CCC's record lookup "
                "(ccc.record_status.MachineRecords); got "
                f"{type(lookup).__name__}. Without CCC, Triad output is not used."
            )
        if attestation_key is not None:
            _require_key(attestation_key)
            if not isinstance(lookup, StampLookup):
                raise TypeError(
                    "with an attestation_key, CccRecordGate needs a lookup that shows the handoff's stamps "
                    f"(ccc.record_status.MachineRecords.stamps); {type(lookup).__name__} does not")
        self._lookup = lookup
        self._key = attestation_key

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
        if outcome is GateOutcome.PASS and self._key is not None and not self._stamp_verifies(candidate, digest):
            outcome, reason = (GateOutcome.TERMINAL_BREACH,
                               "CCC answered held, but no stamp it shows for this item verifies under this key; "
                               "a store that cannot show the handoff's stamp is never read as permission")
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


    def _stamp_verifies(self, candidate: TriadOutput, digest: str) -> bool:
        if self._key is None:
            return False
        expected = handoff_stamp(self._key, source=SOURCE, candidate_id=candidate.candidate_id, text_digest=digest)
        shown = self._lookup.stamps(SOURCE, candidate.candidate_id, digest)  # type: ignore[attr-defined]
        if isinstance(shown, (str, bytes)) or not isinstance(shown, Sequence):
            return False
        return any(isinstance(stamp, str) and hmac.compare_digest(stamp, expected) for stamp in shown)


def admit(output: TriadOutput, lookup: RecordLookup, *, attestation_key: Optional[bytes] = None) -> TriadOutput:
    """The door. Returns `output` only if CCC holds it (and, with a key, shows a stamp that verifies); raises
    otherwise."""
    result = CccRecordGate(lookup, attestation_key=attestation_key).check(output)
    if result.outcome is not GateOutcome.PASS:
        raise UnrecordedTriadOutput(result)
    return output

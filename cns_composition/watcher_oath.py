"""watcher_oath: did the Watcher leave the run record exactly as it found it?

WHY THIS EXISTS

WATCHER_MCU reads the record Warden prints at the end of a run (`cns.run/1`) and describes it in plain words.
Its whole claim is that it describes and never grades: it cannot touch a verdict, a finding, a file or a
baseline. The Watcher enforces that on its own side, by dropping any sentence the record does not back. A
claim made only from inside is a claim its author checks. This is the other side's check: CNS takes the record
that went in and the record as it stands once the Watcher has finished, and says whether they are the same.

WHAT IT CHECKS

Both must read as a `cns.run.RunRecord`, and their digests (`cns.gate.subject_digest`, over the whole object, so
an extra field a Watcher added counts too) must be identical. It is an OMEGA gate: it judges what a narration
run left behind. The verdict is bound to the record that went in.

  PASS             the record is unchanged.
  TERMINAL_BREACH  the record changed, is not a run record, or cannot be described for binding. A changed
                   record is a Watcher that interfered; there is no retry that makes it not have.

It judges nothing the Watcher wrote. The account is the Watcher's own, checked by its own oath. CNS imports no
repository: the two records are handed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest
from cns.run import RunRecord

__all__ = ["Narration", "WatcherLeftRecordAlone"]

_SUBJECT = "watcher_narration"


@dataclass(frozen=True)
class Narration:
    """What a narration run left behind: the record handed to the Watcher, and the same record read again after."""

    before: Mapping[str, Any]
    after: Mapping[str, Any]


class WatcherLeftRecordAlone:
    """An OMEGA gate: PASS only if the Watcher left the run record byte for byte as it found it."""

    name = "watcher_mcu.record_untouched"
    position = GatePosition.OMEGA

    def _result(self, outcome: GateOutcome, reason: str, digest: str = "") -> GateResult:
        return GateResult(gate=self.name, position=self.position, outcome=outcome, reason=reason,
                          subject=_SUBJECT, subject_digest=digest)

    def check(self, candidate: object) -> GateResult:
        if not isinstance(candidate, Narration):
            return self._result(GateOutcome.TERMINAL_BREACH,
                                f"the candidate is a {type(candidate).__name__}, not a Narration; nothing was judged")
        try:
            RunRecord.from_dict(candidate.before)
        except ValueError as exc:
            return self._result(GateOutcome.TERMINAL_BREACH,
                                f"the record handed to the Watcher is not a run record ({exc}); nothing to compare")
        try:
            before = subject_digest(candidate.before)
        except TypeError as exc:
            return self._result(GateOutcome.TERMINAL_BREACH, f"the record cannot be described for binding ({exc})")
        try:
            RunRecord.from_dict(candidate.after)
            after = subject_digest(candidate.after)
        except (ValueError, TypeError) as exc:
            return self._result(GateOutcome.TERMINAL_BREACH,
                                f"after the Watcher the record no longer reads as a run record ({exc})", before)
        if after != before:
            return self._result(GateOutcome.TERMINAL_BREACH,
                                "the run record changed while the Watcher had it; the Watcher is sworn not to interfere",
                                before)
        return self._result(GateOutcome.PASS, "the run record is exactly as it was handed to the Watcher", before)

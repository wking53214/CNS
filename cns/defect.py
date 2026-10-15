"""cns.defect: one defect a scanner reported, as the governor and the drafter read it.

WHY THIS EXISTS

A defect crosses repositories: Ghost Tools reports it, Warden carries it through the loop,
the Drafter proposes a fix for it, and Burnish reports what remains. Each of them has to
agree on what a defect is, including the identity that lets a finding be recognised across
runs. That agreement is a row shape, so it lives here.

WHAT IT CARRIES

`Defect` is the row, `DefectSeverity` and `DefectLifecycle` are its enums, and `identity` is
a pure function of the row: the scanner's own identifier when it gave one, otherwise the
human label, otherwise the summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from cns.epistemic import EpistemicState
from cns.rowenum import RowEnum

__all__ = ["DefectSeverity", "DefectLifecycle", "Defect"]


class DefectSeverity(RowEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DefectLifecycle(RowEnum):
    IDENTIFIED = "identified"
    PROPOSED = "proposed"
    AUTHORIZED = "authorized"
    MODIFIED = "modified"
    TESTED = "tested"
    ADVERSARIALLY_TESTED = "adversarially_tested"
    FIXED = "fixed"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@dataclass
class Defect:
    """One architectural or documentary defect."""

    summary: str
    severity: DefectSeverity
    lifecycle: DefectLifecycle = DefectLifecycle.IDENTIFIED
    ghost_id: Optional[str] = None
    human_id: Optional[str] = None
    evidence: Tuple[str, ...] = ()
    file: Optional[str] = None
    epistemic: EpistemicState = EpistemicState.UNKNOWN
    ghost_status: Optional[str] = None
    #: What the scanner said, verbatim, so a drafter can act on its facts.
    detector: Optional[str] = None
    line: Optional[int] = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        return self.ghost_id or self.human_id or self.summary

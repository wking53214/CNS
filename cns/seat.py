"""cns.seat: the rows the governor hands to the seats and the seats return.

WHY THIS EXISTS

The governor runs three seats: a drafter that proposes changes, a finisher that writes the
prose, and a judge that decides. Each seat is a separate repository, and each reads what the
governor measured and returns what it decided. Those rows are the contract between them. A
seat that reads a different `Evidence` from the one the governor writes is a seat that can
be fooled, so the rows live here, not in whichever repository happens to own the governor.

WHAT IT CARRIES

`FileEdit`, `Facts`, `Evidence` and `Verdict`: frozen rows with no methods. The governor's
behaviour (applying edits, running suites, calling the seats) stays in the governor. Warden
and the judge agree on these fields by importing them from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from cns.defect import Defect
from cns.suite import SuiteRun

__all__ = ["FileEdit", "Facts", "Evidence", "Verdict"]


@dataclass(frozen=True)
class FileEdit:
    path: str
    kind: str  # "replace" | "write" | "delete"
    new: str
    old: str = ""
    replace_all: bool = False


@dataclass(frozen=True)
class Facts:
    """What the governor and the scanner measured at the converged state, handed to the finisher."""

    #: The target's own suite, run by the governor after the loop. None: it was not run.
    suite: Optional[SuiteRun]
    #: What the scanner still reports. Converged means no proposals are left, not that this is empty.
    remaining: Tuple[Defect, ...]
    #: How many loop cycles ran.
    cycles: int
    #: Checks that did not run ("ghost", "swizzle", "suite").
    unmeasured: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    """Everything a judge may rely on, measured by someone other than the judge.

    The governor assembles it. The scanner, the suite and the attacker produced the numbers.
    None means "not measured", which is never the same as "fine".
    """

    target: str
    #: The human grant's scope: "documentation" or "code".
    scope: str
    #: (cycle number, outcome) for every cycle that ran.
    cycles: Tuple[Tuple[int, str], ...]
    #: (path, kind) of every edit that was actually applied, finishing included.
    changed: Tuple[Tuple[str, str], ...]
    #: Of those, the paths that decide acceptability (tests, test config, CI).
    judging_files_touched: Tuple[str, ...]
    suite_before: Optional[SuiteRun]
    suite_after: Optional[SuiteRun]
    #: Scanner finding identities at the start and at the end. None: the scanner never ran.
    ghost_before: Optional[Tuple[str, ...]]
    ghost_after: Optional[Tuple[str, ...]]
    #: Finding id -> the scanner's own severity word (Ghost: critical, major, minor, informational).
    #: None means the writer did not say. Added in 2.1.0; the bare ids stay in ghost_before and ghost_after.
    #: Keyword-only, so it can sit here beside the ids it describes without moving any positional field.
    ghost_severity: Optional[Mapping[str, str]] = field(default=None, kw_only=True)
    #: Removals that failed a test and were left in place.
    declined: Tuple[str, ...]
    #: True: the attacker's own proofs held. False: they did not. None: not run.
    swizzle_proofs: Optional[bool]
    #: The attacks on the governor, as reported ({scenario, severity, status}). None: not run.
    attacks: Optional[Tuple[Mapping[str, str], ...]]
    #: Checks that never ran, by name.
    unmeasured: Tuple[str, ...]
    notes: Tuple[str, ...] = field(default=())
    #: The scanner graded against the answer key. None: not run.
    assay: Optional[Mapping[str, object]] = None
    ghost_baseline_before: Optional[Mapping[str, object]] = None
    ghost_baseline_after: Optional[Mapping[str, object]] = None
    #: True: the finisher was called after the loop converged. False: it was not. None: the governor did
    #: not say (a governor older than this field). Added in 2.0.0 because a converged run ends on
    #: NOTHING_TO_PROPOSE whether or not a finisher then edited files, so without this the judge cannot
    #: tell a finishing edit from a fabricated one; JUDGE 0.4.8 records that limit in its own docstring.
    finisher_ran: Optional[bool] = None


@dataclass(frozen=True)
class Verdict:
    """The judge's decision. ACCEPT, REJECT, or INSUFFICIENT (cannot decide on this evidence)."""

    decision: str
    reasons: Tuple[str, ...]
    judge: str = ""

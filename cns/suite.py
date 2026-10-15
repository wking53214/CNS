"""cns.suite: what one run of a target's test suite reported.

WHY THIS EXISTS

The governor measures the target's suite before and after every change, and the judge
reads both results. Those results cross repositories: Warden writes them, the Judge and
the Finisher read them. This is the row they share.

WHAT IT CARRIES

`SuiteRun` is the counts pytest reported, the exit status, and two pure functions of
those counts: `green` says whether the suite can be trusted to protect behaviour, and
`describe` says it in plain words. Running the suite is I/O and stays in the governor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["SuiteRun"]


@dataclass(frozen=True)
class SuiteRun:
    """One run of a target's suite, as pytest reported it."""

    ran: bool
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    reason: str = ""
    #: Tests marked as expected to fail that did fail, and ones that passed anyway.
    xfailed: int = 0
    xpassed: int = 0
    #: pytest's own exit status. None only for a SuiteRun made by hand. Green needs 0.
    exit_code: Optional[int] = None

    @property
    def green(self) -> bool:
        return (self.ran and self.exit_code in (None, 0)
                and self.passed > 0 and self.failed == 0 and self.errors == 0)

    def describe(self) -> str:
        if not self.ran:
            return f"did not run ({self.reason})"
        text = (f"{self.passed} passed, {self.failed} failed, {self.errors} errors, "
                f"{self.skipped} skipped, {self.xfailed} xfailed, {self.xpassed} xpassed")
        if self.exit_code not in (None, 0):
            text += f"; pytest exited {self.exit_code}" + (f" ({self.reason})" if self.reason else "")
        return text

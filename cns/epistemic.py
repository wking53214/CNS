"""cns.epistemic: the vocabulary for what kind of claim a finding makes.

WHY THIS EXISTS

A finding is only as useful as its claim is honest. "Guaranteed" and "assumed" mean
different things, and the governor, the scanner and the finisher all have to read the same
word the same way. A claim's state is a contract about the kind of evidence behind it, not
a confidence score, so it is a row shape the repositories share rather than a convention.

WHAT IT CARRIES

`EpistemicState`, the states a claim may be in. Each member is a value, not a number, and
none of them ranks above another.
"""

from __future__ import annotations

from cns.rowenum import RowEnum

__all__ = ["EpistemicState"]


class EpistemicState(RowEnum):
    """What kind of claim is being made."""

    GUARANTEED = "guaranteed"
    VERIFIED = "verified"
    IMPLEMENTED = "implemented"
    DESIGNED = "designed"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"
    NOT_IMPLEMENTED = "not_implemented"
    INTENTIONALLY_NOT_PROVIDED = "intentionally_not_provided"

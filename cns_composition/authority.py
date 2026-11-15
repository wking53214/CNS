"""authority: HERALD's words for where a claim came from, read as `cns.authority.AuthorityKind` (CNS-103).

Two vocabularies, both HERALD's, taken as text so CNS imports no repository: the reading of a claim (how it was got
from the text) and the standing of a source (what kind of thing the text is). Anything unrecognised, in any letter
case other than the exact one, is UNKNOWN, never human: a misspelt HUMAN_CONFIRMED must not become a sign-off.
"""

from __future__ import annotations

from cns.authority import AuthorityKind

__all__ = ["of_herald_reading", "of_herald_standing"]

_READINGS = {
    "HUMAN_CONFIRMED": AuthorityKind.HUMAN_SIGNOFF,
    "EXTRACTED": AuthorityKind.MACHINE_READING,
    "INFERRED": AuthorityKind.MACHINE_READING,
}
_STANDINGS = {
    "record": AuthorityKind.RECORD,
    "attestation": AuthorityKind.ATTESTATION,
    "derived": AuthorityKind.DERIVED,
    "unknown": AuthorityKind.UNKNOWN,
}


def of_herald_reading(reading: object) -> AuthorityKind:
    """HERALD's reading of a claim (EXTRACTED, INFERRED, HUMAN_CONFIRMED) as an authority kind; UNKNOWN otherwise."""
    return _READINGS.get(reading, AuthorityKind.UNKNOWN) if isinstance(reading, str) else AuthorityKind.UNKNOWN


def of_herald_standing(standing: object) -> AuthorityKind:
    """HERALD's standing of a source (record, attestation, derived, unknown) as an authority kind; UNKNOWN otherwise."""
    return _STANDINGS.get(standing, AuthorityKind.UNKNOWN) if isinstance(standing, str) else AuthorityKind.UNKNOWN

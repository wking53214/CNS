"""authority: what a statement rests on, named so a person's judgement is never confused with a machine's.

The repositories already draw this line in their own words. HERALD reads a claim as EXTRACTED or INFERRED (a
machine's reading) or HUMAN_CONFIRMED (a named person confirmed it), and labels a source's standing as record,
attestation, derived or unknown; TIE takes the machine readings as evidence and the confirmations as sign-off, and
never the one for the other. This is that vocabulary as one shared shape, so a statement crossing a boundary can say
which kind of authority it carries. Reading another repository's words into it is behaviour and lives in
`cns_composition.authority`.
"""

from __future__ import annotations

from .rowenum import RowEnum

__all__ = ["AuthorityKind"]


class AuthorityKind(RowEnum):
    """What a statement rests on.

    HUMAN_SIGNOFF is the only kind that is a person's judgement, and nothing is
    ever promoted to it: a statement that does not say, or says something
    unrecognised, is UNKNOWN, which is never read as human.
    """

    HUMAN_SIGNOFF = 'human_signoff'      # a named person confirmed it (HERALD HUMAN_CONFIRMED)
    MACHINE_READING = 'machine_reading'  # a model or parser read it (HERALD EXTRACTED, INFERRED)
    RECORD = 'record'                    # a system of record holds it (HERALD standing "record")
    ATTESTATION = 'attestation'          # a party asserts it; truth not established (HERALD standing "attestation")
    DERIVED = 'derived'                  # another system computed it (HERALD standing "derived")
    UNKNOWN = 'unknown'                  # not declared, or not recognised

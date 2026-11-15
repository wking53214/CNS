"""digest_ref: reading and checking a subject digest that names its encoding (CNS-101).

`cns.gate.DigestRef` is the shape: the digest and the name of the encoding it was made with (`cns-digest/1`). This
module is what is done with one: make it from content, read it from text, and check it against content.

A bare 64-hex digest, the only form written before this, reads as `cns-digest/1`, so nothing already recorded needs
rewriting. A digest naming any other encoding is never checked as if it were this one: `matches` says False, because
a fingerprint whose recipe CNS does not know proves nothing about the content.
"""

from __future__ import annotations

import dataclasses
import hmac
import re

from cns.gate import DigestRef, subject_digest

__all__ = ["DIGEST_VERSION", "matches", "parse", "ref_of"]

#: The encoding `subject_digest` implements, read from the one place it is written: `DigestRef.version`'s default.
DIGEST_VERSION: str = next(f.default for f in dataclasses.fields(DigestRef) if f.name == "version")  # type: ignore[assignment]

_HEX = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"[a-z][a-z0-9.-]*/[0-9]+")


def ref_of(content: object) -> DigestRef:
    """The digest of `content` under the current encoding, with the encoding named."""
    return DigestRef(subject_digest(content))  # type: ignore[arg-type]


def parse(text: str) -> DigestRef:
    """A `DigestRef` from `version:value`, or from a bare digest (read as the current encoding). ValueError for
    anything else: a digest that cannot be read is not a digest of anything."""
    if not isinstance(text, str):
        raise ValueError(f"a digest reference is text; got {type(text).__name__}")
    if _HEX.fullmatch(text):
        return DigestRef(text)
    version, sep, value = text.rpartition(":")
    if not sep or not _VERSION.fullmatch(version) or not _HEX.fullmatch(value):
        raise ValueError(f"not a digest reference: {text[:80]!r} (expected 64 lower-case hex, or version:hex)")
    return DigestRef(value, version)


def matches(ref: DigestRef, content: object) -> bool:
    """Whether `ref` is the digest of `content`. False for an encoding this CNS does not implement."""
    if not isinstance(ref, DigestRef) or ref.version != DIGEST_VERSION:
        return False
    return hmac.compare_digest(ref.value, subject_digest(content))  # type: ignore[arg-type]

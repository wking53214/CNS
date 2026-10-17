"""fallback_parity: does a repository's own copy of the digest agree with CNS's?

WHY THIS EXISTS

`cns.gate.subject_digest` is the one definition of "what this verdict was bound to", and it is shared so that two
repositories can check each other's verdicts. A repository that works without CNS installed has to carry its
own stand-in for when CNS is absent. composition-engine does: its `cns_integration` falls back to a local
`subject_digest`. A stand-in that digests differently is worse than none: a verdict bound without CNS never
verifies with CNS, and nothing says so until two repositories disagree. Measured on 2026-10-17, composition-engine's
fallback agreed with CNS on none of seven sample mappings (it hashes JSON; CNS hashes a length-prefixed encoding).

WHAT IT DOES

`digest_parity(repo, fn)` runs the repository's function and CNS's on the same fixed samples and reports every
one on which they differ, including a function that raises or returns something that is not text. It is the
check each repository can put in its own tests against its own fallback, and the check CNS runs when it is
handed the function. CNS imports no repository: the function is handed in.

WHAT IT DOES NOT DO

It does not decide that a fallback is wrong to exist, and it does not fix one. It says on which samples they
differ, so the owner can.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Tuple

from cns.gate import subject_digest

__all__ = ["COPIES", "SAMPLES", "Parity", "digest_parity"]

#: Repositories known to carry their own copy of `subject_digest`, and where.
COPIES: Mapping[str, str] = {
    "composition-engine": "the fallback subject_digest in cns_integration, used when CNS is not installed",
}

#: Mappings every copy must digest exactly as CNS does. Each probes something a shortcut gets wrong.
SAMPLES: Tuple[Mapping[str, Any], ...] = (
    {},
    {"a": 1},
    {"a": "b", "n": None},
    {"b": 1, "a": 2},                 # key order must not matter
    {"ab": "c"},
    {"a": "bc"},                      # the pair a separator-based encoding confuses
    {"v": True},
    {"v": 1},                         # a bool is not the int 1
    {"x": [1, 2, {"y": [True, None]}]},
    {"u": "café ✓"},
    {"f": 1.5},
    {"z": 0.0},
    {"z": -0.0},                      # equal to 0.0, so it digests the same
    {"big": 12345678901234567890},
)


@dataclass(frozen=True)
class Parity:
    repo: str
    checked: int
    differing: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.differing


def digest_parity(repo: str, fn: Callable[[Mapping[str, Any]], str]) -> Parity:
    """Compare `fn` with `cns.gate.subject_digest` on every sample. Raises KeyError for a repository not in COPIES."""
    if repo not in COPIES:
        raise KeyError(f"{repo!r} is not a repository known to carry its own subject_digest; add it to COPIES first")
    differing = []
    for sample in SAMPLES:
        want = subject_digest(sample)
        try:
            got = fn(sample)
        except Exception as exc:  # a copy that raises on ordinary content disagrees, whatever it raised
            differing.append(f"{sample!r}: raised {type(exc).__name__}")
            continue
        if not isinstance(got, str):
            differing.append(f"{sample!r}: returned {type(got).__name__}, not text")
        elif got != want:
            differing.append(f"{sample!r}: {got[:12]} not {want[:12]}")
    return Parity(repo, len(SAMPLES), tuple(differing))

"""spine_trace: does one run of the decision spine hang together, stage to stage?

WHY THIS EXISTS

The decision spine is four small repositories that never import each other's outputs as a whole:
interconnected_alpha detects Keys, interconnected_zeta evaluates Locks over them, interconnected_beta
turns lock states into a Decision, interconnected_delta records the Decision in a hash-chained ledger.
Each now offers a CNS binding for its own output (a digest of exactly what it produced), and each is
tested alone. Nothing checked the seams: that the Decision cites only Keys that were detected, only
Locks that were evaluated, belongs to the entity the run was about, and is the Decision the ledger recorded.
delta even carries its own copy of how a Decision is described for binding, because beta's was not
available to it when it was written, so the two descriptions could drift apart unnoticed.

This is the check of the seams. The caller (CNS imports no repository) reads four small facts and four
digests off the real objects, in the order the spine runs, and hands them over as a `SpineRecord`.
`problems` says what does not hang together. `root` is one digest over the whole run, so a single
verdict can be bound to the run and not to one stage of it.

WHAT IT CHECKS

  - every digest is a full SHA-256 and the four stages are bound to different things;
  - alpha, zeta and beta agree about one entity (beta names it; alpha and zeta results do not carry it,
    so the caller states it once);
  - the Decision's keys are a subset of the Keys alpha detected as present;
  - the Decision's locks are a subset of the Locks zeta evaluated, and every open Lock is one zeta evaluated.
    A Decision cites the Locks its rule required, and a rule may require a Lock to be CLOSED (a discharge
    rests on the absence of trouble), so "open" is not the test; "evaluated" is;
  - beta's digest of the Decision equals delta's digest of the Decision it recorded.

WHAT IT DOES NOT CHECK

That the Decision is the right one (that is beta's rules), or that a Lock should have opened (zeta's), or
that the ledger chain verifies (delta's own `verify_chain_integrity`). It checks that the stages describe
one run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Mapping, Tuple

from cns.gate import subject_digest

__all__ = ["SPINE", "SpineRecord", "problems", "root"]

#: The repositories of the spine, in the order a run passes through them, and the package each ships.
SPINE: Mapping[str, str] = {
    "interconnected_alpha": "alpha",
    "interconnected_zeta": "zeta",
    "interconnected_beta": "beta",
    "interconnected_delta": "delta",
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SpineRecord:
    """What the four stages say about one run. Digests are each repository's own `*_digest`."""

    entity_id: str
    # interconnected_alpha
    keyset_digest: str
    keys_present: Tuple[str, ...]
    # interconnected_zeta: lock id -> digest of that lock's result
    lock_result_digests: Mapping[str, str]
    open_locks: Tuple[str, ...]
    # interconnected_beta
    decision_entity_id: str
    decision_keys: Tuple[str, ...]
    decision_locks: Tuple[str, ...]
    decision_digest: str
    # interconnected_delta: the digest of the Decision part of the entry, and of the whole entry
    ledger_decision_digest: str
    entry_digest: str


def problems(record: SpineRecord) -> List[str]:
    """Everything in `record` that does not hang together. Empty when the stages describe one run."""
    out: List[str] = []
    digests = {
        "alpha keyset": record.keyset_digest,
        "beta decision": record.decision_digest,
        "delta ledger decision": record.ledger_decision_digest,
        "delta ledger entry": record.entry_digest,
    }
    for lock_id, digest in record.lock_result_digests.items():
        digests[f"zeta lock {lock_id}"] = digest
    for name, digest in digests.items():
        if not isinstance(digest, str) or not _SHA256.match(digest):
            out.append(f"{name} digest is not a full SHA-256")
    if not record.lock_result_digests:
        out.append("zeta evaluated no lock, so the Decision has nothing to rest on")
    stage_digests = [record.keyset_digest, record.decision_digest, record.entry_digest]
    if len(set(stage_digests)) != len(stage_digests):
        out.append("two stages are bound to the same digest; each stage must be bound to its own output")
    if not record.entity_id or record.entity_id != record.decision_entity_id:
        out.append(f"the run is about {record.entity_id!r} but the Decision is about {record.decision_entity_id!r}")
    absent = sorted(set(record.decision_keys) - set(record.keys_present))
    if absent:
        out.append(f"the Decision cites key(s) alpha did not detect as present: {', '.join(absent)}")
    unevaluated = sorted(set(record.decision_locks) - set(record.lock_result_digests))
    if unevaluated:
        out.append(f"the Decision cites lock(s) zeta never evaluated: {', '.join(unevaluated)}")
    unknown = sorted(set(record.open_locks) - set(record.lock_result_digests))
    if unknown:
        out.append(f"zeta reports open lock(s) it has no result for: {', '.join(unknown)}")
    if record.decision_digest != record.ledger_decision_digest:
        out.append("beta's digest of the Decision differs from delta's digest of the Decision it recorded; "
                   "the two descriptions have drifted apart, or the ledger recorded a different Decision")
    return out


def root(record: SpineRecord) -> str:
    """One digest over the whole run. Raises ValueError if the stages do not hang together."""
    found = problems(record)
    if found:
        raise ValueError("the spine run does not hang together: " + "; ".join(found))
    return subject_digest({
        "entity": record.entity_id,
        "alpha": record.keyset_digest,
        "zeta": dict(record.lock_result_digests),
        "beta": record.decision_digest,
        "delta": record.entry_digest,
    })

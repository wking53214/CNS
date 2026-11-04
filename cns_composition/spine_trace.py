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

WHAT `problems` CANNOT SEE, AND `verify` ADDS

`problems` compares values a caller typed. Nothing ties a typed fact to the digest next to it, so a record with
forged facts and genuine digests has the genuine root. `verify` takes the content each stage digested (the
`*_content` function of its connector), recomputes every digest from it, reads the facts off the content instead of
the caller, requires each lock result to name the entity, requires the ledger entry to hold exactly the Decision beta
decided, flags a stale lock result, and refuses a ledger chain nobody checked. `verified_root` is `root` after that.
It adds a check and moves no root.

It still does not see that a stage consumed its predecessor's real output (no stage records the digest of the input it
was given), or that beta's rule for the locks was followed (the rule is not in the Decision's content). Those are the
stages' to record. A successful trace is not proof that any stage's own rules were right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional, Tuple

from cns.gate import subject_digest

__all__ = ["SPINE", "SpineContents", "SpineRecord", "problems", "root", "verified_root", "verify"]

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
    for field in ("keys_present", "open_locks", "decision_keys", "decision_locks"):
        value = getattr(record, field)
        if not isinstance(value, (tuple, list)) or any(not isinstance(v, str) for v in value):
            out.append(f"{field} must be a tuple of names, not {type(value).__name__}")
    if out:
        return out  # the set arithmetic below would read a bare string as its letters
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
    stage_digests = [record.keyset_digest, record.decision_digest, record.entry_digest,
                     *record.lock_result_digests.values()]
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


@dataclass(frozen=True)
class SpineContents:
    """What each stage digested, as that stage's own connector returns it, so `verify` can recompute the digests.

    `keyset` is `alpha.cns_connector.keyset_content`, `lock_results` maps each lock id to
    `zeta.cns_connector.lock_result_content(result, entity_id=...)`, `decision` is `beta.cns_connector.decision_content`
    and `entry` is `delta.cns_connector.entry_content`. `ledger_chain_verified` is what the caller read from delta: True
    only if `verify_chain_integrity()` held and the recorded entry is the chain head. CNS imports no repository, so
    that one is a fact the caller states; left at its default it is a problem, never a pass.
    """

    keyset: Mapping[str, Any]
    lock_results: Mapping[str, Mapping[str, Any]]
    decision: Mapping[str, Any]
    entry: Mapping[str, Any]
    ledger_chain_verified: bool = False


def _digest(content: object, what: str, out: List[str]) -> Optional[str]:
    try:
        return subject_digest(content)  # type: ignore[arg-type]
    except (TypeError, ValueError, AttributeError) as exc:
        out.append(f"{what}: the content cannot be digested ({type(exc).__name__})")
        return None


def _names(rows: object, flag: str) -> Optional[List[str]]:
    if not isinstance(rows, (list, tuple)) or any(not isinstance(r, Mapping) for r in rows):
        return None
    return sorted(str(r.get("name")) for r in rows if r.get(flag) is True)


def verify(record: SpineRecord, contents: SpineContents, *, expected_locks: Optional[Iterable[str]] = None) -> List[str]:
    """Everything `problems` names, and everything the stages' own content says is not so. Empty when it all holds.

    `expected_locks`, when given, is the set of locks the application's own lock registry holds: zeta must have
    evaluated exactly those, so a lock dropped from the run (or invented) is named."""
    out = problems(record)
    keyset, decision, entry = contents.keyset, contents.decision, contents.entry
    locks = contents.lock_results
    if not (isinstance(keyset, Mapping) and keyset and isinstance(decision, Mapping) and decision
            and isinstance(entry, Mapping) and entry and isinstance(locks, Mapping) and locks):
        out.append("a stage has no content: alpha, zeta, beta and delta must each supply what they digested")
        return out

    if _digest(keyset, "alpha", out) != record.keyset_digest:
        out.append("alpha: the digest is not the digest of the content supplied for it")
    if _digest(decision, "beta", out) != record.decision_digest:
        out.append("beta: the digest is not the digest of the content supplied for it")
    if _digest(entry, "delta", out) != record.entry_digest:
        out.append("delta: the digest is not the digest of the content supplied for it")
    recorded = entry.get("decision")
    if _digest(recorded, "delta's recorded decision", out) != record.ledger_decision_digest:
        out.append("delta: the recorded Decision's digest is not the digest of the content supplied for it")
    if recorded != decision:
        out.append("delta recorded a different Decision than beta decided: the entry's Decision content is not beta's")

    present = _names(keyset.get("keys"), "present")
    if present is None:
        out.append("alpha: the content holds no keys to read")
    else:
        if sorted(record.keys_present) != present:
            out.append("keys_present is not the keys alpha's content shows present: "
                       f"{', '.join(sorted(record.keys_present)) or 'none'} against {', '.join(present) or 'none'}")
        names = [str(r.get("name")) for r in list(keyset.get("keys") or [])]
        if len(set(names)) != len(names):
            out.append("alpha's content names a key twice, so which one counts is not settled")

    if set(locks) != set(record.lock_result_digests):
        out.append("zeta: the lock content supplied is not for the locks the record holds digests for")
    opened = sorted(i for i, c in locks.items() if isinstance(c, Mapping) and c.get("open") is True)
    if sorted(record.open_locks) != opened:
        out.append("open locks are not the ones zeta's content shows open: "
                   f"{', '.join(sorted(record.open_locks)) or 'none'} against {', '.join(opened) or 'none'}")
    for lock_id, content in sorted(locks.items()):
        if not isinstance(content, Mapping):
            out.append(f"zeta lock {lock_id}: no content")
            continue
        if _digest(content, f"zeta lock {lock_id}", out) != record.lock_result_digests.get(lock_id):
            out.append(f"zeta lock {lock_id}: the digest is not the digest of the content supplied for it")
        if content.get("lock_id") != lock_id:
            out.append(f"zeta lock {lock_id}: the content names lock {content.get('lock_id')!r}")
        who = content.get("entity_id")
        if not who:
            out.append(f"zeta lock {lock_id}: digested without an entity, so it cannot be tied to {record.entity_id!r}")
        elif who != record.entity_id:
            out.append(f"zeta lock {lock_id}: evaluated for {who!r}, not for {record.entity_id!r}")
        if content.get("stale") is True:
            out.append(f"zeta lock {lock_id}: its result is stale (the observation was refused), so a Decision "
                       "over it rests on nothing current")

    if decision.get("entity_id") != record.decision_entity_id:
        out.append(f"the Decision's content is about {decision.get('entity_id')!r}, not "
                   f"{record.decision_entity_id!r}")
    for field, typed in (("triggered_by_keys", record.decision_keys), ("triggered_by_locks", record.decision_locks)):
        if decision.get(field) != sorted(typed):
            out.append(f"the Decision's {field} is not what the record says: {decision.get(field)!r}")

    if expected_locks is not None:
        want, have = set(expected_locks), set(locks)
        for lock_id in sorted(want - have):
            out.append(f"zeta never evaluated {lock_id}, which the application's lock registry holds")
        for lock_id in sorted(have - want):
            out.append(f"zeta evaluated {lock_id}, which the application's lock registry does not hold")

    if contents.ledger_chain_verified is not True:
        out.append("the ledger chain was not shown to verify (delta's verify_chain_integrity, with the recorded entry "
                   "as the chain head), so the entry may not belong to the chain")
    return out


def verified_root(record: SpineRecord, contents: SpineContents, *,
                  expected_locks: Optional[Iterable[str]] = None) -> str:
    """`root`, after `verify`. Raises ValueError if the stages' content does not back the record."""
    found = verify(record, contents, expected_locks=expected_locks)
    if found:
        raise ValueError("the spine run does not hang together: " + "; ".join(found))
    return root(record)

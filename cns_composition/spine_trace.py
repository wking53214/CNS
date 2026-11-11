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

STRICT VERIFICATION (`strict_problems`, `strict_root`)

`problems` trusts what the caller read off the objects: digests and summaries it never recomputes. A caller can
hand it a set that agrees with itself and describes nothing, and it issues a root. The strict check takes each
stage's CONTENT (the plain mapping its connector produces: `keyset_content`, `lock_result_content`,
`decision_content`, `entry_content`, each called with a pipeline context), recomputes every digest itself, and
requires:

  - every stage carries a pipeline context (`CONTEXT_SCHEMA`: schema, entity_id, event_id, run_id) and all of
    them are the same: one subject, one event, one run;
  - zeta's results and beta's Decision each name the digest of alpha's KeySet content, beta names the digest of
    each of zeta's lock-result contents (exactly those, none missing or extra), and delta names the digest of
    beta's Decision content, whose fields its own embedded copy must equal;
  - the Decision cites only Keys alpha listed as present (`present_names`, which alpha states so that CNS never
    re-implements zeta's confidence rule) and only Locks zeta evaluated;
  - delta's entry was recorded under that run and event;
  - beta's Decision and delta's embedded copy of it both carry a `content_fingerprint` (a full lowercase SHA-256): the
    legacy form, with none, is refused here only (the lenient `problems` and `root` are unchanged), because a Decision
    whose fingerprint was blanked has lost the claim that its fields were not edited. The fingerprint is compared as
    carried and never recomputed;
  - a ledger receipt (`chain=`, what `delta.cns_connector.verification_receipt` returns after delta's own chain check and a
    check against a checkpoint held outside the ledger) that is for exactly the delta content given and the run's context,
    read once, with exactly its ten plain-str keys and exact types, its entry_hash and previous_hash equal to the delta
    content's, `0 <= index < checkpoint_length <= ledger_length`, the ledger head equal to the entry's hash when the entry is
    the last, and the checkpoint head equal to the ledger head when the checkpoint covers the whole ledger. The receipt is
    not signed: a forger who writes a consistent one passes. The old `chain_verified` boolean is a deprecated alias and
    never counts.

When alpha content carries an `origin` (source, producer, observed_at, collection_context, transformation) it is checked
for well-formedness and for `observed_at` not being later than the Decision's timestamp, and for nothing else: these are
the producer's own claims, and CNS makes no authenticity, authorization or truthfulness claim about them.

A missing field is a problem, not a skip. Content that cannot be digested or read is a problem, not an exception.

WHAT STRICT DOES NOT PROVE (recorded as facts in `chains/spine_run.py`, scenarios marked GAP)

It verifies that the supplied contents AGREE with each other, chain by digest, and sit behind a receipt that fits them. It
does not prove where they came from. The recorded limits:

  - No authorship key. Four contents made up by someone who recomputes every digest and fingerprint (zeta's rule, beta's
    `decision_fingerprint` and `content_fingerprint`, all public and keyless) and writes a consistent, unsigned ledger
    receipt pass. A receipt and a fingerprint detect mistakes and partial edits, not an author.
  - `LockResult` fields (`keyset_fingerprint`, `stale`, `entity_id`) are caller-settable, and an empty `entity_id` is
    accepted as legacy, so a lock result built by hand says whatever it likes.
  - A receipt written by hand over real contents, with no ledger behind it, passes if its fields fit one another (an
    index of 4 in a ledger of 9 whose checkpoint head is the ledger head, say): nothing signs it.
  - Checkpoint custody and durability are not implemented here: delta's ledger is in memory, and a checkpoint is only as
    good as the place its holder keeps it. A ledger's sink runs before the ledger changes, so a sink's own store can keep a
    write the ledger does not have; delta's contract is an idempotent sink and a caller who reconciles.
  - `content_fingerprint` is keyless: it catches an edit that forgets to recompute it.
  - `origin` is the producer's own claim: CNS checks its form and order, not who made it or whether it is true.
  - A Decision records the union of the locks its rule cited, so one citing a closed lock passes.
  - Without `keyset_fingerprint_of`, alpha's fingerprint string is compared and never recomputed.

CNS reads fields by their documented names and applies no decision policy: it does not say which Key should be
present, which Lock should open, or whether the Decision is right. `strict_root` is domain-separated
(`TRACE_SCHEMA`), so it can never equal a lenient `root`, and it is never a native digest of any stage.
"""

from __future__ import annotations

import re
import threading
import types
import warnings
import weakref
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from cns.gate import subject_digest

__all__ = [
    "CONTEXT_SCHEMA",
    "SPINE",
    "SpineRecord",
    "RECEIPT_SCHEMA",
    "TRACE_SCHEMA",
    "context_problems",
    "problems",
    "root",
    "strict_problems",
    "strict_root",
]

#: The repositories of the spine, in the order a run passes through them, and the package each ships.
SPINE: Mapping[str, str] = {
    "interconnected_alpha": "alpha",
    "interconnected_zeta": "zeta",
    "interconnected_beta": "beta",
    "interconnected_delta": "delta",
}

_SHA256 = re.compile(r"[0-9a-f]{64}")


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
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
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


# ---------------------------------------------------------------------------------------------------------------
# Strict verification: the actual contents, not a caller's account of them.
# ---------------------------------------------------------------------------------------------------------------

#: The pipeline context every stage binds: one subject, one event, one run. Each of the four repositories' connectors
#: validates its own copy of this contract; `chains/spine_run.py` holds those copies to `context_problems`.
CONTEXT_SCHEMA = "spine-context/1"
#: Names the strict root, so it can never equal a lenient `root`.
TRACE_SCHEMA = "spine-trace/2"
#: The only ledger receipt this check reads: the mapping `delta.cns_connector.verification_receipt` returns.
RECEIPT_SCHEMA = "ledger-receipt/1"
CHAIN_NOT_SHOWN = ("the ledger chain was not shown to verify (delta's verify_chain_integrity, with the recorded entry "
                   "as a member of that chain), so the entry may not belong to the chain")
BARE_ASSERTION = "chain_verified is a bare assertion and is not evidence; pass chain= a delta verification receipt"
LEGACY_DECISION = ("{who} carries no content_fingerprint (a full lowercase SHA-256): strict verification refuses a legacy "
                   "Decision, because a blanked fingerprint is a downgrade that removes the integrity claim")
FINGERPRINT_NOT_RECOMPUTED = "alpha's KeySet fingerprint does not match a recomputation from alpha's keys"
_ORIGIN_FIELDS = ("source", "producer", "observed_at", "collection_context", "transformation")
_RECEIPT_FIELDS = ("schema", "entry_digest", "index", "entry_hash", "previous_hash", "ledger_length", "ledger_head",
                   "checkpoint_length", "checkpoint_head", "context")
_UNSET: Any = object()

_CONTEXT_FIELDS = ("schema", "entity_id", "event_id", "run_id")
_RUN_FIELDS = ("entity_id", "event_id", "run_id")
#: Fields beta's content carries only when bound to a run; the ledger's embedded copy of the Decision has none of them.
_BETA_RUN_FIELDS = ("context", "keyset_digest", "lock_result_digests")


def context_problems(context: object) -> List[str]:
    """What is wrong with a pipeline context. Empty when it is exactly the four fields, non-empty exact strings, a known schema.

    The mapping is read once (`dict(context)`) and the snapshot is what is judged, so a mapping that answers differently
    on a later read cannot pass here and be recorded as something else elsewhere. A value must be exactly `str`: a
    subclass can lie about its own equality, hash or text, so it is a named problem, not a pass."""
    if not isinstance(context, Mapping):
        return [f"a pipeline context must be a mapping; got {type(context).__name__}"]
    try:
        snapshot = dict(context)
    except Exception as exc:  # noqa: BLE001 - a mapping that cannot be read once is not a valid context
        return [f"a pipeline context could not be read: {type(exc).__name__}: {exc}"]
    out: List[str] = []
    if set(snapshot) != set(_CONTEXT_FIELDS):
        out.append(f"a pipeline context has exactly the fields {list(_CONTEXT_FIELDS)}; got {sorted(map(str, snapshot))}")
        return out
    for name in _CONTEXT_FIELDS:
        value = snapshot[name]
        if type(value) is not str:
            kind = f"a str subclass ({type(value).__name__}); the exact type str is required" if isinstance(value, str) else type(value).__name__
            out.append(f"context field {name} must be a str; got {kind}")
        elif not value:
            out.append(f"context field {name} must be non-empty")
    if not out and snapshot["schema"] != CONTEXT_SCHEMA:
        out.append(f"unsupported schema {snapshot['schema']!r}; this check speaks {CONTEXT_SCHEMA!r}")
    return out


def _digest(content: Mapping[str, Any], who: str, out: List[str]) -> Optional[str]:
    try:
        return subject_digest(content)
    except (TypeError, ValueError) as exc:
        out.append(f"{who} content cannot be digested: {exc}")
        return None


def _same(a: Any, b: Any) -> bool:
    """Whether two values are the same content as CNS binds it. Python calls True, 1 and 1.0 equal; CNS does not."""
    try:
        return subject_digest({"v": a}) == subject_digest({"v": b})
    except (TypeError, ValueError):
        return False


def _differing(a: Mapping[str, Any], b: Mapping[str, Any]) -> List[str]:
    return sorted(k for k in set(a) | set(b) if k not in a or k not in b or not _same(a[k], b[k]))


def _plain(value: Any) -> Any:
    """A copy made by reading each mapping and sequence exactly once, so what is checked is what is hashed."""
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in list(value.items())}
    if isinstance(value, list):
        return [_plain(v) for v in list(value)]
    if isinstance(value, tuple):
        return tuple(_plain(v) for v in value)
    return value


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _strings(value: object) -> Optional[List[str]]:
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def strict_problems(
    alpha: Mapping[str, Any],
    zeta: Mapping[str, Mapping[str, Any]],
    beta: Mapping[str, Any],
    delta: Mapping[str, Any],
    *,
    chain: Optional[Mapping[str, Any]] = None,
    chain_verified: Any = _UNSET,
    keyset_fingerprint_of: Optional[Callable[[Mapping[str, Any]], str]] = None,
    held_checkpoint: Any = None,
    require_keyset_verifier: bool = False,
) -> List[str]:
    """Everything that does not hold together in four stages' contents. Empty when they describe one run.

    `alpha` is `keyset_content(keys, context=...)`, `zeta` maps each lock id to
    `lock_result_content(result, context=..., keyset_digest=...)`, `beta` is `decision_content(decision,
    context=..., keyset_digest=..., lock_result_digests=...)` and `delta` is `entry_content(entry, context=...,
    decision_digest=...)`. Every digest is recomputed here.

    `chain` is the one fact the contents cannot carry: that delta's own ledger verified, with the recorded entry a
    member of it, against a checkpoint held outside it. It is the receipt `delta.cns_connector.verification_receipt`
    returns (schema `ledger-receipt/1`). CNS imports no repository and never sees the ledger, so it checks the receipt
    against what it already holds: the receipt is read once into a snapshot and must be a mapping with exactly the ten
    plain-str keys (schema, entry_digest, index, entry_hash, previous_hash, ledger_length, ledger_head, checkpoint_length,
    checkpoint_head, context), each value of its exact type (a str or int subclass is refused); its `entry_digest` must
    equal the digest of the delta content given, its `entry_hash` and `previous_hash` the delta content's `immutable_hash`
    and `previous_hash`, its context the run's; its lengths and index must be ints (not bools) with
    `0 <= index < checkpoint_length <= ledger_length`; its heads must be 64 lowercase hex digits; the ledger head must be
    the entry's hash when the entry is the ledger's last, and the checkpoint head the ledger head when the checkpoint
    covers the whole ledger. Every failure is a named problem; without a valid receipt the chain is "not shown to
    verify" and no root is issued. The receipt is not signed: someone who can build a consistent one can pass this check,
    so it raises the bar for mistakes and partial forgeries and is not proof of custody.

    `held_checkpoint`, when given, is the checkpoint the CALLER holds, kept in storage the producer of the ledger cannot
    write (a `(length, head)` pair or a mapping with exactly `length` and `head`; same exact-type rules as the receipt:
    an int that is not a bool, a 64 character lowercase hex head). The receipt's `checkpoint_length` and
    `checkpoint_head` must then equal it exactly, each a named problem if not. This is the only thing here that can
    refuse a ledger that was tampered with, rechained from the tampered entry on, and given a fresh checkpoint: delta
    issues a receipt for that ledger, and every field of the receipt is consistent with the others. WITHOUT it, such a
    receipt cannot be told from an honest one by anything CNS holds (behaviour is then exactly as before, and the root
    is the root it always was). With it, what stays undetectable is a tampering the held checkpoint does not cover
    (entries after its length), a held checkpoint the attacker could also rewrite, and a caller that supplies a
    checkpoint taken from the ledger it is checking. CNS holds no ledger and no storage: it compares what it is handed.
    A root issued against a held checkpoint carries that fact in its domain, so it differs from one issued without.

    `chain_verified` is a deprecated alias that is never evidence. Passing it, whatever the value, emits a
    DeprecationWarning and is always the problem "chain_verified is a bare assertion and is not evidence; pass chain= a
    delta verification receipt".

    `keyset_fingerprint_of`, when supplied, is a callable(alpha content) -> str that recomputes alpha's KeySet fingerprint
    from alpha's keys. The caller builds it from zeta, which owns the rule; CNS never implements it and imports nothing
    from zeta. Its result must equal alpha's `keyset_fingerprint`; if it raises or answers anything else the problem is
    "alpha's KeySet fingerprint does not match a recomputation from alpha's keys". Left out, CNS only compares the
    fingerprint strings that alpha, zeta and beta carry, so a substituted alpha content that copies the original
    fingerprint string passes (a recorded gap). The callable is itself supplied by the caller, which is one more thing
    that is trusted. It is asked ONCE per alpha content: the answer is kept against the callable and the content, so a
    callable that answers differently the second time cannot make `strict_problems` name a problem and `strict_root`
    issue a root for the same run (hacker1 E55). A root issued with a callable says so in its domain (present only when
    set, so a root issued without one is unchanged), so the two are never equal. `require_keyset_verifier=True` makes the absence of the callable a
    named problem instead (default False, so existing callers are unchanged).
    """
    if chain_verified is not _UNSET:
        warnings.warn("chain_verified is deprecated and never counts as evidence; pass chain= a delta verification receipt",
                      DeprecationWarning, stacklevel=2)
    _require_bool(require_keyset_verifier)
    snap, unread = _snapshot(alpha, zeta, beta, delta)
    if unread:
        return unread
    return _strict_problems(*snap, chain=chain, bare_assertion=chain_verified is not _UNSET,
                            keyset_fingerprint_of=keyset_fingerprint_of, held_checkpoint=held_checkpoint,
                            require_keyset_verifier=require_keyset_verifier)


def _snapshot(alpha: Any, zeta: Any, beta: Any, delta: Any) -> Tuple[Tuple[Any, Any, Any, Any], List[str]]:
    """Read each stage once into plain copies. A stage that cannot be read is a problem, not an exception."""
    unread: List[str] = []
    copies: List[Any] = []
    for name, content in (("alpha", alpha), ("zeta", zeta), ("beta", beta), ("delta", delta)):
        try:
            copies.append(_plain(content))
        except Exception as exc:  # noqa: BLE001 - any failure to read is a failure to verify
            unread.append(f"{name} content could not be read: {type(exc).__name__}: {exc}")
            copies.append(None)
    return (copies[0], copies[1], copies[2], copies[3]), unread


def _origin_problems(origin: Any, decided_at: Any) -> List[str]:
    """What is wrong with the origin record alpha carries, or about its ordering against the Decision. Empty if none.

    Well-formedness and order only: exactly the five fields, each a non-empty exact str, `observed_at` ISO 8601 text
    (`datetime.fromisoformat`) that is not later than the Decision's timestamp. These are the producer's own assertions.
    Nothing here says who the producer is, that the source is real, that the observation is true, or that anyone was
    authorized: CNS makes no authenticity claim."""
    if not isinstance(origin, Mapping):
        return [f"alpha origin must be a mapping; got {type(origin).__name__}"]
    out: List[str] = []
    if set(map(str, origin)) != set(_ORIGIN_FIELDS) or len(origin) != len(_ORIGIN_FIELDS):
        return [f"alpha origin has exactly the fields {list(_ORIGIN_FIELDS)}; got {sorted(map(str, origin))}"]
    for name in _ORIGIN_FIELDS:
        value = origin[name]
        if type(value) is not str:
            out.append(f"alpha origin {name} must be a str; got {type(value).__name__}")
        elif not value:
            out.append(f"alpha origin {name} must be non-empty")
    if out:
        return out
    try:
        observed = datetime.fromisoformat(origin["observed_at"])
    except ValueError:
        return [f"alpha origin observed_at is not ISO 8601 text: {origin['observed_at']!r}"]
    if not isinstance(decided_at, str):
        return ["alpha origin observed_at cannot be ordered against the Decision: beta carries no timestamp text"]
    try:
        decided = datetime.fromisoformat(decided_at)
    except ValueError:
        return [f"alpha origin observed_at cannot be ordered against the Decision: beta's timestamp {decided_at!r} is not ISO 8601 text"]
    if (observed.utcoffset() is None) != (decided.utcoffset() is None):
        return ["alpha origin observed_at and the Decision's timestamp cannot be ordered: one carries a time zone and the other does not"]
    if observed > decided:
        return [f"alpha origin observed_at {origin['observed_at']!r} is later than the Decision's timestamp {decided_at!r}"]
    return []


def _is_int(value: object) -> bool:
    return type(value) is int


def _is_hex_str(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _shown(value: object) -> str:
    """How a receipt value is named in a problem. Only plain values are shown as themselves: a hostile object's own repr is
    never called."""
    if value is None or type(value) in (str, int, bool, float):
        return repr(value)
    return f"<{type(value).__name__}>"


def _receipt_problems(chain: Any, delta: Any, delta_digest: Optional[str], run: Optional[Mapping[str, Any]],
                      held_cp: Optional[Tuple[int, str]] = None) -> List[str]:
    """What is wrong with a ledger receipt, judged against the delta content and the run CNS already holds. Empty if none.

    The receipt is read ONCE into a plain dict and everything below is judged from that snapshot, so a mapping that answers
    differently on a later read cannot pass and be used as something else. Only an exact set of ten `str` keys is a receipt,
    every value must be of its exact type (a subclass can lie about its own equality), and the receipt's hashes and
    positions must agree with the delta content and with each other. Nothing here raises: every failure is a named problem."""
    if not isinstance(chain, Mapping):
        return [f"the ledger receipt must be a mapping (delta's verification_receipt); got {type(chain).__name__}"]
    try:
        receipt = dict(chain)
    except Exception as exc:  # noqa: BLE001 - a receipt that cannot be read once is not evidence
        return [f"the ledger receipt could not be read: {type(exc).__name__}: {exc}"]
    out: List[str] = []
    schema = receipt.get("schema")
    if type(schema) is not str or schema != RECEIPT_SCHEMA:
        out.append(f"the ledger receipt has schema {_shown(schema)}; this check reads {RECEIPT_SCHEMA!r}")
    foreign = sum(1 for k in receipt if type(k) is not str)
    present = {k for k in receipt if type(k) is str}
    odd = sorted(present ^ set(_RECEIPT_FIELDS))
    if odd or foreign:
        detail = ", ".join(odd + ([f"{foreign} key(s) that are not a plain str"] if foreign else []))
        out.append(f"the ledger receipt has exactly the fields {list(_RECEIPT_FIELDS)} as plain str keys; these differ: {detail}")
        return out
    entry_digest = receipt["entry_digest"]
    if not _is_hex_str(entry_digest):
        out.append("the ledger receipt's entry_digest is not a full lowercase SHA-256 (an exact str)")
    elif delta_digest is not None and entry_digest != delta_digest:
        out.append("the ledger receipt is for other content: its entry_digest is not the digest of the delta content given")
    held_context = receipt["context"]
    snapshot: Any = held_context
    if isinstance(held_context, Mapping):
        try:
            snapshot = dict(held_context)
        except Exception as exc:  # noqa: BLE001 - a context that cannot be read once is not a context
            out.append(f"the ledger receipt's context could not be read: {type(exc).__name__}: {exc}")
            snapshot = None
    if snapshot is not None:
        issues = context_problems(snapshot)
        if issues:
            out += [f"the ledger receipt's context: {issue}" for issue in issues]
        elif run is not None and snapshot != dict(run):
            out.append("the ledger receipt is for another run: its context is not the run's context")
    ints = True
    for name in ("index", "ledger_length", "checkpoint_length"):
        if not _is_int(receipt[name]):
            out.append(f"the ledger receipt's {name} must be an int (not a bool, not a subclass); got {type(receipt[name]).__name__}")
            ints = False
    heads = True
    for name in ("ledger_head", "checkpoint_head"):
        if not _is_hex_str(receipt[name]):
            out.append(f"the ledger receipt's {name} is not a full lowercase SHA-256 (an exact str)")
            heads = False
    # The entry the receipt is about must be the entry the delta content describes: hashes of the entry itself, which
    # delta's own content carries (and whose digest the entry_digest above already binds).
    hashes = True
    for name, field in (("entry_hash", "immutable_hash"), ("previous_hash", "previous_hash")):
        value = receipt[name]
        if type(value) is not str or not value:
            out.append(f"the ledger receipt's {name} must be a non-empty exact str; got {type(value).__name__}")
            hashes = False
        elif not isinstance(delta, Mapping) or field not in delta:
            out.append(f"the delta content carries no {field}, so the ledger receipt's {name} cannot be matched to it")
            hashes = False
        elif not _same(value, delta[field]):
            out.append(f"the ledger receipt's {name} is not the delta content's {field}: the receipt is about another entry")
            hashes = False
    if ints:
        index, length, held = receipt["index"], receipt["ledger_length"], receipt["checkpoint_length"]
        if not 0 <= index < length:
            out.append(f"the ledger receipt's index {index} is not within a ledger of {length} entries")
        if held < 1:
            out.append("the ledger receipt's checkpoint_length is below 1: an empty checkpoint carries no evidence")
        elif held > length:
            out.append(f"the ledger receipt's checkpoint_length {held} is beyond its ledger_length {length}")
        if 0 <= index and held >= 1 and index >= held:
            out.append(f"the ledger receipt's index {index} is not covered by its checkpoint_length {held}: "
                       "the checkpoint held outside the ledger says nothing of that entry")
        if heads:
            if index == length - 1 and hashes and receipt["ledger_head"] != receipt["entry_hash"]:
                out.append("the ledger receipt's entry is the ledger's last, but its ledger_head is not the entry's own hash")
            if 1 <= held == length and receipt["checkpoint_head"] != receipt["ledger_head"]:
                out.append("the ledger receipt's checkpoint covers the whole ledger but its head is not the ledger's head")
            if index == held - 1 >= 0 and hashes and receipt["checkpoint_head"] != receipt["entry_hash"]:
                out.append("the ledger receipt's entry is the last one its checkpoint covers, but its checkpoint_head is not "
                           "the entry's own hash")
    if held_cp is not None:
        if ints and receipt["checkpoint_length"] != held_cp[0]:
            out.append(f"the ledger receipt's checkpoint_length {receipt['checkpoint_length']} is not the held checkpoint's "
                       f"length {held_cp[0]}: the checkpoint is not the one held outside the ledger")
        if heads and receipt["checkpoint_head"] != held_cp[1]:
            out.append("the ledger receipt's checkpoint_head is not the checkpoint held outside the ledger: the ledger was "
                       "checkpointed afresh, or it is not the ledger that checkpoint was taken from")
    return out


def _require_bool(value: object) -> None:
    if type(value) is not bool:
        raise TypeError(f"require_keyset_verifier must be a bool; got {type(value).__name__}")


#: What each verifier answered, per alpha content: {id(owner): (weak reference to the owner, {(function, digest): answer})}.
#: Held by identity and weakly, so a collected verifier takes its answers with it and a lookalike cannot borrow them.
_VERIFIED: Dict[int, Tuple[Any, Dict[Tuple[Any, str], Optional[str]]]] = {}
_VERIFIED_LOCK = threading.Lock()
_VERIFIED_LIMIT = 64


def _recomputed_once(verifier: Callable[[Mapping[str, Any]], str], alpha: Mapping[str, Any]) -> Optional[str]:
    """Ask `verifier` for the fingerprint of this alpha content, once. A verifier that raises has answered None. The answer
    is kept for the pair (verifier, content digest), so a later evaluation of the same run reuses it instead of asking a
    verifier that may now answer differently. A callable that cannot be held weakly is asked every time."""
    owner: Any = verifier.__self__ if isinstance(verifier, types.MethodType) else verifier
    tag: Any = verifier.__func__ if isinstance(verifier, types.MethodType) else None
    key: Optional[Tuple[Any, str]]
    memo: Optional[Dict[Tuple[Any, str], Optional[str]]]
    try:
        key = (tag, subject_digest(alpha))
        slot = _VERIFIED.get(id(owner))
        memo = slot[1] if slot is not None and slot[0]() is owner else None
    except Exception:  # noqa: BLE001 - nothing to key on: ask the verifier, keep nothing
        key, memo = None, None
    if memo is not None and key in memo:
        return memo[key]
    try:
        answer: Optional[str] = verifier(_plain(alpha))
    except Exception:  # noqa: BLE001 - a verifier that cannot recompute has not verified
        answer = None
    if key is not None and (answer is None or type(answer) is str):
        try:
            with _VERIFIED_LOCK:
                slot = _VERIFIED.get(id(owner))
                if slot is None or slot[0]() is not owner:
                    ident = id(owner)

                    def forget(_ref: Any, ident: int = ident) -> None:
                        _VERIFIED.pop(ident, None)
                    slot = (weakref.ref(owner, forget), {})
                    _VERIFIED[ident] = slot
                if len(slot[1]) >= _VERIFIED_LIMIT:
                    slot[1].pop(next(iter(slot[1])))
                slot[1][key] = answer
        except TypeError:  # not weakly referenceable
            pass
    return answer


def _held_checkpoint(held: Any) -> Tuple[Optional[Tuple[int, str]], List[str]]:
    """The checkpoint the caller holds, read ONCE and validated as strictly as a receipt's. (None, problems) if it is not
    well formed. Nothing here raises."""
    shape = "held_checkpoint must be a (length, head) pair or a mapping with exactly length and head"
    try:
        if isinstance(held, Mapping):
            read = dict(held)
            if set(read) != {"length", "head"} or any(type(k) is not str for k in read):
                return None, [shape]
            length, head = read["length"], read["head"]
        elif isinstance(held, (tuple, list)) and len(held) == 2:
            length, head = held[0], held[1]
        else:
            return None, [shape]
    except Exception as exc:  # noqa: BLE001 - a held checkpoint that cannot be read once is not evidence
        return None, [f"held_checkpoint could not be read: {type(exc).__name__}: {exc}"]
    out: List[str] = []
    if not _is_int(length):
        out.append(f"held_checkpoint length must be an int (not a bool, not a subclass); got {type(length).__name__}")
    elif length < 1:
        out.append("held_checkpoint length is below 1: an empty checkpoint carries no evidence")
    if not _is_hex_str(head):
        out.append("held_checkpoint head is not a full lowercase SHA-256 (an exact str)")
    return (None, out) if out else ((length, head), [])


def _strict_problems(alpha: Any, zeta: Any, beta: Any, delta: Any, *, chain: Any = None, bare_assertion: bool = False,
                     keyset_fingerprint_of: Any = None, held_checkpoint: Any = None,
                     require_keyset_verifier: bool = False) -> List[str]:
    out: List[str] = []
    stages = {"alpha": alpha, "beta": beta, "delta": delta}
    for name, content in stages.items():
        if not isinstance(content, Mapping):
            out.append(f"{name} content is not a mapping")
    if not isinstance(zeta, Mapping) or not zeta:
        out.append("zeta evaluated no lock, so the Decision has nothing to rest on")
    else:
        for lock_id, content in zeta.items():
            if not isinstance(content, Mapping):
                out.append(f"zeta lock {lock_id} content is not a mapping")
    if out:
        return out

    # Who is bound to what run. Every stage must carry a valid context; the run is the one most stages name.
    contexts: Dict[str, Mapping[str, Any]] = {}
    labelled: List[Tuple[str, Mapping[str, Any]]] = [("alpha", alpha)]
    labelled += [(f"zeta lock {lock_id}", content) for lock_id, content in zeta.items()]
    labelled += [("beta", beta), ("delta", delta)]
    for who, content in labelled:
        if "context" not in content:
            out.append(f"{who} carries no context, and strict verification needs one")
            continue
        issues = context_problems(content["context"])
        if issues:
            out += [f"{who} context: {issue}" for issue in issues]
            continue
        contexts[who] = content["context"]
    # The run is alpha's context: alpha is the stage that holds the observation, so every other stage is judged against
    # it. (A vote among stages named the honest stages when one outlier outnumbered them, e.g. a registry of many locks.)
    run: Optional[Mapping[str, Any]] = contexts.get("alpha")
    if run is not None:
        for who, c in contexts.items():
            if who != "alpha" and dict(c) != dict(run):
                wrong = [f"{f} {c[f]!r} vs {run[f]!r}" for f in _CONTEXT_FIELDS if c[f] != run[f]]
                out.append(f"{who} is bound to a different run than alpha's: {', '.join(wrong)}")

    # Lineage: each stage names the digest of the one before it, and CNS recomputes that digest from the content.
    da = _digest(alpha, "alpha", out)
    dz: Dict[str, str] = {}
    for lock_id, content in zeta.items():
        digest = _digest(content, f"zeta lock {lock_id}", out)
        if digest is not None:
            dz[lock_id] = digest
    db = _digest(beta, "beta", out)
    dd = _digest(delta, "delta", out)
    for lock_id, content in zeta.items():
        if content.get("stale"):
            out.append(f"zeta lock {lock_id} was refused as stale; a Decision cannot rest on an observation zeta declined to apply")
        if "lock_id" in content and content["lock_id"] != lock_id:
            out.append(f"zeta lock {lock_id} carries lock_id {content['lock_id']!r}; a result is filed under its own lock id")
    if da is not None:
        for lock_id, content in zeta.items():
            if "keyset_digest" not in content:
                out.append(f"zeta lock {lock_id} names no keyset_digest")
            elif content["keyset_digest"] != da:
                out.append(f"zeta lock {lock_id} was evaluated from a different KeySet than alpha produced")
        if "keyset_digest" not in beta:
            out.append("beta names no keyset_digest")
        elif beta["keyset_digest"] != da:
            out.append("beta's Decision was made from a different KeySet than alpha produced")
    named = beta.get("lock_result_digests")
    if not isinstance(named, Mapping):
        out.append("beta names no lock_result_digests")
    else:
        for lock_id in sorted(set(dz) & set(named)):
            if named[lock_id] != dz[lock_id]:
                out.append(f"beta's Decision rests on a different lock result than zeta produced for {lock_id}")
        absent = sorted(set(zeta) - set(named))
        if absent:
            out.append(f"beta's Decision does not digest zeta's lock result(s): {', '.join(absent)}")
        extra = sorted(set(named) - set(zeta))
        if extra:
            out.append(f"beta's Decision names lock result(s) zeta did not produce: {', '.join(extra)}")
    if "decision_digest" not in delta:
        out.append("delta names no decision_digest")
    elif db is not None and delta["decision_digest"] != db:
        out.append("delta recorded a Decision other than the one beta produced")
    embedded = delta.get("decision")
    if not isinstance(embedded, Mapping):
        out.append("delta's entry carries no decision content")
    else:
        core = {k: v for k, v in beta.items() if k not in _BETA_RUN_FIELDS}
        drift = _differing(core, embedded)
        if drift:
            out.append(f"the Decision delta recorded differs from beta's in: {', '.join(drift)}")
        if not _is_sha256(embedded.get("content_fingerprint")):
            out.append(LEGACY_DECISION.format(who="delta's embedded Decision"))
    if not _is_sha256(beta.get("content_fingerprint")):
        out.append(LEGACY_DECISION.format(who="beta's Decision"))

    # Identity and what the Decision cites.
    if run is not None:
        entity = run["entity_id"]
        for lock_id, content in zeta.items():
            if "entity_id" in content and content["entity_id"] != entity:
                out.append(f"zeta lock {lock_id} records entity {content['entity_id']!r} but the run is about {entity!r}")
        if beta.get("entity_id") != entity:
            out.append(f"beta's Decision is about {beta.get('entity_id')!r} but the run is about {entity!r}")
        for field in ("run_id", "event_id"):
            if field not in delta:
                out.append(f"delta's entry records no {field}")
            elif delta[field] != run[field]:
                out.append(f"delta's entry was recorded under {field} {delta[field]!r} but the run is {run[field]!r}")
    present = _strings(alpha.get("present_names"))
    keys = alpha.get("keys")
    held: Optional[set] = None
    if isinstance(keys, list) and all(isinstance(k, Mapping) and isinstance(k.get("name"), str) for k in keys):
        held = {k["name"] for k in keys if k.get("present") is True}
    else:
        out.append("alpha keys are not a list of named keys")
    if present is None:
        out.append("alpha lists no present_names, so what the Decision cites cannot be checked")
    else:
        if held is not None:
            unheld = sorted(set(present) - held)
            if unheld:
                out.append(f"alpha lists present_names that its own keys do not hold as present: {', '.join(unheld)}")
        cited_keys = _strings(beta.get("triggered_by_keys"))
        if cited_keys is None:
            out.append("beta's Decision lists no triggered_by_keys")
        else:
            unseen = sorted(set(cited_keys) - set(present))
            if unseen:
                out.append(f"the Decision cites key(s) alpha did not list as present: {', '.join(unseen)}")
    cited_locks = _strings(beta.get("triggered_by_locks"))
    if cited_locks is None:
        out.append("beta's Decision lists no triggered_by_locks")
    else:
        unevaluated = sorted(set(cited_locks) - set(zeta))
        if unevaluated:
            out.append(f"the Decision cites lock(s) zeta never evaluated: {', '.join(unevaluated)}")
    newly = _strings(beta.get("newly_triggered_locks"))
    if newly is None:
        out.append("beta's Decision lists no newly_triggered_locks")
    else:
        unseen_new = sorted(set(newly) - set(zeta))
        if unseen_new:
            out.append(f"the Decision names newly triggered lock(s) zeta never evaluated: {', '.join(unseen_new)}")
    if "origin" in alpha:
        out += _origin_problems(alpha["origin"], beta.get("timestamp"))
    # Zeta's own record of the KeySet it evaluated, against the fingerprint alpha reports for the KeySet it produced.
    # A digest a binder names can be made to chain; this is a fact each component computed about its own object.
    fa = alpha.get("keyset_fingerprint")
    if not _is_sha256(fa):
        out.append("alpha carries no keyset_fingerprint (a full lowercase SHA-256), so a lock result cannot be matched to its KeySet")
    else:
        for lock_id, content in zeta.items():
            fz = content.get("keyset_fingerprint")
            if not _is_sha256(fz):
                out.append(f"zeta lock {lock_id} carries no keyset_fingerprint, so it cannot be matched to alpha's KeySet")
            elif fz != fa:
                out.append(f"zeta lock {lock_id} was evaluated from a different KeySet than alpha produced "
                           "(its recorded KeySet fingerprint differs from alpha's)")
        if keyset_fingerprint_of is not None:
            # Zeta owns the fingerprint rule; the caller hands CNS a function built from it. CNS only compares. A copy of
            # alpha is handed over so the function cannot alter what is judged, and a function that raises or answers
            # anything but alpha's own fingerprint is the same problem.
            recomputed = _recomputed_once(keyset_fingerprint_of, alpha)
            if type(recomputed) is not str or recomputed != fa:
                out.append(FINGERPRINT_NOT_RECOMPUTED)
        fb = beta.get("keyset_fingerprint")
        if not _is_sha256(fb):
            out.append("beta carries no keyset_fingerprint, so its Decision cannot be matched to alpha's KeySet")
        elif fb != fa:
            out.append("beta's Decision was made from a different KeySet than alpha produced "
                       "(its recorded KeySet fingerprint differs from alpha's)")
    if keyset_fingerprint_of is None and require_keyset_verifier:
        out.append("no keyset_fingerprint_of was supplied, and require_keyset_verifier is set: alpha's KeySet fingerprint "
                   "was not recomputed by the component that owns the rule")
    if bare_assertion:
        out.append(BARE_ASSERTION)
    held_cp: Optional[Tuple[int, str]] = None
    held_issues: List[str] = []
    if held_checkpoint is not None:
        held_cp, held_issues = _held_checkpoint(held_checkpoint)
    receipt_issues = [] if chain is None else _receipt_problems(chain, delta, dd, run, held_cp)
    out += held_issues + receipt_issues
    if chain is None or receipt_issues or held_issues:
        out.append(CHAIN_NOT_SHOWN)
    stage_digests = [d for d in (da, db, dd) if d is not None]
    if len(set(stage_digests)) != len(stage_digests):
        out.append("two stages are bound to the same digest; each stage must be bound to its own output")
    return out


def strict_root(
    alpha: Mapping[str, Any],
    zeta: Mapping[str, Mapping[str, Any]],
    beta: Mapping[str, Any],
    delta: Mapping[str, Any],
    *,
    chain: Optional[Mapping[str, Any]] = None,
    chain_verified: Any = _UNSET,
    keyset_fingerprint_of: Optional[Callable[[Mapping[str, Any]], str]] = None,
    held_checkpoint: Any = None,
    require_keyset_verifier: bool = False,
) -> str:
    """One digest over the whole run, from the contents. Raises ValueError if the stages do not hold together.

    Without a valid `chain` (a delta verification receipt, see `strict_problems`) no root is issued. The deprecated
    `chain_verified` never counts: it warns and is always a problem, so it never yields a root."""
    if chain_verified is not _UNSET:
        warnings.warn("chain_verified is deprecated and never counts as evidence; pass chain= a delta verification receipt",
                      DeprecationWarning, stacklevel=2)
    _require_bool(require_keyset_verifier)
    (alpha, zeta, beta, delta), unread = _snapshot(alpha, zeta, beta, delta)
    found = unread or _strict_problems(alpha, zeta, beta, delta, chain=chain, bare_assertion=chain_verified is not _UNSET,
                                       keyset_fingerprint_of=keyset_fingerprint_of, held_checkpoint=held_checkpoint,
                                       require_keyset_verifier=require_keyset_verifier)
    if found:
        raise ValueError("the spine run does not hold together: " + "; ".join(found))
    context = alpha["context"]
    held_fact: Dict[str, Any] = {}
    if held_checkpoint is not None:
        held, _ = _held_checkpoint(held_checkpoint)
        assert held is not None  # a held checkpoint that did not read is a problem above, so no root reaches here
        held_fact = {"held_checkpoint": {"length": held[0], "head": held[1]}}
    if keyset_fingerprint_of is not None:
        held_fact["keyset_verifier"] = "supplied"  # present only when set: a root issued without one is exactly what it was
    return subject_digest({
        **held_fact,
        "schema": TRACE_SCHEMA,
        "context": {f: context[f] for f in _CONTEXT_FIELDS},
        "alpha": subject_digest(alpha),
        "zeta": {lock_id: subject_digest(content) for lock_id, content in zeta.items()},
        "beta": subject_digest(beta),
        "delta": subject_digest(delta),
    })

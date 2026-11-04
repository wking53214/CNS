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
  - delta's entry was recorded under that run and event.

A missing field is a problem, not a skip. Content that cannot be digested is a problem, not an exception. CNS
reads fields by their documented names and applies no decision policy: it does not say which Key should be
present, which Lock should open, or whether the Decision is right. `strict_root` is domain-separated
(`TRACE_SCHEMA`), so it can never equal a lenient `root`, and it is never a native digest of any stage.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from cns.gate import subject_digest

__all__ = [
    "CONTEXT_SCHEMA",
    "SPINE",
    "SpineRecord",
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


# ---------------------------------------------------------------------------------------------------------------
# Strict verification: the actual contents, not a caller's account of them.
# ---------------------------------------------------------------------------------------------------------------

#: The pipeline context every stage binds: one subject, one event, one run. Each of the four repositories' connectors
#: validates its own copy of this contract; `chains/spine_run.py` holds those copies to `context_problems`.
CONTEXT_SCHEMA = "spine-context/1"
#: Names the strict root, so it can never equal a lenient `root`.
TRACE_SCHEMA = "spine-trace/2"

_CONTEXT_FIELDS = ("schema", "entity_id", "event_id", "run_id")
_RUN_FIELDS = ("entity_id", "event_id", "run_id")
#: Fields beta's content carries only when bound to a run; the ledger's embedded copy of the Decision has none of them.
_BETA_RUN_FIELDS = ("context", "keyset_digest", "lock_result_digests")


def context_problems(context: object) -> List[str]:
    """What is wrong with a pipeline context. Empty when it is exactly the four fields, non-empty strings, a known schema."""
    if not isinstance(context, Mapping):
        return [f"a pipeline context must be a mapping; got {type(context).__name__}"]
    out: List[str] = []
    if set(context) != set(_CONTEXT_FIELDS):
        out.append(f"a pipeline context has exactly the fields {list(_CONTEXT_FIELDS)}; got {sorted(map(str, context))}")
        return out
    for name in _CONTEXT_FIELDS:
        value = context[name]
        if not isinstance(value, str):
            out.append(f"context field {name} must be a str; got {type(value).__name__}")
        elif not value:
            out.append(f"context field {name} must be non-empty")
    if not out and context["schema"] != CONTEXT_SCHEMA:
        out.append(f"unsupported schema {context['schema']!r}; this check speaks {CONTEXT_SCHEMA!r}")
    return out


def _digest(content: Mapping[str, Any], who: str, out: List[str]) -> Optional[str]:
    try:
        return subject_digest(content)
    except (TypeError, ValueError) as exc:
        out.append(f"{who} content cannot be digested: {exc}")
        return None


def _differing(a: Mapping[str, Any], b: Mapping[str, Any]) -> List[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k, _MISSING) != b.get(k, _MISSING))


_MISSING = object()


def _strings(value: object) -> Optional[List[str]]:
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return list(value)
    return None


def strict_problems(
    alpha: Mapping[str, Any],
    zeta: Mapping[str, Mapping[str, Any]],
    beta: Mapping[str, Any],
    delta: Mapping[str, Any],
) -> List[str]:
    """Everything that does not hold together in four stages' contents. Empty when they describe one run.

    `alpha` is `keyset_content(keys, context=...)`, `zeta` maps each lock id to
    `lock_result_content(result, context=..., keyset_digest=...)`, `beta` is `decision_content(decision,
    context=..., keyset_digest=..., lock_result_digests=...)` and `delta` is `entry_content(entry, context=...,
    decision_digest=...)`. Nothing is taken from the caller but those four contents; every digest is recomputed here.
    """
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
    run: Optional[Mapping[str, Any]] = None
    if contexts:
        counts = Counter(tuple(sorted(c.items())) for c in contexts.values())
        best = max(counts.values())
        first = next(c for c in contexts.values() if counts[tuple(sorted(c.items()))] == best)
        run = first
        for who, c in contexts.items():
            if dict(c) != dict(run):
                wrong = [f"{f} {c[f]!r} vs {run[f]!r}" for f in _CONTEXT_FIELDS if c[f] != run[f]]
                out.append(f"{who} is bound to a different run: {', '.join(wrong)}")

    # Lineage: each stage names the digest of the one before it, and CNS recomputes that digest from the content.
    da = _digest(alpha, "alpha", out)
    dz: Dict[str, str] = {}
    for lock_id, content in zeta.items():
        digest = _digest(content, f"zeta lock {lock_id}", out)
        if digest is not None:
            dz[lock_id] = digest
    db = _digest(beta, "beta", out)
    dd = _digest(delta, "delta", out)
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
    if present is None:
        out.append("alpha lists no present_names, so what the Decision cites cannot be checked")
    else:
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
    stage_digests = [d for d in (da, db, dd) if d is not None]
    if len(set(stage_digests)) != len(stage_digests):
        out.append("two stages are bound to the same digest; each stage must be bound to its own output")
    return out


def strict_root(
    alpha: Mapping[str, Any],
    zeta: Mapping[str, Mapping[str, Any]],
    beta: Mapping[str, Any],
    delta: Mapping[str, Any],
) -> str:
    """One digest over the whole run, from the contents. Raises ValueError if the stages do not hold together."""
    found = strict_problems(alpha, zeta, beta, delta)
    if found:
        raise ValueError("the spine run does not hold together: " + "; ".join(found))
    context = alpha["context"]
    return subject_digest({
        "schema": TRACE_SCHEMA,
        "context": {f: context[f] for f in _CONTEXT_FIELDS},
        "alpha": subject_digest(alpha),
        "zeta": {lock_id: subject_digest(content) for lock_id, content in zeta.items()},
        "beta": subject_digest(beta),
        "delta": subject_digest(delta),
    })

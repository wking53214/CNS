"""The decision spine, run for real, then checked at its seams.

alpha detects Keys from vitals, zeta evaluates Locks over them, beta turns lock states into a Decision, delta
records the Decision in a hash-chained ledger. Each repository binds its own output with its optional CNS
connector. `cns_composition.spine_trace` checks that the four stages describe one run: the Decision cites only
Keys that were detected and Locks that were evaluated, belongs to the entity the run was about, and beta's digest of the
Decision equals delta's digest of the Decision it recorded.

Every scenario states what it must produce and the script exits 1 if any differs. Run in the `chains` workflow
against the four repositories' default branches, so it fails the day one of them drifts from the others.

Two groups. The first seven are the LENIENT check (`spine_trace.problems`), which takes the facts a caller read
off the objects. The rest are STRICT: each stage's content is built with a pipeline context and the lineage digest
of the stage before it, and `spine_trace.strict_problems` recomputes every digest from those contents. They run the
real objects through the real attacks (another subject, another event, another run, an altered stage, a stale
replay, a repeat, a truncated ledger, a missing context, a fabricated run, and the hardened components' own refusals:
an empty or always-equal checkpoint, a replayed or backdated record, a failed append, another entity's lock results, a
str-subclass or shifting context, an aliased list, a stale content fingerprint, a forged chain_verified flag, a KeySet
swapped under a copied fingerprint) and state, as an `Expect` (see
`spine_oracle.py`), the problems the boundary that should refuse each one must name and the only extras it may add.
A scenario fails if a required problem is missing, if an unlisted problem appears, if it returns nothing when it
should be refused, if it crashes without declaring it (a SystemExit or KeyboardInterrupt is a crash of that scenario and
never ends the run), if a refusal's text came back without a refusal having been recorded, or if a refusal changed the
state it guarded (the whole content of every entry, not only its hash). Thirteen scenarios, marked GAP, record what the strict check does NOT catch as facts that expect no problem: authorship (a forger who
recomputes every digest and fingerprint and writes a consistent receipt), a receipt written by hand over real contents
with no ledger behind it, a narrative forged by someone who also recomputes the keyless content fingerprint, a Decision
citing a closed lock, a legacy lock result with no entity id, a KeySet swapped under a copied fingerprint when no
recomputation is supplied, a sink whose own store keeps a write the ledger does not have (delta's idempotency
contract), and a rewritten ledger given a fresh checkpoint when no checkpoint is held outside it (`held_checkpoint`), and, with the
signed receipts and the durable store, a holder of a trusted key signing a forged receipt, an older signed checkpoint (a signature
carries no freshness) and a ledger rolled back to an older complete signed package. They go red the day the gap closes and are then
updated on purpose.

Three groups were added with the signing hook, delta's file store and the verify command. `signed:` signs the receipt through
delta's `sign_receipt` with the reference keys of `receipt_keys.py` (a trust list, a revocation set, rotation) and asks CNS's
`strict_problems` with `receipt_signature`, `verify_receipt_signature` and `require_signed_receipt`; one scenario holds CNS's
`receipt_signing_input` byte-equal to delta's. `store:` runs a producer and a fresh consumer as separate processes
(`store_worker.py`) through `FileLedgerStore`, with the checkpoint in a directory of its own, signed. `package:` runs
`make_package.py` and `verify_package.py` as separate processes, end to end. Their refusals carry the named reason of the
process that refused, and the files they guard are compared byte for byte before and after.

The run also attacks the receipt itself (zeroed heads, an index beyond the ledger or the checkpoint, another entry's
hashes, a lying str-subclass digest or head, a key that only prints like a field name) starting from the receipt delta
really issues, and the hardened ledger (a replay with the fingerprint blanked, a lying entity id, a list that changes
between reads, a datetime subclass, a sink that appends, a checkpoint that answers honestly once, a receipt for an entry
the checkpoint does not cover). Delta's refusal of a checkpoint is one sentence for five causes; the runner's own wrapper
(`ask_delta`) names the cause from what it can see, which is an inference and not delta's statement: a scenario is only as
specific as the attack it builds (the empty-checkpoint ones carry the ledger's real head, so removing the length-0 guard turns them red).
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import threading
import warnings
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import receipt_keys
from spine_oracle import Expect, attempts, check_table, entries_digest, judge
from spine_oracle import refused as _refused

import alpha.cns_connector as alpha_cns
import beta.cns_connector as beta_cns
import delta.cns_connector as delta_cns
import delta as delta_pkg
import delta.signing as delta_signing
import delta.context as delta_context
import zeta.cns_connector as zeta_cns
from alpha import PackError, PackRegistry, PackValidationError, pack_identity
from alpha.packs.pediatric_vitals import VitalsObservation, observe
from alpha.packs.pediatric_vitals import PediatricVitalsPack
from alpha.packs.service_health import ServiceHealthPack, ServiceObservation
from beta import (
    Decision, DecisionEngine, DecisionRule, DecisionRuleRegistry, KeySetMismatchError,
    StaleLockResultError, decision_fingerprint)
from beta.fingerprint import content_fingerprint
from cns.gate import subject_digest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cns_composition import spine_manifest
from cns_composition import spine_trace
from cns_composition.spine_trace import (
    CONTEXT_SCHEMA, SpineRecord, context_problems, problems, root, strict_problems, strict_root)
from delta import DecisionLedger
from delta.ledger import DuplicateRecordError, LedgerCheckpoint
from zeta import Combination, Key, KeySet, LockEvaluator, LockRegistry, LockSpec

T0 = datetime(2026, 10, 1, 8, 0, 0)
SICK = VitalsObservation(heart_rate=148, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=14)
WELL = VitalsObservation(heart_rate=100, oxygen_saturation=99.0, respiratory_rate=24, temperature=37.0, age_months=14)


def build():
    locks = LockRegistry([
        LockSpec(lock_id="sepsis_lock", required_keys=("septic_shock", "respiratory_distress", "hypovolemic_shock"),
                 combination=Combination.OR, dwell_threshold=1, force=True, lock_seconds=3600),
        LockSpec(lock_id="abnormal_vitals_lock",
                 required_keys=("critical_o2", "warning_o2", "tachycardia", "bradycardia", "tachypnea", "fever", "hypothermia"),
                 combination=Combination.OR, dwell_threshold=1),
    ])
    rules = DecisionRuleRegistry([
        DecisionRule(decision_id="escalate_sepsis", decision="ESCALATE", open_locks=("sepsis_lock",), priority=10,
                     reasoning_template="{decision}: sepsis", instructions="Emergency room now."),
        DecisionRule(decision_id="hold_abnormal", decision="HOLD", open_locks=("abnormal_vitals_lock",),
                     closed_locks=("sepsis_lock",), priority=5, reasoning_template="{decision}: monitoring",
                     instructions="Keep monitoring."),
        DecisionRule(decision_id="discharge_safe", decision="DISCHARGE_SAFE",
                     closed_locks=("sepsis_lock", "abnormal_vitals_lock"), priority=0,
                     reasoning_template="{decision}: vitals normal", instructions="Discharge with follow-up."),
    ])
    return locks, DecisionEngine(rules, locks)


def facts(keys, results, decision, entry, entity="patient_1") -> SpineRecord:
    return SpineRecord(
        entity_id=entity,
        keyset_digest=alpha_cns.keyset_digest(keys), keys_present=tuple(sorted(keys.names_present())),
        lock_result_digests={lid: zeta_cns.lock_result_digest(r) for lid, r in results.items()},
        open_locks=tuple(lid for lid, r in results.items() if r.open),
        decision_entity_id=decision.entity_id, decision_keys=tuple(decision.triggered_by_keys),
        decision_locks=tuple(decision.triggered_by_locks), decision_digest=beta_cns.decision_digest(decision),
        ledger_decision_digest=subject_digest(delta_cns.entry_content(entry)["decision"]),
        entry_digest=delta_cns.entry_digest(entry))


def run(vitals=SICK):
    locks, engine = build()
    ledger = DecisionLedger()
    keys = observe(vitals)
    results = LockEvaluator(locks).evaluate_all("patient_1", keys, T0)
    decision = engine.decide("patient_1", keys, results, T0)
    return engine, ledger, keys, results, decision, ledger.append(decision)


def clean(vitals) -> List[str]:
    _, _, keys, results, decision, entry = run(vitals)
    return problems(facts(keys, results, decision, entry))


def cites_a_key_alpha_never_saw() -> List[str]:
    _, _, keys, results, decision, entry = run()
    return problems(facts(keys, results, dataclasses.replace(decision, triggered_by_keys=("ghost_key",)), entry))


def cites_a_lock_zeta_never_evaluated() -> List[str]:
    _, _, keys, results, decision, entry = run()
    return problems(facts(keys, results, dataclasses.replace(decision, triggered_by_locks=("invented_lock",)), entry))


def ledger_recorded_another_decision() -> List[str]:
    engine, ledger, keys, results, decision, _ = run()
    well = observe(WELL)
    other = engine.decide("patient_1", well, LockEvaluator(build()[0]).evaluate_all("patient_1", well, T0), T0)
    return problems(facts(keys, results, decision, ledger.append(other)))


def wrong_entity() -> List[str]:
    _, _, keys, results, decision, entry = run()
    return problems(facts(keys, results, decision, entry, entity="patient_2"))


def two_runs_have_different_roots() -> List[str]:
    a, b = run(SICK), run(WELL)
    ra, rb = root(facts(a[2], a[3], a[4], a[5])), root(facts(b[2], b[3], b[4], b[5]))
    return [] if ra != rb else ["two different runs produced the same root"]


# --- strict: the real objects, with a context and lineage, checked from their contents ---------------------------

CTX = {"schema": CONTEXT_SCHEMA, "entity_id": "patient_1", "event_id": "event_1", "run_id": "run_1"}


SICK_ELSEWHERE = VitalsObservation(heart_rate=149, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=14)


def stages(vitals=SICK, ctx=CTX, results_from=None, keys_for_decision=None, bind_keyset_of=None, origin=None,
           ledger=None, at=T0) -> Dict[str, Any]:
    """Run the four stages for real, binding each to the context and to the digest of the stage before it. `ledger` (default a
    new one that requires a context) and `at` (the Decision's time) let a caller record several runs into one ledger."""
    locks, engine = build()
    ledger = DecisionLedger(require_context=True) if ledger is None else ledger
    entity = ctx["entity_id"]
    keys = observe(vitals)
    alpha = alpha_cns.keyset_content(keys, context=ctx, origin=origin)
    # zeta and beta are told which KeySet digest to name; nothing in either can check it against what they evaluated.
    da = subject_digest(alpha if bind_keyset_of is None else alpha_cns.keyset_content(observe(bind_keyset_of), context=ctx))
    results = LockEvaluator(locks).evaluate_all(entity, keys, at)
    zeta = {lid: zeta_cns.lock_result_content(r, context=ctx, keyset_digest=da) for lid, r in results.items()}
    decided_on = results if results_from is None else results_from
    decision = engine.decide(entity, keys if keys_for_decision is None else keys_for_decision, decided_on, at)
    beta = beta_cns.decision_content(
        decision, context=ctx, keyset_digest=da,
        lock_result_digests={lid: zeta_cns.lock_result_digest(r, context=ctx, keyset_digest=da) for lid, r in decided_on.items()})
    entry = ledger.append(decision, context=ctx)
    delta = delta_cns.entry_content(entry, context=ctx, decision_digest=subject_digest(beta))
    return {"alpha": alpha, "zeta": zeta, "beta": beta, "delta": delta, "ledger": ledger, "engine": engine,
            "decision": decision, "keys": keys, "results": results, "da": da, "checkpoint": ledger.checkpoint()}


def zeta_keyset_fingerprint(alpha_content) -> str:
    """Zeta's own fingerprint of the KeySet that alpha's content describes: rebuilt from alpha's keys (name, present,
    confidence, reason) and min_confidence by zeta's constructors, then zeta's `fingerprint()`. Zeta owns the rule; CNS is
    handed this function and only compares what it returns with the fingerprint alpha carries."""
    keys = [Key(name=k["name"], present=k["present"], confidence=k["confidence"], reason=k["reason"])
            for k in alpha_content["keys"]]
    return KeySet(keys, min_confidence=alpha_content["min_confidence"]).fingerprint()


DELTA_GENERIC_REFUSAL = "the checkpoint is empty, foreign, mistyped or not contained in this ledger"


def refusal_cause(ledger: DecisionLedger, held: Any) -> str:
    """Why delta refused a checkpoint, from what the runner can see of the ledger and the checkpoint (delta's own text is one
    sentence for five causes, and the runner does not change delta). Each cause has its own text, so a scenario can require
    the one it is about. The checkpoint is read once."""
    length, head = held.length, held.head
    held_hash = (len(head) == 64 and all(c in "0123456789abcdef" for c in head)) if type(head) is str else False
    entries = list(ledger.entries)
    if type(length) is not int or not held_hash:
        return "mistyped checkpoint: its length is not an exact int or its head is not an exact 64 hex str"
    if length < 1:
        return f"empty checkpoint: length {length} names no entry, so it is the same for every ledger"
    if length > len(entries):
        return (f"ledger shorter than the checkpoint: it holds {len(entries)} entries and the checkpoint covers {length} "
                "(truncated, with its own chain still verifying)")
    if any(e.immutable_hash == head for e in entries):
        return "checkpoint head is another entry of this ledger: its history was reordered or rewritten after the checkpoint"
    return ("unmatched checkpoint: its head names no entry of this ledger (a checkpoint of another ledger, or of this ledger's own "
            "history before it was rewritten and rechained; a length and a head cannot tell which)")


def ask_delta(ledger: DecisionLedger, held: Any, *, context: Any, decision_digest: Any) -> Dict[str, Any]:
    """Delta's `verification_receipt`, with a refusal about the checkpoint explained by `refusal_cause`. Delta's own message
    is kept first; a broken chain is already its own message and is only labelled."""
    try:
        return delta_cns.verification_receipt(ledger, held, context=context, decision_digest=decision_digest)
    except ValueError as exc:
        if DELTA_GENERIC_REFUSAL in str(exc):
            raise ValueError(f"{exc} [cause: {refusal_cause(ledger, held)}]") from exc
        if "chain does not verify" in str(exc):
            raise ValueError(f"{exc} [cause: ledger's own chain check fails, so it was altered, or its head not reset after "
                             "entries were removed]") from exc
        raise


def chain_receipt(parts) -> Tuple[Any, str]:
    """Ask delta itself for a verification receipt about the ledger's last entry, against the checkpoint the scenario holds.

    The checkpoint was taken before any attack and is held in `parts`, outside the ledger object. Delta refuses unless its
    chain verifies and the ledger still contains the history the checkpoint recorded (an empty or foreign checkpoint is
    refused too, and the refusal says which cause it was, see `ask_delta`), and the receipt carries the digest of the entry
    as exported under the content's own context and decision digest, so content that describes another Decision, run or
    time than the entry cannot match it. No checkpoint, or a refusal, is (None, why): CNS is then given no receipt."""
    try:
        held = parts.get("checkpoint")
        if held is None:
            return None, "this scenario holds no checkpoint taken before the attack, so no receipt can be asked for"
        content = parts["delta"]
        return ask_delta(parts["ledger"], held, context=content.get("context"), decision_digest=content.get("decision_digest")), ""
    except Exception as exc:  # noqa: BLE001 - delta refused, or there was nothing to ask: no receipt, not an exception
        return None, f"{type(exc).__name__}: {exc}"


def check(parts, *, verify_fingerprint: bool = True) -> List[str]:
    """The strict check as the runner asks it: with delta's receipt and, unless a scenario says otherwise, with zeta's
    recomputation of alpha's KeySet fingerprint."""
    receipt, refusal = chain_receipt(parts)
    found = strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain=receipt,
                            keyset_fingerprint_of=zeta_keyset_fingerprint if verify_fingerprint else None)
    return found + ([f"delta issued no verification receipt: {refusal}"] if refusal else [])


def refused(thunk: Callable[[], Any], state: Callable[[], Any] | None = None, catch: Tuple[type, ...] = (),
            record: Any = None) -> List[str]:
    """What a boundary refused, as a problem string, or nothing if it let the call through. `state` is compared before
    and after: a refusal that changed it is a second problem (see spine_oracle.refused). `catch` adds exception classes
    beyond the ValueErrors, TypeErrors and OverflowErrors the oracle already treats as refusals. `record` is the scenario's
    own record (`attempts()`), handed to a thread the scenario started; see spine_oracle.attempts."""
    return _refused(thunk, catch=(StaleLockResultError, KeySetMismatchError) + tuple(catch), state=state, record=record)


def ledger_state(ledger: DecisionLedger) -> Callable[[], Any]:
    """What a refusal must leave alone: the length, the head AND a digest of the whole content of every entry in order (its
    Decision, ids and timestamp as well as its hashes), so a refusal that swapped an entry for another of the same count and
    head, or edited an entry and kept its hash, still shows."""
    def state() -> Any:
        entries = list(ledger.entries)
        return (len(entries), ledger.chain_head, entries_digest(entries))
    return state


def strict_clean(vitals) -> List[str]:
    return check(stages(vitals))


def strict_roots_differ_by_run() -> List[str]:
    a, b = stages(SICK), stages(SICK, ctx={**CTX, "run_id": "run_2"})
    ra, rb = (strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], chain=chain_receipt(p)[0],
                         keyset_fingerprint_of=zeta_keyset_fingerprint) for p in (a, b))
    return [] if ra != rb else ["the same readings in two runs produced one root"]


def strict_root_is_not_a_lenient_root() -> List[str]:
    p = stages(SICK)
    strict = strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], chain=chain_receipt(p)[0],
                         keyset_fingerprint_of=zeta_keyset_fingerprint)
    lenient = root(facts(p["keys"], p["results"], p["decision"], p["ledger"].entries[0]))
    return [] if strict != lenient else ["a strict root equals a lenient root"]


def subject_substituted_between_alpha_and_zeta() -> List[str]:
    """Zeta's results are bound to another patient's context, though they cite alpha's KeySet digest. Zeta now refuses to
    bind a result to a context of another entity, so the results here are the other patient's own (evaluated for it)."""
    p = stages(SICK)
    other = {**CTX, "entity_id": "patient_2"}
    p["zeta"] = {lid: zeta_cns.lock_result_content(dataclasses.replace(r, entity_id="patient_2"), context=other,
                                                   keyset_digest=p["da"]) for lid, r in p["results"].items()}
    return check(p)


def event_substituted_between_zeta_and_beta() -> List[str]:
    p = stages(SICK)
    other = {**CTX, "event_id": "event_2"}
    p["beta"] = beta_cns.decision_content(
        p["decision"], context=other, keyset_digest=p["da"],
        lock_result_digests={lid: subject_digest(c) for lid, c in p["zeta"].items()})
    return check(p)


def alpha_and_zeta_from_one_run_beta_and_delta_from_another() -> List[str]:
    one, two = stages(SICK), stages(SICK, ctx={**CTX, "run_id": "run_2"})
    return check({**one, "beta": two["beta"], "delta": two["delta"]})


def keyset_altered_after_zeta_evaluated_it() -> List[str]:
    p = stages(SICK)
    p["alpha"] = alpha_cns.keyset_content(observe(WELL), context=CTX)  # other keys, the summaries unchanged
    return check(p)


def lock_result_altered_after_beta_decided_on_it() -> List[str]:
    p = stages(SICK)
    other = stages(WELL)
    p["zeta"] = {**p["zeta"], "sepsis_lock": other["zeta"]["sepsis_lock"]}
    return check(p)


def decision_altered_after_delta_recorded_it() -> List[str]:
    p = stages(SICK)
    forged = dataclasses.replace(p["decision"], instructions="Send home.")
    p["beta"] = beta_cns.decision_content(
        forged, context=CTX, keyset_digest=p["da"], lock_result_digests=p["beta"]["lock_result_digests"])
    return check(p)


def beta_decided_from_another_lock_result() -> List[str]:
    """Beta is given the sick patient's KeySet and the well patient's lock results. It used to return ESCALATE with no
    triggering Keys and full confidence; each result now records the KeySet it came from, and beta refuses."""
    locks, _ = build()
    well_results = LockEvaluator(locks).evaluate_all("patient_1", observe(WELL), T0)
    return refused(lambda: stages(SICK, results_from=well_results))


def delta_recorded_another_decision() -> List[str]:
    p = stages(SICK)
    other = p["engine"].decide("patient_1", observe(WELL), LockEvaluator(build()[0]).evaluate_all("patient_1", observe(WELL), T0), T0)
    p["delta"] = delta_cns.entry_content(DecisionLedger().append(other, context=CTX), context=CTX,
                                         decision_digest=subject_digest(p["beta"]))
    return check(p)


def contradictory_basis_is_refused_by_beta() -> List[str]:
    p = stages(SICK)
    return refused(lambda: dataclasses.replace(p["decision"], confidence_basis="absence"))


def contradictory_basis_that_skips_construction_is_refused_by_delta() -> List[str]:
    p = stages(SICK)
    bad = object.__new__(Decision)
    for f in dataclasses.fields(Decision):
        object.__setattr__(bad, f.name, getattr(p["decision"], f.name))
    object.__setattr__(bad, "confidence_basis", "absence")
    ledger = DecisionLedger()
    return refused(lambda: ledger.append(bad, context=CTX), ledger_state(ledger))


def stale_replay_is_refused_by_beta() -> List[str]:
    locks, engine = build()
    ev = LockEvaluator(locks)
    ev.evaluate_all("patient_1", observe(WELL), T0)
    stale = ev.evaluate_all("patient_1", observe(SICK), T0 - timedelta(hours=2))
    return refused(lambda: engine.decide("patient_1", observe(SICK), stale, T0))


def the_same_decision_is_recorded_twice_in_one_run() -> List[str]:
    p = stages(SICK)
    return refused(lambda: p["ledger"].append(p["decision"], context=CTX), ledger_state(p["ledger"]))


def a_stage_carries_no_context() -> List[str]:
    p = stages(SICK)
    p["delta"] = delta_cns.entry_content(p["ledger"].entries[0])
    return check(p)


def a_run_fabricated_with_digests_that_do_not_chain() -> List[str]:
    """What the lenient check accepts: four stages that agree with themselves and describe nothing. Here the digests are
    invented and do not chain; a fabricator who recomputes them passes (see the GAP scenario)."""
    d = lambda n: subject_digest({"fabricated": n})  # noqa: E731
    fake = {"alpha": {"context": dict(CTX), "present_names": ["anything"], "keys": [], "min_confidence": 0.0},
            "zeta": {"any_lock": {"context": dict(CTX), "entity_id": "patient_1", "keyset_digest": d(1)}},
            "beta": {"context": dict(CTX), "entity_id": "patient_1", "triggered_by_keys": ["anything"],
                     "triggered_by_locks": ["any_lock"], "keyset_digest": d(1), "lock_result_digests": {"any_lock": d(2)}},
            "delta": {"context": dict(CTX), "run_id": "run_1", "event_id": "event_1", "decision_digest": d(3),
                      "decision": {"entity_id": "patient_1"}}}
    return check(fake)


def three_decisions_in_a_ledger() -> DecisionLedger:
    """Three real Decisions, each a minute later (an identical Decision is a replay, which delta refuses)."""
    ledger = DecisionLedger()
    for i, vitals in enumerate((SICK, WELL, SICK)):
        engine = build()[1]
        keys = observe(vitals)
        at = T0 + timedelta(minutes=i)
        results = LockEvaluator(build()[0]).evaluate_all("patient_1", keys, at)
        ledger.append(engine.decide("patient_1", keys, results, at), context={**CTX, "run_id": f"run_{i}", "event_id": f"event_{i}"})
    return ledger


MIDDLE_CTX = {**CTX, "run_id": "run_1", "event_id": "event_1"}


def a_ledger_truncated_with_its_head_reset() -> List[str]:
    """A checkpoint is held outside a three-entry ledger; then the ledger is cut back by one entry and its head reset, which
    its own chain check accepts. Delta refuses to issue a receipt against the held checkpoint, so CNS is never given one."""
    ledger = three_decisions_in_a_ledger()
    held = ledger.checkpoint()
    ledger.entries.pop()
    ledger.chain_head = ledger.entries[-1].immutable_hash
    assert ledger.verify_chain_integrity(), "the chain alone is expected to accept this: that is the gap"
    return refused(lambda: ask_delta(ledger, held, context=MIDDLE_CTX, decision_digest=subject_digest({})), ledger_state(ledger))


def a_ledger_rolled_back_without_resetting_its_head() -> List[str]:
    """The last entry is removed and the head is left where it was, so the ledger's own chain check fails and delta refuses
    before it looks at the checkpoint."""
    ledger = three_decisions_in_a_ledger()
    held = ledger.checkpoint()
    ledger.entries.pop()
    assert not ledger.verify_chain_integrity(), "removing the last entry without moving the head is expected to break the chain"
    return refused(lambda: ask_delta(ledger, held, context=MIDDLE_CTX, decision_digest=subject_digest({})), ledger_state(ledger))


def an_empty_checkpoint_against_an_honest_ledger() -> List[str]:
    ledger = three_decisions_in_a_ledger()
    empty = LedgerCheckpoint(0, ledger.chain_head)  # the ledger's own head: removing the length-0 guard turns this red
    return refused(lambda: ask_delta(ledger, empty, context=MIDDLE_CTX, decision_digest=subject_digest({})), ledger_state(ledger))


def a_checkpoint_taken_from_another_ledger() -> List[str]:
    """An honest ledger and an honest checkpoint of a different ledger (other Decisions, a length the first one reaches)."""
    ledger = three_decisions_in_a_ledger()
    other = DecisionLedger()
    engine, keys = build()[1], observe(WELL)
    other.append(engine.decide("patient_9", keys, LockEvaluator(build()[0]).evaluate_all("patient_9", keys, T0), T0),
                 context={**CTX, "entity_id": "patient_9"})
    foreign = other.checkpoint()
    return refused(lambda: ask_delta(ledger, foreign, context=MIDDLE_CTX, decision_digest=subject_digest({})), ledger_state(ledger))


def a_stale_lock_result_is_rested_on() -> List[str]:
    """Zeta's contents say the observation was refused as stale; beta's Decision, made from fresh results, names them."""
    locks, _ = build()
    ev = LockEvaluator(locks)
    ev.evaluate_all("patient_1", observe(WELL), T0)
    stale = ev.evaluate_all("patient_1", observe(SICK), T0 - timedelta(hours=2))
    p = stages(SICK)
    p["zeta"] = {lid: zeta_cns.lock_result_content(r, context=CTX, keyset_digest=p["da"]) for lid, r in stale.items()}
    p["beta"] = beta_cns.decision_content(
        p["decision"], context=CTX, keyset_digest=p["da"],
        lock_result_digests={lid: subject_digest(c) for lid, c in p["zeta"].items()})
    p["delta"] = delta_cns.entry_content(p["ledger"].entries[0], context=CTX, decision_digest=subject_digest(p["beta"]))
    return check(p)


def a_lock_result_filed_under_another_locks_id() -> List[str]:
    p = stages(SICK)
    z = dict(p["zeta"])
    z["sepsis_lock"], z["abnormal_vitals_lock"] = z["abnormal_vitals_lock"], z["sepsis_lock"]
    p["zeta"] = z
    p["beta"] = beta_cns.decision_content(
        p["decision"], context=CTX, keyset_digest=p["da"],
        lock_result_digests={lid: subject_digest(c) for lid, c in z.items()})
    p["delta"] = delta_cns.entry_content(p["ledger"].entries[0], context=CTX, decision_digest=subject_digest(p["beta"]))
    return check(p)


def alpha_lists_a_key_it_does_not_hold_as_present() -> List[str]:
    p = stages(SICK)
    forged = dict(p["alpha"])
    forged["present_names"] = sorted(set(forged["present_names"]) | {"invented_key"})
    p["alpha"] = forged
    da = subject_digest(forged)
    p["zeta"] = {lid: zeta_cns.lock_result_content(r, context=CTX, keyset_digest=da) for lid, r in p["results"].items()}
    p["beta"] = beta_cns.decision_content(
        p["decision"], context=CTX, keyset_digest=da,
        lock_result_digests={lid: subject_digest(c) for lid, c in p["zeta"].items()})
    p["delta"] = delta_cns.entry_content(p["ledger"].entries[0], context=CTX, decision_digest=subject_digest(p["beta"]))
    return check(p)


def zeta_and_beta_named_the_digest_of_another_keyset() -> List[str]:
    """Zeta and beta evaluated and decided on one set of readings and were bound with the digest of a different KeySet
    that lists the same present Keys. This used to pass (a recorded GAP): the digest a binder names can be made to chain.
    Zeta now records a fingerprint of the KeySet it evaluated and alpha reports its own; they differ."""
    p = stages(SICK, bind_keyset_of=SICK_ELSEWHERE)
    p["alpha"] = alpha_cns.keyset_content(observe(SICK_ELSEWHERE), context=CTX)
    return check(p)


def origin_observed(at: datetime) -> Dict[str, str]:
    """An origin record as alpha's producer states it. Its claims are the producer's own: nothing authenticates them."""
    return {"source": "ward monitor 4", "producer": "vitals-ingest 2.1", "observed_at": at.isoformat(),
            "collection_context": "bedside, continuous", "transformation": "none"}


def an_origin_observed_before_the_decision() -> List[str]:
    return check(stages(SICK, origin=origin_observed(T0 - timedelta(seconds=30))))


def an_origin_observed_after_the_decision() -> List[str]:
    return check(stages(SICK, origin=origin_observed(T0 + timedelta(minutes=1))))


def rechain_from_alpha(p, alpha):
    """Recompute every downstream digest with the real connectors, from the real objects, given another alpha content."""
    da = subject_digest(alpha)
    zeta = {lid: zeta_cns.lock_result_content(r, context=CTX, keyset_digest=da) for lid, r in p["results"].items()}
    beta = beta_cns.decision_content(
        p["decision"], context=CTX, keyset_digest=da, lock_result_digests={lid: subject_digest(c) for lid, c in zeta.items()})
    delta = delta_cns.entry_content(p["ledger"].entries[-1], context=CTX, decision_digest=subject_digest(beta))
    return {**p, "alpha": alpha, "zeta": zeta, "beta": beta, "delta": delta}


def substituted_alpha_content_under_the_original_fingerprint(*, verify_fingerprint: bool) -> List[str]:
    """Matrix row 2b. Alpha's content is replaced by another KeySet's (other readings in the reasons, the same present
    Keys) that carries the ORIGINAL fingerprint string, and every digest downstream is recomputed from the real objects,
    so the lineage digests chain. Comparing fingerprint strings cannot see it; recomputing from alpha's keys does."""
    p = stages(SICK)
    other = alpha_cns.keyset_content(observe(SICK_ELSEWHERE), context=CTX)
    other["keyset_fingerprint"] = p["alpha"]["keyset_fingerprint"]
    return check(rechain_from_alpha(p, other), verify_fingerprint=verify_fingerprint)


def a_keyset_substituted_under_a_copied_fingerprint_is_recomputed() -> List[str]:
    return substituted_alpha_content_under_the_original_fingerprint(verify_fingerprint=True)


def a_verifier_is_asked_once_inside_one_root_evaluation() -> List[str]:
    """E55, as far as it holds. A substituted alpha under a copied fingerprint, and a verifier that recomputes honestly the first
    time it is asked and then echoes alpha's own fingerprint. `strict_root` evaluates once and uses that one answer, so no root
    is issued. Two separate public calls are two evaluations and each asks afresh: a verifier that lies across them is the
    caller's trust (stated in `strict_problems`' docstring), not something this scenario claims."""
    p = stages(SICK)
    other = alpha_cns.keyset_content(observe(SICK_ELSEWHERE), context=CTX)
    other["keyset_fingerprint"] = p["alpha"]["keyset_fingerprint"]
    q = rechain_from_alpha(p, other)
    receipt, why = chain_receipt(q)
    asked: List[int] = []

    def flaky(alpha: Any) -> str:
        asked.append(1)
        return zeta_keyset_fingerprint(alpha) if len(asked) == 1 else alpha["keyset_fingerprint"]
    found: List[str] = []
    try:
        strict_root(q["alpha"], q["zeta"], q["beta"], q["delta"], chain=receipt, keyset_fingerprint_of=flaky)
        found.append("a root was issued for a run whose verifier answered wrongly")
    except ValueError as exc:
        found += str(exc).split("the spine run does not hold together: ", 1)[-1].split("; ")
    if len(asked) != 1:
        found.append(f"the verifier was asked {len(asked)} times inside one evaluation")
    return found


def a_required_verifier_that_is_missing() -> List[str]:
    """F-07. Without `keyset_fingerprint_of` CNS cannot recompute alpha's fingerprint (the recorded gap before); a caller that
    cannot accept that says `require_keyset_verifier=True` and the absence is a named problem."""
    p = stages(SICK)
    receipt, why = chain_receipt(p)
    return strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], chain=receipt, require_keyset_verifier=True)


def an_honest_run_with_a_required_verifier() -> List[str]:
    p = stages(SICK)
    receipt, why = chain_receipt(p)
    return strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], chain=receipt, keyset_fingerprint_of=zeta_keyset_fingerprint,
                           require_keyset_verifier=True)


def GAP_a_keyset_substituted_under_a_copied_fingerprint_without_a_recomputation() -> List[str]:
    """KNOWN GAP, stated as a fact. Without `keyset_fingerprint_of` CNS compares the fingerprint strings alpha, zeta and
    beta carry and never recomputes alpha's from alpha's keys, so substitute content that copies the original string
    passes. The runner supplies the recomputation (the scenario before this one); a caller that does not gets this."""
    return substituted_alpha_content_under_the_original_fingerprint(verify_fingerprint=False)


def GAP_contents_fabricated_by_someone_who_recomputes_the_digests() -> List[str]:
    """KNOWN GAP, stated as a fact. There is no key in this check: four contents that agree with each other, carry one
    KeySet fingerprint (recomputed with zeta's own function, which is public), chain by digest and come with a receipt the
    forger wrote to match (the receipt is not signed) pass whether or not any component produced them. It verifies agreement, not authorship. (Without the fingerprints,
    or without a receipt that fits, it is refused; the other scenarios hold that.) No problem is found."""
    ctx = dict(CTX)
    alpha = {"min_confidence": 0.0, "keys": [{"name": "anything", "present": True, "confidence": 1.0, "reason": "made up"}],
             "context": dict(ctx), "present_names": ["anything"]}
    fp = alpha["keyset_fingerprint"] = zeta_keyset_fingerprint(alpha)  # the forger recomputes it, with zeta's own function
    da = subject_digest(alpha)
    zeta = {"any_lock": {"entity_id": "patient_1", "lock_id": "any_lock", "open": True, "changed": True, "forced": False,
                         "reasons": ["made up"], "context": dict(ctx), "keyset_digest": da, "keyset_fingerprint": fp}}
    fingerprint = decision_fingerprint({
        "entity_id": "patient_1", "decision_id": "d", "decision": "DISCHARGE_SAFE",
        "triggered_by_locks": ["any_lock"], "triggered_by_keys": ["anything"]})
    core = {"entity_id": "patient_1", "decision_id": "d", "decision": "DISCHARGE_SAFE", "timestamp": "2026-10-01T08:00:00",
            "confidence": 1.0, "triggered_by_locks": ["any_lock"], "triggered_by_keys": ["anything"],
            "newly_triggered_locks": [], "decision_fingerprint": fingerprint, "reasoning": "made up",
            "reversal_conditions": [], "instructions": "made up", "keyset_fingerprint": fp}
    # the forger recomputes beta's keyless content_fingerprint too, with beta's own public function, from a Decision it builds
    core["content_fingerprint"] = content_fingerprint(Decision(
        entity_id="patient_1", decision_id="d", decision="DISCHARGE_SAFE", timestamp=T0, confidence=1.0,
        triggered_by_locks=("any_lock",), triggered_by_keys=("anything",), newly_triggered_locks=(),
        decision_fingerprint=fingerprint, reasoning="made up", reversal_conditions=(), instructions="made up",
        keyset_fingerprint=fp))
    beta = {**core, "context": dict(ctx), "keyset_digest": da,
            "lock_result_digests": {k: subject_digest(v) for k, v in zeta.items()}}
    delta = {"audit_id": "0" * 16, "timestamp": "2026-10-01T08:00:00", "previous_hash": "0" * 64, "immutable_hash": "1" * 64,
             "decision": dict(core), "run_id": ctx["run_id"], "event_id": ctx["event_id"], "context": dict(ctx),
             "decision_digest": subject_digest(beta)}
    head = delta["immutable_hash"]  # a lone, last entry: the ledger's head is the entry's own hash, which the forger knows
    receipt = {"schema": "ledger-receipt/1", "entry_digest": subject_digest(delta), "index": 0,
               "entry_hash": delta["immutable_hash"], "previous_hash": delta["previous_hash"], "ledger_length": 1,
               "ledger_head": head, "checkpoint_length": 1, "checkpoint_head": head, "context": dict(ctx)}
    return strict_problems(alpha, zeta, beta, delta, chain=receipt, keyset_fingerprint_of=zeta_keyset_fingerprint)


def delta_content_names_a_hash_the_ledger_never_wrote() -> List[str]:
    p = stages(SICK)
    p["delta"] = {**p["delta"], "immutable_hash": "9" * 64}
    return check(p)


def delta_content_of_another_decision_under_the_ledgers_hashes() -> List[str]:
    """Honest ledger, substituted content: the hashes are the ledger's last entry, the Decision, run and time are another
    run's. The hash fields alone matched; the whole exported entry must."""
    p, q = stages(SICK), stages(WELL)
    e = p["ledger"].entries[-1]
    forged = {**q["delta"], "audit_id": e.audit_id, "previous_hash": e.previous_hash, "immutable_hash": e.immutable_hash}
    return check({**q, "delta": forged, "ledger": p["ledger"], "checkpoint": p["checkpoint"]})


def the_ledger_chain_is_broken_after_the_run() -> List[str]:
    p = stages(SICK)
    first = p["ledger"].entries[0]
    p["ledger"].entries[0] = dataclasses.replace(first, decision=dataclasses.replace(first.decision, instructions="Send home."))
    return check(p)


def nobody_asked_delta_whether_the_chain_verifies() -> List[str]:
    p = stages(SICK)
    return strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"])


def a_scenario_that_holds_no_checkpoint_is_refused() -> List[str]:
    p = stages(SICK)
    del p["checkpoint"]
    return check(p)


def an_unbound_append_to_a_ledger_that_requires_a_context() -> List[str]:
    p = stages(SICK)
    ledger = DecisionLedger(require_context=True)
    return refused(lambda: ledger.append(p["decision"]), ledger_state(ledger))


def a_second_decision_for_an_event_already_recorded() -> List[str]:
    p = stages(SICK)
    other = p["engine"].decide("patient_1", observe(WELL), LockEvaluator(build()[0]).evaluate_all("patient_1", observe(WELL), T0), T0)
    return refused(lambda: p["ledger"].append(other, context={**CTX, "run_id": "run_9"}), ledger_state(p["ledger"]))


def one_run_spanning_two_events() -> List[str]:
    p = stages(SICK)
    other = p["engine"].decide("patient_1", observe(WELL), LockEvaluator(build()[0]).evaluate_all("patient_1", observe(WELL), T0), T0)
    return refused(lambda: p["ledger"].append(other, context={**CTX, "event_id": "event_9"}), ledger_state(p["ledger"]))


def an_older_decision_after_a_newer_one_for_the_same_entity() -> List[str]:
    p = stages(SICK)
    locks, engine = build()
    keys = observe(WELL)
    older = engine.decide("patient_1", keys, LockEvaluator(locks).evaluate_all("patient_1", keys, T0 - timedelta(days=1)),
                          T0 - timedelta(days=1))
    return refused(lambda: p["ledger"].append(older, context={**CTX, "run_id": "run_9", "event_id": "event_9"}),
                   ledger_state(p["ledger"]))


def an_append_onto_a_head_that_does_not_match() -> List[str]:
    p = stages(SICK)
    p["ledger"].entries.pop()
    return refused(lambda: p["ledger"].append(p["decision"], context={**CTX, "run_id": "run_9", "event_id": "event_9"}),
                   ledger_state(p["ledger"]))


def a_narrative_edit_under_the_old_content_fingerprint() -> List[str]:
    """Beta's decision_fingerprint covers 5 of a Decision's 16 fields; a separate content_fingerprint covers 13 (all but
    audit_hash, decision_fingerprint and itself). Instructions, confidence and reasoning rewritten while the Decision keeps
    its OLD content_fingerprint no longer record: delta refuses at append (it checks the fingerprint when it has a context)."""
    p = stages(SICK)
    forged = dataclasses.replace(p["decision"], instructions="Send home.", confidence=0.01, reasoning="vitals normal")
    ledger = DecisionLedger(require_context=True)
    return refused(lambda: ledger.append(forged, context=CTX), ledger_state(ledger))


def GAP_a_decisions_narrative_forged_by_someone_who_recomputes_the_content_fingerprint() -> List[str]:
    """KNOWN GAP, stated as a fact, by design. content_fingerprint is keyless and its function (beta.fingerprint) is public,
    so a forger who rewrites instructions, confidence and reasoning and RECOMPUTES it produces a Decision that validates,
    records, binds and chains: it detects a partial edit, not an authored one. No problem is found. Only a key (authorship)
    could close it; there is none."""
    p = stages(SICK)
    edited = dataclasses.replace(p["decision"], instructions="Send home.", confidence=0.01, reasoning="vitals normal")
    forged = dataclasses.replace(edited, content_fingerprint=content_fingerprint(edited))
    forged.validate(check_fingerprint=True)
    ledger = DecisionLedger(require_context=True)
    entry = ledger.append(forged, context=CTX)
    p.update(ledger=ledger, checkpoint=ledger.checkpoint())
    p["beta"] = beta_cns.decision_content(
        forged, context=CTX, keyset_digest=p["da"], lock_result_digests=p["beta"]["lock_result_digests"])
    p["delta"] = delta_cns.entry_content(entry, context=CTX, decision_digest=subject_digest(p["beta"]))
    return check(p)


def GAP_a_decision_cites_a_lock_that_is_closed() -> List[str]:
    """KNOWN GAP, stated as a fact. A Decision keeps the union of the locks its rule cited, not which the rule required
    open and which closed, so an ESCALATE that cites sepsis_lock passes while zeta's bound content says it is closed.
    (The forger recomputes beta's public, keyless fingerprints, decision_fingerprint and content_fingerprint.) No problem
    is found. Recording the partition is a native Beta change that has not been made."""
    p = stages(WELL)
    d = p["decision"]
    edited = dataclasses.replace(
        d, decision="ESCALATE", decision_id="escalate_sepsis", triggered_by_locks=("sepsis_lock",),
        decision_fingerprint=decision_fingerprint({
            "entity_id": d.entity_id, "decision_id": "escalate_sepsis", "decision": "ESCALATE",
            "triggered_by_locks": ["sepsis_lock"], "triggered_by_keys": list(d.triggered_by_keys)}))
    forged = dataclasses.replace(edited, content_fingerprint=content_fingerprint(edited))
    ledger = DecisionLedger(require_context=True)
    entry = ledger.append(forged, context=CTX)
    p.update(ledger=ledger, checkpoint=ledger.checkpoint())
    p["beta"] = beta_cns.decision_content(
        forged, context=CTX, keyset_digest=p["da"], lock_result_digests=p["beta"]["lock_result_digests"])
    p["delta"] = delta_cns.entry_content(entry, context=CTX, decision_digest=subject_digest(p["beta"]))
    return check(p)


def a_legacy_decision_with_no_content_fingerprint_is_refused_by_the_strict_check() -> List[str]:
    """Step 11. A Decision whose content_fingerprint was blanked (beta before it had one, or a downgrade) is recorded by a
    ledger that does not require a context, with a context given at append. Every digest chains, delta's receipt is real, and
    the strict check still refuses it: it has lost the claim that its fields were not edited. (A require_context ledger
    refuses to record one; see the replay scenario.)"""
    p = stages(SICK)
    legacy = dataclasses.replace(p["decision"], content_fingerprint="")
    ledger = DecisionLedger()
    entry = ledger.append(legacy, context=CTX)
    p.update(ledger=ledger, checkpoint=ledger.checkpoint())
    p["beta"] = beta_cns.decision_content(
        legacy, context=CTX, keyset_digest=p["da"], lock_result_digests=p["beta"]["lock_result_digests"])
    p["delta"] = delta_cns.entry_content(entry, context=CTX, decision_digest=subject_digest(p["beta"]))
    found = check(p)
    lenient = problems(facts(p["keys"], p["results"], legacy, entry))
    return found + [f"the lenient check, which is unchanged, now names: {lenient}"] if lenient else found


def a_content_fingerprint_altered_in_beta_content_only() -> List[str]:
    """CNS compares content_fingerprint as carried (beta's content against delta's embedded copy) and never recomputes it."""
    p = stages(SICK)
    p["beta"] = {**p["beta"], "content_fingerprint": "0" * 64}
    return check(p)


def a_stale_content_fingerprint_in_an_unbound_ledger_cannot_be_bound_to_a_run() -> List[str]:
    """Matrix row 6b. A default DecisionLedger() has no context, so its append does not check fingerprints (stated as a
    limit: an unbound ledger is not judged). The entry it records has no run, so delta refuses to bind it to one, and the
    strict check has nothing to take."""
    p = stages(SICK)
    forged = dataclasses.replace(p["decision"], decision="DISCHARGE_SAFE", instructions="Send home.")
    ledger = DecisionLedger()
    entry = ledger.append(forged)
    return refused(lambda: delta_cns.entry_content(entry, context=CTX, decision_digest=subject_digest(p["beta"])), ledger_state(ledger))


# --- the receipt itself attacked: each starts from the receipt delta really issues and alters it in one way -----------

class LyingHex(str):
    """A str subclass equal to everything: what a receipt's digest must not be allowed to be."""

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__


class KeyLike:
    """Not a str, but prints as one: a receipt key compared by its text would take it for the field of that name."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return self.name


def altered_receipt(alter: Callable[[Dict[str, Any]], Dict[str, Any]], parts: Dict[str, Any] | None = None) -> List[str]:
    """Delta's real receipt for the run, altered in one way, handed to the strict check. A root issued anyway is a problem."""
    p = parts if parts is not None else stages(SICK)
    real, why = chain_receipt(p)
    if real is None:
        return [f"delta issued no receipt to alter: {why}"]
    forged = alter(dict(real))
    args = (p["alpha"], p["zeta"], p["beta"], p["delta"])
    found = strict_problems(*args, chain=forged, keyset_fingerprint_of=zeta_keyset_fingerprint)
    try:
        strict_root(*args, chain=forged, keyset_fingerprint_of=zeta_keyset_fingerprint)
        found.append("a root was issued for the altered receipt")
    except ValueError:
        pass
    return found


def a_receipt_with_both_heads_zeroed() -> List[str]:
    return altered_receipt(lambda r: {**r, "ledger_head": "0" * 64, "checkpoint_head": "0" * 64})


def a_receipt_with_an_index_beyond_its_ledger_and_its_checkpoint() -> List[str]:
    return altered_receipt(lambda r: {**r, "index": 4})


def a_receipt_for_entry_four_of_nine_under_a_checkpoint_that_covers_one() -> List[str]:
    return altered_receipt(lambda r: {**r, "index": 4, "ledger_length": 9})


def a_receipt_whose_checkpoint_ends_at_the_entry_but_names_no_such_head() -> List[str]:
    """A1. The entry is the last one its checkpoint covers (index == checkpoint_length - 1), so the checkpoint's head must be
    the entry's own hash; a receipt that names any other head for it was accepted before."""
    return altered_receipt(lambda r: {**r, "ledger_length": 2, "ledger_head": "a" * 64, "checkpoint_head": "b" * 64})


def _rewrite_receipted_under_a_fresh_checkpoint(held: Any) -> List[str]:
    """macg2 A4. A ledger tampered with, rechained and given a fresh checkpoint: delta issues a receipt for it (a fresh
    checkpoint of that ledger contains it), and every field agrees. `held` is the checkpoint the verifier kept elsewhere."""
    q = rewrite_the_run_completely()
    original = q["checkpoint"]
    content = q["delta"]
    receipt = ask_delta(q["ledger"], q["ledger"].checkpoint(), context=content["context"], decision_digest=content["decision_digest"])
    args = (q["alpha"], q["zeta"], q["beta"], q["delta"])
    kwargs: Dict[str, Any] = {"chain": receipt, "keyset_fingerprint_of": zeta_keyset_fingerprint}
    if held is not None:
        kwargs["held_checkpoint"] = (original.length, original.head)
    found = strict_problems(*args, **kwargs)
    try:
        strict_root(*args, **kwargs)
        if found:
            found.append("a root was issued although problems were named")
    except ValueError:
        pass
    return found


def a_rewritten_ledger_with_a_fresh_checkpoint_is_refused_against_the_checkpoint_held_outside() -> List[str]:
    return _rewrite_receipted_under_a_fresh_checkpoint(held=True)


def GAP_a_rewritten_ledger_with_a_fresh_checkpoint_and_no_checkpoint_held_outside() -> List[str]:
    """KNOWN GAP, stated as a fact. The same rewrite, verified without `held_checkpoint`: nothing CNS holds can tell the
    receipt from an honest one, so no problem is named. Only a checkpoint kept where the ledger's producer cannot write it
    closes this, and CNS can only compare what it is handed."""
    return _rewrite_receipted_under_a_fresh_checkpoint(held=None)


def an_honest_run_against_the_checkpoint_held_outside() -> List[str]:
    p = stages(SICK)
    receipt, why = chain_receipt(p)
    if receipt is None:
        return [f"delta issued no receipt: {why}"]
    held = p["checkpoint"]
    return strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], chain=receipt, keyset_fingerprint_of=zeta_keyset_fingerprint,
                           held_checkpoint=(held.length, held.head))


# --- independent verification: delta's public export, verified outside the producer --------------------------------

def _through_json(data: Any) -> Any:
    """What a verifier in another process receives: the export written as text and read back."""
    return json.loads(json.dumps(data))


def _frozen(data: Any) -> Callable[[], str]:
    """The state a refusal must leave alone: the export as the verifier received it."""
    return lambda: json.dumps(data, sort_keys=True)


def independent_check(p: Dict[str, Any], data: Any, *, export_checkpoint: Any, held: Any = None) -> List[str]:
    """The export is verified by delta's `verify_export` (a ValueError is a refusal and propagates), the rebuilt ledger is asked
    for a receipt, and the strict check runs with that receipt as `chain` and, when given, `held_checkpoint` taken from
    the checkpoint the verifier kept outside the producer."""
    rebuilt = delta_pkg.verify_export(data, export_checkpoint)
    content = p["delta"]
    receipt = ask_delta(rebuilt, rebuilt.checkpoint(), context=content["context"], decision_digest=content["decision_digest"])
    kwargs: Dict[str, Any] = {"chain": receipt, "keyset_fingerprint_of": zeta_keyset_fingerprint}
    if held is not None:
        kwargs["held_checkpoint"] = (held.length, held.head)
    return strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], **kwargs)


def _two_entries() -> Tuple[Dict[str, Any], Any]:
    """A real ledger of two entries (a second run for the same patient) and the checkpoint of its first entry."""
    p = stages(SICK)
    first = p["checkpoint"]
    ctx2 = {**CTX, "run_id": "run_2", "event_id": "event_2"}
    p["ledger"].append(stages(WELL, ctx=ctx2)["decision"], context=ctx2)
    p["checkpoint"] = p["ledger"].checkpoint()
    return p, first


def an_honest_export_is_verified_outside_the_producer() -> List[str]:
    p = stages(SICK)
    return independent_check(p, _through_json(p["ledger"].export()), export_checkpoint=p["checkpoint"], held=p["checkpoint"])


def an_export_with_an_edited_entry_is_refused() -> List[str]:
    p = stages(SICK)
    data = _through_json(p["ledger"].export())
    data["entries"][0]["decision"]["instructions"] = "Send home."
    return refused(lambda: delta_pkg.verify_export(data, p["checkpoint"]), _frozen(data))


def an_export_with_an_edited_hash_is_refused() -> List[str]:
    p = stages(SICK)
    data = _through_json(p["ledger"].export())
    data["entries"][0]["immutable_hash"] = "0" * 64
    return refused(lambda: delta_pkg.verify_export(data, p["checkpoint"]), _frozen(data))


def an_export_with_a_removed_entry_is_refused() -> List[str]:
    p, _ = _two_entries()
    data = _through_json(p["ledger"].export())
    del data["entries"][0]
    return refused(lambda: delta_pkg.verify_export(data, p["checkpoint"]), _frozen(data))


def _truncated_export() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    p, _ = _two_entries()
    data = _through_json(p["ledger"].export())
    del data["entries"][-1]
    data["chain_head"] = data["entries"][-1]["immutable_hash"]  # a shorter chain that is consistent in itself
    return p, data


def a_truncated_export_is_refused_against_a_held_checkpoint() -> List[str]:
    p, data = _truncated_export()
    return refused(lambda: delta_pkg.verify_export(data, p["checkpoint"]), _frozen(data))


def GAP_a_truncated_export_without_a_held_checkpoint() -> List[str]:
    """KNOWN GAP, stated as a fact. The same truncation, verified with no held checkpoint, is a consistent shorter chain and
    verify_export returns it: integrity only, no rollback detection."""
    _, data = _truncated_export()
    if len(delta_pkg.verify_export(data)) != 1:
        raise AssertionError("the truncated export was expected to verify as a one-entry ledger")
    return []


def an_export_checked_against_an_empty_checkpoint_is_refused() -> List[str]:
    p = stages(SICK)
    data = _through_json(p["ledger"].export())
    empty = LedgerCheckpoint(0, data["chain_head"])  # the export's own head: removing the length-0 guard turns this red
    return refused(lambda: delta_pkg.verify_export(data, empty), _frozen(data))


def an_export_checked_against_the_checkpoint_of_another_ledger_is_refused() -> List[str]:
    p = stages(SICK)
    data = _through_json(p["ledger"].export())
    other = stages(SICK, ctx={**CTX, "run_id": "run_2", "event_id": "event_2"})["checkpoint"]
    return refused(lambda: delta_pkg.verify_export(data, other), _frozen(data))


def GAP_a_rewritten_rechained_export_with_a_fresh_checkpoint_and_none_held() -> List[str]:
    """KNOWN GAP, stated as a fact. The ledger of another history (the WELL run) is exported, and verified against its own
    fresh checkpoint with no checkpoint held outside: verify_export accepts it and so does the strict check."""
    w = stages(WELL)
    return independent_check(w, _through_json(w["ledger"].export()), export_checkpoint=w["checkpoint"])


def a_rewritten_rechained_export_is_refused_by_verify_export_against_the_honest_checkpoint() -> List[str]:
    honest = stages(SICK)["checkpoint"]
    w = stages(WELL)
    data = _through_json(w["ledger"].export())
    return refused(lambda: delta_pkg.verify_export(data, honest), _frozen(data))


def a_rewritten_rechained_export_with_a_fresh_checkpoint_is_refused_against_the_held_one() -> List[str]:
    """verify_export accepts the rewrite against its own fresh checkpoint (the gap above); the strict check, given the honest
    checkpoint as `held_checkpoint`, does not."""
    honest = stages(SICK)["checkpoint"]
    w = stages(WELL)
    return independent_check(w, _through_json(w["ledger"].export()), export_checkpoint=w["checkpoint"], held=honest)


def an_export_with_require_context_cleared_is_refused() -> List[str]:
    p = stages(SICK)
    data = _through_json(p["ledger"].export())
    data["require_context"] = False
    return refused(lambda: delta_pkg.verify_export(data, p["checkpoint"], require_context=True), _frozen(data))


def zeta_refuses_to_bind_a_lock_result_to_another_entitys_context() -> List[str]:
    p = stages(SICK)
    other = {**CTX, "entity_id": "patient_2"}
    lid, result = next(iter(p["results"].items()))
    return refused(lambda: zeta_cns.lock_result_content(result, context=other, keyset_digest=p["da"]))


def a_receipt_naming_another_entrys_hashes() -> List[str]:
    return altered_receipt(lambda r: {**r, "entry_hash": "7" * 64, "previous_hash": "8" * 64})


def a_receipt_relabelled_with_another_runs_context_and_a_lying_entry_digest() -> List[str]:
    """One run's real receipt, its entry_digest wrapped in a str subclass equal to everything and its context replaced by
    another run's, offered with that other run's contents."""
    one, two = stages(SICK), stages(SICK, ctx={**CTX, "run_id": "run_2", "event_id": "event_2"})
    real, why = chain_receipt(one)
    if real is None:
        return [f"delta issued no receipt to relabel: {why}"]
    relabelled = {**real, "entry_digest": LyingHex(real["entry_digest"]), "context": two["delta"]["context"]}
    found = strict_problems(two["alpha"], two["zeta"], two["beta"], two["delta"], chain=relabelled,
                            keyset_fingerprint_of=zeta_keyset_fingerprint)
    try:
        strict_root(two["alpha"], two["zeta"], two["beta"], two["delta"], chain=relabelled, keyset_fingerprint_of=zeta_keyset_fingerprint)
        found.append("a root was issued for the relabelled receipt")
    except ValueError:
        pass
    return found


def a_receipt_with_a_str_subclass_head() -> List[str]:
    return altered_receipt(lambda r: {**r, "ledger_head": LyingHex(r["ledger_head"])})


def a_receipt_with_an_extra_key_that_prints_as_a_field() -> List[str]:
    return altered_receipt(lambda r: {**r, KeyLike("index"): 99})


def a_receipt_whose_real_key_is_replaced_by_one_that_prints_alike() -> List[str]:
    return altered_receipt(lambda r: {(KeyLike(k) if k == "index" else k): v for k, v in r.items()})


# --- the reviewers' attacks on the hardened components, with real objects (each states what must refuse it) -----------

def a_replay_with_the_content_fingerprint_blanked() -> List[str]:
    """The identical Decision brought back under a fresh event and run with its content_fingerprint blanked, so that a replay
    key which included the fingerprint would see a new record. A ledger that requires a context refuses it as a downgrade."""
    p = stages(SICK)
    blanked = dataclasses.replace(p["decision"], content_fingerprint="")
    return refused(lambda: p["ledger"].append(blanked, context={**CTX, "run_id": "run_2", "event_id": "event_2"}),
                   ledger_state(p["ledger"]))


class LyingEntity(str):
    """A str that is never equal to anything, itself included: an entity check by equality would never fire on it."""

    def __eq__(self, other: object) -> bool:
        return False

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__


def an_entity_id_that_lies_about_its_equality() -> List[str]:
    p = stages(SICK)
    ledger = DecisionLedger(require_context=True)
    lying = dataclasses.replace(p["decision"], entity_id=LyingEntity(p["decision"].entity_id))
    return refused(lambda: ledger.append(lying, context=CTX), ledger_state(ledger))


class ShiftingList(list):
    """Honest the first time it is iterated, a forged key every time after."""

    reads = 0

    def __iter__(self):
        ShiftingList.reads += 1
        return iter(list.__iter__(self)) if ShiftingList.reads == 1 else iter(["forged_key"])


def a_list_that_changes_between_reads_is_stored_as_its_first_read() -> List[str]:
    """Problems only if something other than the first read was validated or recorded."""
    p = stages(SICK)
    honest = tuple(p["decision"].triggered_by_keys)
    shifting = dataclasses.replace(p["decision"])
    ShiftingList.reads = 0
    object.__setattr__(shifting, "triggered_by_keys", ShiftingList(honest))
    ledger = DecisionLedger(require_context=True)
    out: List[str] = []
    try:
        entry = ledger.append(shifting, context=CTX)
    except (ValueError, TypeError) as exc:  # a refusal is as good as a faithful copy: nothing forged is recorded
        return [] if len(ledger.entries) == 0 else [f"refused ({type(exc).__name__}) but the ledger changed"]
    if tuple(entry.decision.triggered_by_keys) != honest:
        out.append(f"the ledger stored {entry.decision.triggered_by_keys!r}, not the first read {honest!r}")
    try:
        Decision.validate(entry.decision, check_fingerprint=True)
    except ValueError as exc:
        out.append(f"the stored Decision fails its own validation: {exc}")
    if not ledger.verify_chain_integrity():
        out.append("the ledger's chain does not verify after recording a list that changed between reads")
    return out


class NeverEarlier(datetime):
    """A datetime that says it is never earlier than anything, so an ordering check would let 1970 through."""

    def __lt__(self, other: Any) -> bool:
        return False


def a_datetime_subclass_that_backdates_an_entry() -> List[str]:
    p = stages(SICK)
    other = p["engine"].decide("patient_1", observe(WELL), LockEvaluator(build()[0]).evaluate_all("patient_1", observe(WELL), T0), T0)
    return refused(lambda: p["ledger"].append(other, timestamp=NeverEarlier(1970, 1, 1), context={**CTX, "run_id": "run_9", "event_id": "event_9"}),
                   ledger_state(p["ledger"]))


def a_sink_that_appends_to_its_own_ledger() -> List[str]:
    """The sink calls `append` on the ledger it was handed an entry by. Delta refuses with RuntimeError, before taking the
    lock it already holds, so it neither deadlocks nor records twice. The call runs in a thread with a timeout: a hang is a
    problem, not a stuck script."""
    p = stages(SICK)
    holder: List[DecisionLedger] = []

    def sink(entry: Any) -> None:
        holder[0].append(p["decision"], context={**CTX, "run_id": "run_7", "event_id": "event_7"})

    ledger = DecisionLedger(require_context=True, sink=sink)
    holder.append(ledger)
    result: List[List[str]] = []
    mine = attempts()  # the worker thread is this scenario's own: it is handed the scenario's record explicitly
    worker = threading.Thread(
        target=lambda: result.append(refused(lambda: ledger.append(p["decision"], context=CTX), ledger_state(ledger), catch=(RuntimeError,),
                                             record=mine)),
        daemon=True)
    worker.start()
    worker.join(timeout=10)
    if worker.is_alive() or not result:
        return ["the append from inside the sink did not return within 10 seconds (a deadlock)"]
    return result[0]


class AnswersHonestlyOnce(LedgerCheckpoint):
    """A checkpoint whose length and head are honest on the first read of each and a different, fitting-looking pair after."""

    def __getattribute__(self, name: str) -> Any:
        if name in ("length", "head"):
            seen = object.__getattribute__(self, "_seen")
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:
                return {"length": 7, "head": "f" * 64}[name]
        return object.__getattribute__(self, name)


def a_checkpoint_subclass_that_answers_honestly_only_once(context: Any = None) -> List[str]:
    """Delta may refuse it, or issue a receipt; if it issues one, every length and head on it must be the ones it verified.
    A refusal counts only when it is about the checkpoint: a refusal for another reason (a wrong run in the context, say)
    never reached the question and is a problem, so this row cannot pass for the wrong reason."""
    ctx = CTX if context is None else context
    p = stages(SICK)
    real = p["ledger"].checkpoint()
    sneaky = AnswersHonestlyOnce(real.length, real.head)
    object.__setattr__(sneaky, "_seen", {})
    try:
        receipt = delta_cns.verification_receipt(p["ledger"], sneaky, context=ctx, decision_digest=p["delta"]["decision_digest"])
    except (ValueError, TypeError) as exc:
        if DELTA_GENERIC_REFUSAL in str(exc):
            return []
        return [f"delta refused for a reason other than the checkpoint, so the checkpoint question was never asked: "
                f"{type(exc).__name__}: {exc}"]
    wanted = {"ledger_length": len(p["ledger"].entries), "ledger_head": p["ledger"].chain_head,
              "checkpoint_length": real.length, "checkpoint_head": real.head}
    return [f"the receipt says {k} {receipt[k]!r}, not the verified {v!r}" for k, v in wanted.items() if receipt[k] != v]


def a_receipt_asked_for_an_entry_beyond_the_checkpoint() -> List[str]:
    """The checkpoint was held before the second entry existed, so it is no independent evidence about that entry: delta
    issues no receipt for it."""
    p = stages(SICK)
    held = p["checkpoint"]
    other = p["engine"].decide("patient_1", observe(WELL), LockEvaluator(build()[0]).evaluate_all("patient_1", observe(WELL), T0), T0)
    second = {**CTX, "run_id": "run_2", "event_id": "event_2"}
    p["ledger"].append(other, context=second)
    return refused(lambda: ask_delta(p["ledger"], held, context=second, decision_digest="a" * 64), ledger_state(p["ledger"]))


def GAP_a_fully_hand_built_consistent_receipt_is_accepted() -> List[str]:
    """KNOWN GAP, stated as a fact. The receipt is not signed. Real contents from a real run, and a receipt written by hand
    with no ledger behind it: the right entry digest, hashes and context, an index of 4 in a ledger of 9, a checkpoint that
    covers all nine and one head that is neither the entry's nor any ledger's. Every field fits the others, so the strict
    check names nothing. Only where the checkpoint is kept, which CNS cannot see, tells it from delta's."""
    p = stages(SICK)
    delta = p["delta"]
    head = "1" * 64
    receipt = {"schema": "ledger-receipt/1", "entry_digest": subject_digest(delta), "index": 4,
               "entry_hash": delta["immutable_hash"], "previous_hash": delta["previous_hash"], "ledger_length": 9,
               "ledger_head": head, "checkpoint_length": 9, "checkpoint_head": head, "context": dict(CTX)}
    return strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], chain=receipt, keyset_fingerprint_of=zeta_keyset_fingerprint)


def GAP_a_sink_keeps_a_write_the_ledger_does_not_have() -> List[str]:
    """KNOWN GAP, stated as a fact, and delta's idempotency contract with it. The sink runs before the ledger changes, so a
    sink that writes to its own store and then raises leaves that write behind while the ledger holds nothing: the store has
    an entry the ledger never recorded. A retry hands the sink the same entry (same immutable_hash), so a store keyed by it
    holds one record, not two. Delta supplies the hook, not the storage; the sink must be idempotent and the caller must
    reconcile. No problem is found when the fact holds; one is reported if the phantom write ever disappears."""
    p = stages(SICK)
    store: Dict[str, Any] = {}
    failing = [True]

    def sink(entry: Any) -> None:
        store[entry.immutable_hash] = entry  # idempotent: keyed by the entry's own hash
        if failing[0]:
            raise RuntimeError("the store's acknowledgement was lost")

    ledger = DecisionLedger(require_context=True, sink=sink)
    out = refused(lambda: ledger.append(p["decision"], context=CTX), catch=(RuntimeError,))
    if not out:
        return ["the failing sink did not stop the append"]
    out = []
    if len(ledger.entries) != 0:
        out.append("the ledger recorded an entry although its sink raised")
    if len(store) != 1:
        out.append(f"the gap has closed: the sink's own store holds {len(store)} write(s) after the ledger refused, not the one phantom")
    failing[0] = False
    ledger.append(p["decision"], context=CTX)
    if len(ledger.entries) != 1 or len(store) != 1:
        out.append(f"the retry is not idempotent: the ledger holds {len(ledger.entries)} and the store {len(store)}")
    if set(store) != {ledger.entries[0].immutable_hash}:
        out.append("the retry handed the sink a different entry than the one it first wrote")
    return out


# --- the hardened components, attacked as the matrix did (row numbers are the attack matrix's) -------------------------

def a_forged_chain_verified_flag() -> List[str]:
    """Row 7. The ledger's chain is broken after the run and the caller asserts chain_verified=True. The flag is a bare
    assertion: it warns and is a problem whatever it says."""
    p = stages(SICK)
    first = p["ledger"].entries[0]
    p["ledger"].entries[0] = dataclasses.replace(first, decision=dataclasses.replace(first.decision, instructions="Send home."))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        found = strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], chain_verified=True,
                                keyset_fingerprint_of=zeta_keyset_fingerprint)
    if not any(issubclass(w.category, DeprecationWarning) for w in caught):
        found.append("the deprecated chain_verified alias did not warn")
    return found


class AlwaysEqual:
    """Not a str, and equal to everything: what a checkpoint head must not be allowed to be."""

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = None  # type: ignore[assignment]


def rewrite_the_run_completely(honest_checkpoint_is_stale: bool = True) -> Dict[str, Any]:
    """Row 11. A real rewrite: the run was SICK and its ledger entry and four exports are replaced, in place, by another
    history's (the WELL run under the same context): the same ledger object now holds different entries and head, and every
    export describes the new history and chains. The ledger's own chain still verifies, so only a checkpoint held outside
    can tell. The checkpoint the original run left is checked to be refused for the rewrite (it is stale), so the rewrite is
    shown to be a rewrite and not a second honest run."""
    p = stages(SICK)
    original = p["checkpoint"]
    q = stages(WELL)
    p["ledger"].entries[:] = list(q["ledger"].entries)
    p["ledger"].chain_head = q["ledger"].chain_head
    p.update(alpha=q["alpha"], zeta=q["zeta"], beta=q["beta"], delta=q["delta"])
    if not p["ledger"].verify_chain_integrity():
        raise AssertionError("the rewritten ledger is expected to verify on its own chain: that is what a rewrite does")
    receipt, why = chain_receipt({**p, "checkpoint": original})
    if receipt is not None:
        raise AssertionError("delta accepted the checkpoint of the original history for the rewritten ledger")
    if "unmatched checkpoint" not in why:
        raise AssertionError(f"the original checkpoint was refused, but not as one naming no entry of the rewrite: {why}")
    return p


def a_complete_rewrite_against_an_empty_checkpoint() -> List[str]:
    """Row 11b. The run is rewritten completely (ledger and exports) and verified against a checkpoint of length 0, which
    fits every self-consistent ledger. Delta refuses to issue a receipt against it."""
    q = rewrite_the_run_completely()
    q["checkpoint"] = LedgerCheckpoint(0, q["ledger"].chain_head)  # the rewritten ledger's own head: removing the length-0 guard turns this red
    return check(q)


def a_complete_rewrite_against_a_checkpoint_head_that_equals_everything() -> List[str]:
    """Row 11c. The same rewrite verified against a checkpoint whose head is an object whose __eq__ is always true."""
    q = rewrite_the_run_completely()
    q["checkpoint"] = LedgerCheckpoint(1, AlwaysEqual())  # type: ignore[arg-type]
    return check(q)


def the_identical_decision_replayed_under_a_fresh_event_and_run() -> List[str]:
    """Row 12b. The same Decision brought back under a new event id and a new run id is a replay, not a new decision."""
    p = stages(SICK)
    return refused(lambda: p["ledger"].append(p["decision"], context={**CTX, "run_id": "run_2", "event_id": "event_2"}),
                   ledger_state(p["ledger"]))


def a_backdated_entry_timestamp() -> List[str]:
    """Row 14b. A contradictory Decision at the same instant is not stale (equal times are allowed), but recording it with
    an entry time of 1970 is a backdated entry."""
    p = stages(SICK)
    other = p["engine"].decide("patient_1", observe(WELL), LockEvaluator(build()[0]).evaluate_all("patient_1", observe(WELL), T0), T0)
    return refused(lambda: p["ledger"].append(other, timestamp=datetime(1970, 1, 1), context={**CTX, "run_id": "run_9", "event_id": "event_9"}),
                   ledger_state(p["ledger"]))


def an_injected_failure_during_append_leaves_the_ledger_as_it_was() -> List[str]:
    """Row 16a. The write fails inside the append (here the sink every entry is handed to). Length and head are unchanged
    and the ledger still takes the next record; before, the head had already moved and every later append was refused."""
    p = stages(SICK)
    failing = [True]

    def sink(entry: Any) -> None:
        if failing[0]:
            raise RuntimeError("the store refused the write")

    ledger = DecisionLedger(require_context=True, sink=sink)
    found = refused(lambda: ledger.append(p["decision"], context=CTX), ledger_state(ledger), catch=(RuntimeError,))
    failing[0] = False
    try:
        ledger.append(p["decision"], context=CTX)
    except Exception as exc:  # noqa: BLE001 - a ledger that cannot take the retry is unavailable after the fault
        found.append(f"the ledger took no further record after the failure: {type(exc).__name__}: {exc}")
    if not ledger.verify_chain_integrity() or len(ledger.entries) != 1:
        found.append("the ledger does not hold exactly the one retried entry, with a chain that verifies")
    return found


def lock_results_from_another_entity_are_refused_by_beta() -> List[str]:
    """Row 21. Patient 2's latched lock state, evaluated over patient 1's readings, offered to decide for patient 1. Each
    result now records the entity it was evaluated for."""
    locks, engine = build()
    ev = LockEvaluator(locks)
    ev.evaluate_all("patient_2", observe(SICK), T0)  # patient 2 latches sepsis_lock open
    well = observe(WELL)
    at = T0 + timedelta(minutes=5)
    borrowed = ev.evaluate_all("patient_2", well, at)
    return refused(lambda: engine.decide("patient_1", well, borrowed, at))


def GAP_a_legacy_lock_result_with_no_entity_id_is_accepted() -> List[str]:
    """KNOWN GAP, stated as a fact, kept for compatibility. A LockResult with an empty entity_id (what zeta produced before
    it recorded one, or any object a caller builds) is accepted for any entity: the field is caller-settable and empty
    means legacy. The same cross-entity borrowing as the scenario before this one, with the entity stripped, is decided."""
    locks, engine = build()
    ev = LockEvaluator(locks)
    ev.evaluate_all("patient_2", observe(SICK), T0)
    well = observe(WELL)
    at = T0 + timedelta(minutes=5)
    legacy = {lid: dataclasses.replace(r, entity_id="") for lid, r in ev.evaluate_all("patient_2", well, at).items()}
    return refused(lambda: engine.decide("patient_1", well, legacy, at))


def str_subclass_ids_in_a_context_are_refused() -> List[str]:
    """Row 22. Event and run ids that are equal only to themselves would walk past an equality-based event policy."""
    p = stages(SICK)
    ledger = DecisionLedger(require_context=True)
    return refused(lambda: ledger.append(p["decision"], context={**CTX, "event_id": StrSub("event_1"), "run_id": StrSub("run_1")}),
                   ledger_state(ledger))


def a_context_mapping_that_changes_between_reads_is_recorded_as_first_read() -> List[str]:
    """Row 23. A mapping valid on its first read and different afterwards is recorded as the context that was validated,
    by delta and by alpha, never as a later value. Problems are returned only if a later value got through."""
    p = stages(SICK)
    out: List[str] = []
    ledger = DecisionLedger(require_context=True)
    entry = ledger.append(p["decision"], context=Shifty())
    if (entry.run_id, entry.event_id) != (CTX["run_id"], CTX["event_id"]):
        out.append(f"the ledger recorded run {entry.run_id!r} and event {entry.event_id!r}, not the context that was validated")
    if alpha_cns.keyset_content(p["keys"], context=Shifty())["context"] != CTX:
        out.append("alpha bound a context other than the one that was validated")
    return out


def a_list_the_caller_mutates_after_recording_does_not_reach_the_stored_decision() -> List[str]:
    """Row 26. Lists aliased into a Decision's tuple fields and changed after the append cannot reach the record."""
    p = stages(SICK)
    rc = ["Recheck in 1h"]
    d = dataclasses.replace(p["decision"], reversal_conditions=("Recheck in 1h",))
    d = dataclasses.replace(d, content_fingerprint=content_fingerprint(d))
    object.__setattr__(d, "reversal_conditions", rc)  # the same text as a list that skipped the tuple coercion of construction
    ledger = DecisionLedger(require_context=True)
    entry = ledger.append(d, context=CTX)
    held = ledger.checkpoint()
    rc.append("Ignore all alarms")
    out: List[str] = []
    if tuple(entry.decision.reversal_conditions) != ("Recheck in 1h",):
        out.append(f"the stored Decision changed through the caller's list: {entry.decision.reversal_conditions!r}")
    if not ledger.verify_chain_integrity() or not ledger.verify_against(held):
        out.append("the ledger's chain no longer verifies after the caller mutated its own list")
    return out


class StrSub(str):
    """A str subclass that is equal only to itself, so an equality-based policy (an event is recorded once) would miss
    it. A context built from one is refused everywhere: a subclass can lie about equality, hash or text."""

    def __eq__(self, other: object) -> bool:
        return self is other

    def __ne__(self, other: object) -> bool:
        return self is not other

    __hash__ = str.__hash__


class Shifty(Mapping):
    """A mapping that answers differently on every read after the first of each key: run_id is valid once, then empty.
    A copy-once validator accepts it and returns the first read; one that reads again records or judges something else."""

    def __repr__(self) -> str:
        return "Shifty(valid on the first read, run_id empty after)"

    def __init__(self) -> None:
        self._seen: set = set()

    def __getitem__(self, key: str) -> Any:
        if key in self._seen and key == "run_id":
            return ""
        self._seen.add(key)
        return CTX[key]

    def __iter__(self):
        return iter(CTX)

    def __len__(self) -> int:
        return len(CTX)


CONTEXT_CASES: List[Any] = [
    dict(CTX), {k: v for k, v in CTX.items() if k != "run_id"}, {**CTX, "extra": "x"}, {**CTX, "run_id": ""},
    {**CTX, "event_id": 4}, {**CTX, "schema": "spine-context/2"}, {**CTX, "entity_id": None}, "run_1", None, [], {},
    {**CTX, "run_id": StrSub("run_1")}, {**CTX, "entity_id": StrSub("patient_1")}, Shifty(),
]


def connectors_agree_with_cns_on_what_a_context_is() -> List[str]:
    """Four repositories each validate their own copy of the context. CNS states the contract; they must agree with it.
    An accepted context must also come back as the plain snapshot of the FIRST read (exact str values), so a mapping that
    changes between reads is never recorded as something it was not when it was checked."""
    out: List[str] = []
    checks = {"alpha": alpha_cns._context, "zeta": zeta_cns._context, "beta": beta_cns._context,
              "delta": delta_context.check_context}

    def fresh(case: Any) -> Any:
        return Shifty() if isinstance(case, Shifty) else case

    for case in CONTEXT_CASES:
        cns_accepts = not context_problems(fresh(case))
        for name, validate in checks.items():
            try:
                kept = validate(fresh(case))
                accepts = True
            except (ValueError, TypeError, OverflowError):
                accepts, kept = False, None
            if accepts != cns_accepts:
                out.append(f"{name} {'accepts' if accepts else 'refuses'} {case!r} and CNS {'accepts' if cns_accepts else 'refuses'} it")
            elif accepts and (type(kept) is not dict or kept != CTX or any(type(v) is not str for v in kept.values())):
                out.append(f"{name} accepted {case!r} but returned {kept!r}, not the plain first-read snapshot")
    return out


# --- the oracle held to account with real objects (hacker1 F58 to F66): each returns no problem when the oracle failed
# --- what it should fail, and names the attack that went through when it did not -------------------------------------

def _oracle_must_flag(what: str, expect: Expect, scenario: Callable[[], List[str]]) -> List[str]:
    _, why = judge(expect, scenario)
    return [] if why else [f"the oracle judged this scenario a pass: {what}"]


def _expect_of(name: str) -> Expect:
    return next(e for n, _, e in SCENARIOS if n == name)


def the_oracle_flags_a_component_that_exits() -> List[str]:
    """F65. A scenario whose component raises SystemExit(0) is a failed scenario; before, it ended the run green with the
    remaining rows never judged. Here it must not propagate out of `judge`."""
    def exits() -> List[str]:
        raise SystemExit(0)
    return _oracle_must_flag("a component that exits", CLEAN, exits)


def the_oracle_flags_a_refusal_that_edited_an_entrys_content() -> List[str]:
    """F61. Inside a refused call an entry's Decision is edited, its hashes kept, and the expected refusal raised. The state
    digest covers the whole entry, so the refusal is flagged; before, it covered hashes only."""
    ledger = stages(SICK)["ledger"]

    def tamper_then_refuse() -> None:
        entry = ledger.entries[0]
        ledger.entries[0] = dataclasses.replace(entry, decision=dataclasses.replace(entry.decision, instructions="Send home."))
        raise DuplicateRecordError("run 'run_1' already recorded a Decision for event 'event_1'")
    return _oracle_must_flag("a refusal that edited an entry's content", _expect_of("strict: the same Decision recorded twice in one run"),
                             lambda: refused(tamper_then_refuse, ledger_state(ledger), catch=(DuplicateRecordError,)))


def the_oracle_flags_refusal_text_returned_while_the_attack_succeeded() -> List[str]:
    """F60. The append succeeds and the scenario returns the refusal text anyway; before, returned text was all the oracle
    judged."""
    p = stages(SICK)
    ledger = DecisionLedger(require_context=True)

    def lies() -> List[str]:
        ledger.append(p["decision"], context=CTX)
        return ["DuplicateRecordError: run 'run_1' already recorded a Decision for event 'event_1'"]
    return _oracle_must_flag("refusal text with the attack through", _expect_of("strict: the same Decision recorded twice in one run"), lies)


def the_oracle_refuses_expect_texts_that_match_anything() -> List[str]:
    """F64. A str subclass whose length lies, and a text of one space, are construction errors; before, both built an
    Expect that matched any problem."""
    class Truthy(str):
        def __len__(self) -> int:
            return 1
    out: List[str] = []
    for label, text in (("a str subclass", Truthy("")), ("a single space", " ")):
        try:
            Expect("problems", required=(text,))
        except (TypeError, ValueError):
            continue
        out.append(f"an Expect was built from {label} and would match any problem")
    return out


def a_rewrite_of_the_ledger_itself_is_not_called_a_wrong_ledger() -> List[str]:
    """F59. The checkpoint the original run left, asked of the rewritten ledger, is refused. Length and head cannot say whether
    it came from another ledger or from this one before it was rewritten, so the cause must not claim the first."""
    q = rewrite_the_run_completely()
    _, why = chain_receipt({**q, "checkpoint": q["checkpoint"]})
    out: List[str] = []
    if "wrong-ledger" in why:
        out.append(f"a same-ledger rewrite was labelled wrong-ledger: {why}")
    if "rewritten" not in why:
        out.append(f"the cause does not name the rewrite of this ledger's own history: {why}")
    return out


def a_checkpoint_row_cannot_pass_on_an_unrelated_refusal() -> List[str]:
    """F66. The checkpoint-subclass row with a context for another run: delta refuses at the run check, before the
    checkpoint is asked; before, that returned no problems and the row passed anyway."""
    return a_checkpoint_subclass_that_answers_honestly_only_once(context={**CTX, "run_id": "run_X"})


# --- the manifest checks, attacked with real git and real-shaped pyproject text (hacker1 E50, hacker2 74b/74c/75) ------

_M_A, _M_Z, _M_B, _M_D = ("a" * 40, "b" * 40, "c" * 40, "d" * 40)
_M_CNS = "41592fb7b6735abe140f745353c09ba3eed8e7a2"
_M_MANIFEST = {"schema": spine_manifest.SCHEMA, "cns": {"tag": "v2.3.0", "commit": _M_CNS},
               "repos": {"interconnected_alpha": _M_A, "interconnected_zeta": _M_Z, "interconnected_beta": _M_B, "interconnected_delta": _M_D}}
_M_RELEASES = {"releases": [{"ref": "v2.3.0", "commit": _M_CNS, "version": "2.3.0"}]}


def _pyproject(deps: Tuple[Tuple[str, str], ...], inside: str = "") -> str:
    lines = "".join(f'    "{n} @ git+https://github.com/wking53214/interconnected_{n}@{ref}",\n' for n, ref in deps)
    return (f'[project]\nname = "x"\n{inside}dependencies = [\n{lines}]\n\n[project.optional-dependencies]\ndev = ["pytest>=7.0"]\n'
            f'cns = ["cns @ git+https://github.com/wking53214/CNS.git@v2.3.0"]\n')


def _manifest_texts(delta: str) -> Dict[str, str]:
    return {"interconnected_alpha": _pyproject((("zeta", _M_Z),)), "interconnected_zeta": _pyproject(()),
            "interconnected_beta": _pyproject((("zeta", _M_Z),)), "interconnected_delta": delta}


def a_dependency_hidden_behind_a_bracket_in_a_comment() -> List[str]:
    """E50. A comment line ending in `]` ended the dependency list early for the old reader, so `evil-pkg` after it was never
    read while pip still installs it. Read as TOML (or refused when it cannot be read completely), it is not accepted."""
    good = _pyproject((("zeta", _M_Z), ("beta", _M_B)))
    hidden = good.replace('dependencies = [\n', 'dependencies = [\n    # see issue [12]\n    "evil-pkg>=1",\n', 1)
    return spine_manifest.check(_M_MANIFEST, _manifest_texts(hidden), dict(_M_MANIFEST["repos"]), _M_RELEASES)


def a_decoy_dependency_list_in_a_multiline_string() -> List[str]:
    """74b V13. A decoy `dependencies = [...]` inside a multi-line string, and the real list pinning zeta from an attacker at a
    branch. The old reader saw the decoy. TOML sees the real list; the 3.10 fallback refuses the multi-line string."""
    decoy = (f'description = """\ndependencies = [\n    "zeta @ git+https://github.com/wking53214/interconnected_zeta@{_M_Z}",\n]\n"""\n')
    real = _pyproject((("zeta", "main"), ("beta", _M_B)), inside=decoy).replace("wking53214/interconnected_zeta@main", "attacker/interconnected_zeta@main")
    return spine_manifest.check(_M_MANIFEST, _manifest_texts(real), dict(_M_MANIFEST["repos"]), _M_RELEASES)


def a_checkout_at_the_pinned_commit_with_an_edited_file() -> List[str]:
    """74c. HEAD is the commit the manifest names, but a tracked file was edited and another planted: the files that are
    imported are not that commit. The old check read `git rev-parse HEAD` only."""
    import subprocess
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        git = ["git", "-C", str(folder), "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", str(folder)], check=True)
        (folder / "mod.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
        head = subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        (folder / "mod.py").write_text("x = 2\n", encoding="utf-8")
        (folder / "planted.py").write_text("print('untracked')\n", encoding="utf-8")
        status = spine_manifest._status(folder)
    manifest = {**_M_MANIFEST, "repos": {**_M_MANIFEST["repos"], "interconnected_zeta": head}}
    texts = _manifest_texts(_pyproject((("zeta", head), ("beta", _M_B))))
    texts["interconnected_alpha"] = texts["interconnected_beta"] = _pyproject((("zeta", head),))
    heads = dict(manifest["repos"])
    clean: Dict[str, Any] = {r: [] for r in spine_manifest.SPINE}
    return spine_manifest.check(manifest, texts, heads, _M_RELEASES, dirty={**clean, "interconnected_zeta": status})


def an_older_zeta_installed_beside_the_others() -> List[str]:
    """75. An older zeta was silently accepted. What pip recorded for the installed distribution (direct_url.json) names the
    commit, and `--installed` holds it to the manifest's."""
    def vcs(repo: str, commit: str) -> Dict[str, Any]:
        return {"direct_url": {"url": f"https://github.com/wking53214/{repo}", "vcs_info": {"vcs": "git", "commit_id": commit}},
                "location": "/site", "imported_from": f"/site/{repo.split('_')[1]}/__init__.py"}
    installed = {pkg: [vcs(repo, _M_MANIFEST["repos"][repo])] for repo, pkg in spine_manifest.SPINE.items()}
    installed["zeta"] = [vcs("interconnected_zeta", "f416b02" + "0" * 33)]
    return spine_manifest.installed_problems(_M_MANIFEST, installed)


def the_reference_keys_sign_verify_rotate_and_revoke() -> List[str]:
    """Step 1. The deployer's reference keys (chains/receipt_keys.py), held to what they document: a signature verifies under
    its own trusted key and no other, an unknown or revoked key id never verifies, rotation keeps the old key verifying until it
    is retired, and a verifier answers False (never raises) for input that is not a signature."""
    old, new, other = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    data = b"some bytes to vouch for"
    sign_old, sign_new = receipt_keys.make_signer(old, "k1"), receipt_keys.make_signer(new, "k2")
    trust_old = {"k1": old.public_key()}
    trust_both = {"k1": old.public_key(), "k2": new.public_key()}
    out: List[str] = []

    def expect(label: str, got: Any, want: bool) -> None:
        if got is not want:
            out.append(f"{label}: expected {want}, got {got!r}")

    expect("a signature under its trusted key", receipt_keys.make_verifier(trust_old)(data, sign_old(data)), True)
    expect("the same signature over other bytes", receipt_keys.make_verifier(trust_old)(data + b"!", sign_old(data)), False)
    expect("a key id the trust list does not hold", receipt_keys.make_verifier(trust_old)(data, sign_new(data)), False)
    expect("a trusted id signed by another key", receipt_keys.make_verifier(trust_old)(data, receipt_keys.make_signer(other, "k1")(data)), False)
    expect("a revoked key that is still listed", receipt_keys.make_verifier(trust_old, revoked={"k1"})(data, sign_old(data)), False)
    expect("rotation: the old key while both are trusted", receipt_keys.make_verifier(trust_both)(data, sign_old(data)), True)
    expect("rotation: the new key", receipt_keys.make_verifier(trust_both)(data, sign_new(data)), True)
    expect("rotation: the old key once retired", receipt_keys.make_verifier({"k2": new.public_key()})(data, sign_old(data)), False)
    expect("rotation: the new key once the old is revoked", receipt_keys.make_verifier(trust_both, revoked={"k1"})(data, sign_new(data)), True)
    verify = receipt_keys.make_verifier(trust_both)
    for label, junk in (("no key id", b"nocolon"), ("an empty envelope", b""), ("a str", "k1:sig"), ("an empty signature", b"k1:"),
                        ("a key id that is not UTF-8", b"\xff\xfe:sig")):
        expect(f"input that is not a signature ({label})", verify(data, junk), False)
    expect("data that is not bytes", verify("text", sign_old(data)), False)
    for bad in ("", "a:b", 7, None):
        if not refused(lambda bad=bad: receipt_keys.make_signer(old, bad)):
            out.append(f"a key id {bad!r} was accepted by make_signer")
    trust_both["k1"] = other.public_key()  # the verifier took a snapshot: editing the dict afterwards changes nothing
    expect("a trust dict edited after make_verifier", verify(data, sign_old(data)), True)
    return out


def a_trust_list_that_is_ambiguous_is_refused() -> List[str]:
    """The trust list is the deployer's whole authority, so a list that can be read two ways is refused rather than guessed:
    one public key under two ids (revoking one id would leave the other), a revoked id that names no trusted id (a typo, a
    case or Unicode-normalisation difference revokes nothing), one id twice in the JSON (the last would win silently), and an
    id outside ASCII (NFC and NFD spell the same id differently). Each is a ValueError from the file reader AND from the verifier
    builder, and a valid list is still accepted."""
    a, b = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    ha, hb = receipt_keys.public_key_hex(a.public_key()), receipt_keys.public_key_hex(b.public_key())
    nfc = unicodedata.normalize("NFC", "k\u00e9")
    nfd = unicodedata.normalize("NFD", nfc)
    out: List[str] = []

    def both_refuse(label: str, text: str, trust: Dict[str, Any], revoked: Tuple[str, ...]) -> None:
        if not refused(lambda: receipt_keys.trust_from_json(text)):
            out.append(f"{label}: trust_from_json accepted it")
        if not refused(lambda: receipt_keys.make_verifier(trust, revoked)):
            out.append(f"{label}: make_verifier accepted it")

    def doc(keys: str, revoked: str = "[]") -> str:
        return '{"keys": {' + keys + '}, "revoked": ' + revoked + '}'

    both_refuse("one public key under two ids", doc(f'"old": "{ha}", "new": "{ha}"', '["old"]'),
                {"old": a.public_key(), "new": a.public_key()}, ("old",))
    both_refuse("a revoked id that matches no trusted id", doc(f'"k1": "{ha}"', '["k2"]'), {"k1": a.public_key()}, ("k2",))
    both_refuse("a revoked id that differs from the trusted one only in case", doc(f'"k1": "{ha}"', '["K1"]'),
                {"k1": a.public_key()}, ("K1",))
    both_refuse("a non-ASCII id (NFC)", doc(f'"{nfc}": "{ha}"'), {nfc: a.public_key()}, ())
    both_refuse("a non-ASCII id (NFD)", doc(f'"{nfd}": "{ha}"'), {nfd: a.public_key()}, ())
    both_refuse("a revoked NFD spelling of an NFC id", doc(f'"{nfc}": "{ha}"', json.dumps([nfd])), {nfc: a.public_key()}, (nfd,))
    if not refused(lambda: receipt_keys.trust_from_json(doc(f'"k1": "{hb}", "k1": "{ha}"'))):
        out.append("one id twice in the JSON: the last silently won")
    if not refused(lambda: receipt_keys.make_signer(a, nfc)):
        out.append("make_signer accepted a non-ASCII id")
    trust, revoked = receipt_keys.trust_from_json(doc(f'"k1": "{ha}", "k2": "{hb}"', '["k1"]'))
    if sorted(trust) != ["k1", "k2"] or revoked != frozenset({"k1"}):
        out.append("a valid trust list with one revoked id was not read back as written")
    with packages(()) as (pkg,):  # the command: an ambiguous trust file is an input that cannot be read, exit 2
        for label, text in (("a key under two ids", doc(f'"old": "{ha}", "new": "{ha}"', '["old"]')),
                            ("a revoked id that names nothing", doc(f'"k1": "{ha}"', '["k2"]')),
                            ("an id twice", doc(f'"k1": "{hb}", "k1": "{ha}"'))):
            with open(os.path.join(pkg.root, "ambiguous.json"), "w", encoding="utf-8") as fh:
                fh.write(text)
            done = pkg.verify(trust=os.path.join(pkg.root, "ambiguous.json"))
            if done.returncode != 2 or "Traceback" in done.stderr:
                out.append(f"verify_package with a trust file with {label}: exit {done.returncode}, stderr {done.stderr.strip()[-160:]!r}")
    return out


# --- signed receipts: the deployer's keys, Delta's signing hook, CNS's verification (Step 2) -----------------------------

#: Fresh keys for each run of the script; nothing is hard-coded. The deployer's key is the one the verifier trusts.
DEPLOYER_KEY, NEW_KEY, STRANGER_KEY = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
BAD_SIGNATURE = spine_trace.RECEIPT_SIGNATURE_BAD
SIGNATURE_REQUIRED = spine_trace.RECEIPT_SIGNATURE_REQUIRED
VERIFIER_NO_SIGNATURE = spine_trace.RECEIPT_SIGNATURE_VERIFIER_NO_SIGNATURE


def deployer_verifier(*, also=(), revoked=()):
    """The verifier a deployer builds from the keys it trusts: key id k1 (the deployer's), plus any `(id, key)` in `also`."""
    trust = {"k1": DEPLOYER_KEY.public_key(), **{kid: key.public_key() for kid, key in also}}
    return receipt_keys.make_verifier(trust, revoked)


def signed_run(vitals=SICK, ctx=CTX, key=None, key_id="k1"):
    """A real run, the receipt Delta issues for it, and the signature Delta's hook makes with the deployer's `sign`."""
    p = stages(vitals, ctx)
    receipt, why = chain_receipt(p)
    if receipt is None:
        raise ValueError(f"delta issued no receipt: {why}")
    return p, receipt, delta_signing.sign_receipt(receipt, receipt_keys.make_signer(key or DEPLOYER_KEY, key_id))


def signed_check(p, receipt, signature, verifier, *, required=True, held=True) -> List[str]:
    """CNS's strict check with the signature arguments, then the root asked the same way: a root is issued exactly when no
    problem is named. The check is run as a deployer runs it (the zeta recomputation, the checkpoint held outside)."""
    kw: Dict[str, Any] = dict(chain=receipt, keyset_fingerprint_of=zeta_keyset_fingerprint, receipt_signature=signature,
                              verify_receipt_signature=verifier, require_signed_receipt=required)
    if held:
        kw["held_checkpoint"] = (p["checkpoint"].length, p["checkpoint"].head)
    found = strict_problems(p["alpha"], p["zeta"], p["beta"], p["delta"], **kw)
    try:
        issued = strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], **kw)
    except ValueError:
        issued = None
    if found and issued is not None:
        found.append("a root was issued although problems were named")
    if not found and issued is None:
        found.append("no root was issued although no problem was named")
    return found


def a_receipt_signed_by_the_deployer_is_verified_and_a_root_issued() -> List[str]:
    p, receipt, signature = signed_run()
    verifier = deployer_verifier()
    out = signed_check(p, receipt, signature, verifier)
    kw: Dict[str, Any] = dict(chain=receipt, keyset_fingerprint_of=zeta_keyset_fingerprint,
                              held_checkpoint=(p["checkpoint"].length, p["checkpoint"].head))
    unsigned = strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], **kw)
    signed = strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], receipt_signature=signature,
                         verify_receipt_signature=verifier, require_signed_receipt=True, **kw)
    return out + ([] if signed != unsigned else ["a root issued with a verified signature equals the unsigned root"])


def an_unsigned_receipt_is_refused_when_a_signature_is_required() -> List[str]:
    p, receipt, _ = signed_run()
    return signed_check(p, receipt, None, deployer_verifier())


def a_verifier_without_a_signature_is_refused_without_the_requirement() -> List[str]:
    """Supplying the verifier says the receipt is meant to be authentic: stripping the signature is not a downgrade."""
    p, receipt, _ = signed_run()
    return signed_check(p, receipt, None, deployer_verifier(), required=False)


def a_requirement_with_no_verifier_and_no_signature_is_refused() -> List[str]:
    p, receipt, _ = signed_run()
    return signed_check(p, receipt, None, None, required=True)


def a_hand_built_consistent_receipt_with_no_delta_call_and_no_key_is_refused() -> List[str]:
    """The receipt of GAP_a_fully_hand_built_consistent_receipt_is_accepted, which the unsigned check accepts: every field
    fits the others, nothing behind it. Asked for a signature, its author has none to give."""
    p = stages(SICK)
    head = "1" * 64
    receipt = {"schema": "ledger-receipt/1", "entry_digest": subject_digest(p["delta"]), "index": 4,
               "entry_hash": p["delta"]["immutable_hash"], "previous_hash": p["delta"]["previous_hash"], "ledger_length": 9,
               "ledger_head": head, "checkpoint_length": 9, "checkpoint_head": head, "context": dict(CTX)}
    return signed_check(p, receipt, None, deployer_verifier(), held=False)


def a_receipt_signed_by_an_untrusted_key() -> List[str]:
    p, receipt, signature = signed_run(key=STRANGER_KEY, key_id="stranger")
    return signed_check(p, receipt, signature, deployer_verifier())


def a_receipt_signed_by_a_key_claiming_the_deployers_id() -> List[str]:
    p, receipt, signature = signed_run(key=STRANGER_KEY, key_id="k1")
    return signed_check(p, receipt, signature, deployer_verifier())


def a_receipt_signed_by_a_revoked_key() -> List[str]:
    p, receipt, signature = signed_run()
    return signed_check(p, receipt, signature, deployer_verifier(revoked={"k1"}))


def a_signature_over_another_receipt() -> List[str]:
    p, receipt, _ = signed_run()
    _, _, other = signed_run(SICK, ctx={**CTX, "run_id": "run_2"})
    return signed_check(p, receipt, other, deployer_verifier())


def a_receipt_edited_after_signing() -> List[str]:
    """Each of several fields of the signed receipt is changed alone; the signature must name every one of them. The other
    problems an edit also causes (the receipt no longer fits the contents) are not what this asks, so only the signature's
    verdict is kept, and a root must not be issued."""
    p, receipt, signature = signed_run()
    verifier = deployer_verifier()
    flip = lambda h: ("0" if h[0] != "0" else "1") + h[1:]  # noqa: E731
    edits = {"entry_digest": lambda r: r.update(entry_digest=flip(r["entry_digest"])),
             "entry_hash": lambda r: r.update(entry_hash=flip(r["entry_hash"])),
             "previous_hash": lambda r: r.update(previous_hash=flip(r["previous_hash"])),
             "ledger_head": lambda r: r.update(ledger_head=flip(r["ledger_head"])),
             "checkpoint_head": lambda r: r.update(checkpoint_head=flip(r["checkpoint_head"])),
             "ledger_length": lambda r: r.update(ledger_length=r["ledger_length"] + 1),
             "checkpoint_length": lambda r: r.update(checkpoint_length=r["checkpoint_length"] + 1),
             "index": lambda r: r.update(index=r["index"] + 1),
             "schema": lambda r: r.update(schema="ledger-receipt/2"),
             "context.run_id": lambda r: r["context"].update(run_id="run_2")}
    out: List[str] = []
    for name, edit in edits.items():
        edited = {**receipt, "context": dict(receipt["context"])}
        edit(edited)
        found = signed_check(p, edited, signature, verifier)
        if BAD_SIGNATURE not in "; ".join(found):
            out.append(f"{name}: the edit was not caught by the signature")
        elif not any("a root was issued" in f for f in found):
            out.append(f"{name}: {BAD_SIGNATURE}")
        else:
            out.append(f"{name}: a root was issued for an edited receipt")
    return out


def rotation_keeps_the_old_key_verifying_until_it_is_retired() -> List[str]:
    p_old, receipt_old, sig_old = signed_run()
    p_new, receipt_new, sig_new = signed_run(ctx={**CTX, "run_id": "run_2"}, key=NEW_KEY, key_id="k2")
    both = deployer_verifier(also=[("k2", NEW_KEY)])
    return signed_check(p_old, receipt_old, sig_old, both) + signed_check(p_new, receipt_new, sig_new, both)


def a_receipt_of_a_retired_key_is_refused_after_rotation() -> List[str]:
    p, receipt, signature = signed_run()
    retired = receipt_keys.make_verifier({"k2": NEW_KEY.public_key()})
    return signed_check(p, receipt, signature, retired)


def the_two_receipt_signing_inputs_do_not_drift() -> List[str]:
    """DRIFT. CNS carries its own `receipt_signing_input` (it imports no repository) and Delta its own. A signature made over
    one and checked over the other only works while they are byte-equal, so this holds them equal over valid receipts and
    equal in refusal over invalid ones: whatever one refuses, the other refuses (the exception class may differ)."""
    import copy
    real = signed_run()[1]
    other = signed_run(WELL, ctx={**CTX, "run_id": "run_2", "event_id": "event_2"})[1]
    astral, pair = chr(0x1F600), chr(0xD83D) + chr(0xDE00)

    def variant(base, **over):
        r = copy.deepcopy(base)
        for k, v in over.items():
            if k.startswith("ctx."):
                r["context"][k[4:]] = v
            else:
                r[k] = v
        return r

    class S(str):
        pass

    class I(int):  # noqa: E742
        pass

    class D(dict):
        pass

    valid = {"a real receipt": real, "another run's": other, "non-ASCII ids": variant(real, **{"ctx.entity_id": "patient_\u00e9\u4e2d"}),
             "an astral character": variant(real, **{"ctx.run_id": "run_" + astral}), "empty strings": variant(real, **{"ctx.run_id": ""}),
             "a huge int": variant(real, index=10 ** 30), "zero lengths": variant(real, index=0, ledger_length=0, checkpoint_length=0),
             "an escaped quote": variant(real, **{"ctx.event_id": 'e"\\\n'})}
    broken = {"a lone surrogate": variant(real, entry_hash=chr(0xD83D)), "a surrogate pair": variant(real, **{"ctx.run_id": pair}),
              "a lone surrogate in the context": variant(real, **{"ctx.entity_id": chr(0xDE00)}),
              "an extra key": {**real, "extra": 1}, "a missing key": {k: v for k, v in real.items() if k != "index"},
              "a bool index": variant(real, index=True), "a bool length": variant(real, ledger_length=False),
              "a negative index": variant(real, index=-1), "a negative length": variant(real, checkpoint_length=-5),
              "a float index": variant(real, index=0.0), "a str-subclass hash": variant(real, ledger_head=S(real["ledger_head"])),
              "an int-subclass index": variant(real, index=I(0)), "a dict subclass": D(real),
              "a context with an extra key": variant(real, context={**real["context"], "extra": "x"}),
              "a context that is a list": variant(real, context=list(real["context"].values())),
              "a non-str key": {**real, 1: 2}, "None": None, "a list": list(real.items()),
              "a NaN where an int belongs": variant(real, index=float("nan")), "bytes where a str belongs": variant(real, entry_hash=b"x")}

    def ask(fn, receipt):
        try:
            return "ok", fn(receipt)
        except (TypeError, ValueError):
            return "refused", None

    out: List[str] = []
    for label, receipt in valid.items():
        mine, theirs = ask(spine_trace.receipt_signing_input, receipt), ask(delta_signing.receipt_signing_input, receipt)
        if mine[0] != "ok" or theirs[0] != "ok" or mine[1] != theirs[1]:
            out.append(f"valid receipt ({label}): CNS {mine[0]}, delta {theirs[0]}, bytes {'equal' if mine[1] == theirs[1] else 'differ'}")
    for label, receipt in broken.items():
        mine, theirs = ask(spine_trace.receipt_signing_input, receipt), ask(delta_signing.receipt_signing_input, receipt)
        if mine[0] != "refused" or theirs[0] != "refused":
            out.append(f"invalid receipt ({label}): CNS {mine[0]}, delta {theirs[0]}")
    if spine_trace.RECEIPT_SIGNATURE_DOMAIN != delta_signing.RECEIPT_SIGNATURE_DOMAIN:
        out.append("the signature domain tags differ")
    return out


def GAP_a_holder_of_a_trusted_key_signs_a_forged_receipt() -> List[str]:
    """KNOWN GAP, stated as a fact and a recorded limit. Signing closes the forged-receipt gap only for a verifier that trusts
    only real keys. Whoever holds a trusted key can sign a hand-built receipt for a ledger that does not exist (index 4 of 9,
    a head that names no ledger), and CNS, which sees a verifying signature and a receipt that fits the contents, names no
    problem and issues a root. The signature says who vouched, not that the ledger is real. Only a held checkpoint taken from
    a real ledger (`held_checkpoint`) or the key holder's honesty tells it from an honest one, and neither is in CNS."""
    p = stages(SICK)
    head = "1" * 64
    receipt = {"schema": "ledger-receipt/1", "entry_digest": subject_digest(p["delta"]), "index": 4,
               "entry_hash": p["delta"]["immutable_hash"], "previous_hash": p["delta"]["previous_hash"], "ledger_length": 9,
               "ledger_head": head, "checkpoint_length": 9, "checkpoint_head": head, "context": dict(CTX)}
    signature = delta_signing.sign_receipt(receipt, receipt_keys.make_signer(DEPLOYER_KEY, "k1"))
    return signed_check(p, receipt, signature, deployer_verifier(), held=False)


# --- the durable store across processes (Step 3) ----------------------------------------------------------------------
#
# Each scenario runs SEPARATE python processes (`store_worker.py`, with this interpreter and this PYTHONPATH). The producer
# records Decisions through FileLedgerStore, writes a signed checkpoint into a directory of its own and hands over the three
# upstream contents and a signature over Delta's receipt. A fresh consumer reconciles the store with the checkpoint, rebuilds
# the receipt itself and asks CNS for the strict root. Every refusal is judged by the consumer's own named reason, and the
# store files must be byte-identical afterwards.

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_worker.py")


def record(ledger, i, vitals=None) -> Dict[str, Any]:
    """The i-th run recorded into `ledger`: alternating readings, a minute later each, its own run and event."""
    return stages((SICK, WELL)[i % 2] if vitals is None else vitals, ctx={**CTX, "run_id": f"run_{i}", "event_id": f"event_{i}"},
                  ledger=ledger, at=T0 + timedelta(minutes=i))


def worker(*args: str, **kw: Any) -> "subprocess.CompletedProcess[str]":
    return subprocess.run([sys.executable, WORKER, *args], capture_output=True, text=True, timeout=180, env=dict(os.environ), **kw)


class World:
    """Three places that do not share a directory: the ledger store, the checkpoint (separate storage) and the hand-off."""

    def __init__(self, root: str) -> None:
        self.root = root
        self.ledger = os.path.join(root, "ledger")
        self.checkpoint = os.path.join(root, "checkpoint-storage", "checkpoint.json")
        self.handoff = os.path.join(root, "handoff")
        self.file = os.path.join(self.ledger, "ledger.jsonl")

    def produce(self, entries: int, *more: str) -> List[str]:
        """Run a producer process to completion; the audit ids it acknowledged."""
        done = worker("producer", "--ledger", self.ledger, "--checkpoint", self.checkpoint, "--handoff", self.handoff,
                      "--entries", str(entries), *more)
        if done.returncode != 0:
            raise RuntimeError(f"the producer exited {done.returncode}: {done.stderr.strip()[-400:]}")
        return [line.split()[1] for line in done.stdout.splitlines() if line.startswith("ACK ")]

    def consume(self, *more: str) -> "subprocess.CompletedProcess[str]":
        return worker("consumer", "--ledger", self.ledger, "--checkpoint", self.checkpoint, "--handoff", self.handoff, *more)

    def state(self) -> Dict[str, str]:
        """Every byte of the ledger store and of the checkpoint storage: a refused load must leave both as they were."""
        found: Dict[str, str] = {}
        for base in (self.ledger, os.path.dirname(self.checkpoint)):
            for folder, _, names in os.walk(base):
                for name in names:
                    path = os.path.join(folder, name)
                    with open(path, "rb") as fh:
                        found[os.path.relpath(path, self.root)] = hashlib.sha256(fh.read()).hexdigest()
        return found

    def lines(self) -> List[bytes]:
        with open(self.file, "rb") as fh:
            return fh.read().splitlines(keepends=True)

    def write_lines(self, lines: List[bytes]) -> None:
        with open(self.file, "wb") as fh:
            fh.write(b"".join(lines))


@contextlib.contextmanager
def world():
    with tempfile.TemporaryDirectory() as root:
        yield World(root)


def consumer_refusal(w: World, *more: str) -> Callable[[], None]:
    """The consumer as a thunk that raises ValueError carrying its own named reason when it exits non-zero."""
    def thunk() -> None:
        done = w.consume(*more)
        if done.returncode != 0:
            raise ValueError(f"the consumer exited {done.returncode}: {done.stderr.strip()}")
    return thunk


def consumer_answer(done: "subprocess.CompletedProcess[str]") -> Dict[str, Any]:
    return json.loads(done.stdout.strip().splitlines()[-1])


def expected_root(w: World, *, signed: bool = True) -> str:
    """The strict root computed IN THIS PROCESS from the same inputs the consumer was given (the store, the signed checkpoint,
    the hand-off and its trust list), by this runner's own code and not by the worker's. `signed=False` leaves the signature
    arguments out, which is the root a consumer that dropped them would print."""
    with open(os.path.join(w.handoff, "trust.json"), encoding="utf-8") as fh:
        trust, revoked = receipt_keys.trust_from_json(fh.read())
    verify = receipt_keys.make_verifier(trust, revoked)
    ledger, _ = delta_pkg.FileLedgerStore(w.ledger).load(require_context=True)
    checkpoint = delta_pkg.CheckpointStore(w.checkpoint).read(verify=verify)
    with open(os.path.join(w.handoff, "contents.json"), encoding="utf-8") as fh:
        contents = json.load(fh)
    with open(os.path.join(w.handoff, "receipt_signature.hex"), encoding="utf-8") as fh:
        signature = bytes.fromhex(fh.read().strip())
    beta = contents["beta"]
    delta = delta_cns.entry_content(ledger.entries[checkpoint.length - 1], context=beta["context"], decision_digest=subject_digest(beta))
    receipt = delta_cns.verification_receipt(ledger, checkpoint, context=beta["context"], decision_digest=subject_digest(beta))
    kw: Dict[str, Any] = dict(receipt_signature=signature, verify_receipt_signature=verify, require_signed_receipt=True) if signed else {}
    return strict_root(contents["alpha"], contents["zeta"], beta, delta, chain=receipt, held_checkpoint=(checkpoint.length, checkpoint.head),
                       keyset_fingerprint_of=zeta_keyset_fingerprint, **kw)


def a_producer_and_a_fresh_consumer_agree() -> List[str]:
    with world() as w:
        acked = w.produce(4)
        before = w.state()
        done = w.consume()
        if done.returncode != 0:
            return [f"the consumer refused an honest store: {done.stderr.strip()}"]
        answer = consumer_answer(done)
        out: List[str] = []
        if len(acked) != 4 or len(w.lines()) != 4:
            out.append(f"the producer acknowledged {len(acked)} entries and the file holds {len(w.lines())}, not 4")
        if os.path.dirname(w.checkpoint) == w.ledger or w.checkpoint.startswith(w.ledger):
            out.append("the checkpoint is in the ledger's directory, which is not independent")
        if answer.get("status") != "OK" or answer.get("entries") != 4 or answer.get("checkpoint_length") != 4:
            out.append(f"the consumer reported {answer}")
        if not (isinstance(answer.get("root"), str) and len(answer["root"]) == 64):
            out.append("the consumer issued no root")
        else:
            want, unsigned = expected_root(w), expected_root(w, signed=False)
            if want == unsigned:
                out.append("the root with a verified signature equals the root without one, so the signature proves nothing here")
            if answer["root"] != want:
                out.append(f"the consumer's root {answer['root']} is not the strict_root {want} computed in-process from the same "
                           f"inputs (the unsigned root would be {unsigned})")
        if w.state() != before:
            out.append("the consumer changed the store or the checkpoint")
        return out


def a_tampered_handoff_is_refused_by_cns(change: Callable[[World], None]) -> List[str]:
    """The store and the checkpoint are honest and the consumer is given a damaged hand-off. Every store check passes, so
    the refusal can only be the consumer's CNS step (`strict check:`), and its named problem must be the one asked for."""
    with world() as w:
        w.produce(4)
        change(w)
        return refused(consumer_refusal(w), state=w.state)


def _edit_handoff(w: World, name: str, change: Callable[[str], str]) -> None:
    path = os.path.join(w.handoff, name)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(change(text))


def _flip_last_hex_digit(text: str) -> str:
    text = text.rstrip("\n")
    return text[:-1] + ("0" if text[-1] != "0" else "1") + "\n"


def _another_decision(text: str) -> str:
    contents = json.loads(text)
    contents["beta"]["instructions"] = "Send home."
    return json.dumps(contents, sort_keys=True)


def _another_keyset(text: str) -> str:
    contents = json.loads(text)
    contents["alpha"]["min_confidence"] = 0.5
    return json.dumps(contents, sort_keys=True)


def a_ledger_file_truncated_below_the_checkpoint() -> List[str]:
    with world() as w:
        w.produce(4)
        w.write_lines(w.lines()[:2])
        return refused(consumer_refusal(w), state=w.state)


def an_entry_rewritten_and_the_file_rechained() -> List[str]:
    """Entry 1 is a different Decision, recorded afresh so that every later hash, sum and the chain are consistent: the file
    verifies on its own. Only the checkpoint held elsewhere says the history was different."""
    with world() as w:
        w.produce(4)
        with tempfile.TemporaryDirectory() as other:
            ledger = DecisionLedger(require_context=True, sink=delta_pkg.FileLedgerStore(other).sink)
            for i in range(4):
                record(ledger, i, SICK_ELSEWHERE if i == 1 else None)
            with open(os.path.join(other, "ledger.jsonl"), "rb") as fh:
                rewritten = fh.read()
        if rewritten == b"".join(w.lines()):
            return ["the rewrite equals the honest file, so nothing was rewritten"]
        with open(w.file, "wb") as fh:
            fh.write(rewritten)
        return refused(consumer_refusal(w), state=w.state)


def a_torn_final_line_is_recovered_and_reported() -> List[str]:
    """A fifth entry past the checkpoint is cut off mid-line, as a crash would. The checkpoint covers four: the load drops the
    torn line, says so, and the strict root is issued for the witnessed entry. Nothing is written by the load."""
    with world() as w:
        acked = w.produce(5, "--checkpoint-at", "4")
        lines = w.lines()
        w.write_lines(lines[:4] + [lines[4][: len(lines[4]) // 2]])
        before = w.state()
        done = w.consume()
        if done.returncode != 0:
            return [f"the consumer refused a torn final line past the checkpoint: {done.stderr.strip()}"]
        answer = consumer_answer(done)
        out: List[str] = []
        if answer["recovered_tail"].get("count") != 1 or answer["status"] != "OK" or answer["entries"] != 4 or not answer.get("root"):
            out.append(f"the torn line was not recovered and reported: {answer} ({len(acked)} acknowledged)")
        if w.state() != before:
            out.append("the load wrote to the store")
        return out


def mid_file_damage_is_refused() -> List[str]:
    with world() as w:
        w.produce(4)
        lines = w.lines()
        if b"patient_1" not in lines[1]:
            return ["the damage could not be made"]
        lines[1] = lines[1].replace(b"patient_1", b"patient_2", 1)
        w.write_lines(lines)
        return refused(consumer_refusal(w), state=w.state)


def _store_verifier(w: World) -> Callable[[bytes, bytes], bool]:
    """The consumer's checkpoint verifier, from the trust list the producer handed over."""
    with open(os.path.join(w.handoff, "trust.json"), encoding="utf-8") as fh:
        trust, revoked = receipt_keys.trust_from_json(fh.read())
    return receipt_keys.make_verifier(trust, revoked)


def _restart(w: World) -> Callable[[], None]:
    """A producer restarting the documented way: rebuild its ledger from the store and attach, against the checkpoint it
    keeps on separate storage."""
    def thunk() -> None:
        delta_pkg.FileLedgerStore(w.ledger).load(True, attach=True, against=delta_pkg.CheckpointStore(w.checkpoint),
                                                 verify=_store_verifier(w))
    return thunk


def a_restart_after_acknowledged_entries_were_deleted_is_refused() -> List[str]:
    """Two acknowledged entries are deleted from the file. A producer that rebuilt its ledger from it and carried on would
    record past the old checkpoint's length, and a checkpoint written then would make the loss look ordinary."""
    with world() as w:
        w.produce(4)
        w.write_lines(w.lines()[:2])
        return refused(_restart(w), catch=(delta_pkg.StoreError,), state=w.state)


def a_restart_after_the_history_was_rewritten_is_refused() -> List[str]:
    """Entry 1 is a different Decision and the file is rechained, so it verifies on its own and is as long as before."""
    with world() as w:
        w.produce(4)
        with tempfile.TemporaryDirectory() as other:
            ledger = DecisionLedger(require_context=True, sink=delta_pkg.FileLedgerStore(other).sink)
            for i in range(4):
                record(ledger, i, SICK_ELSEWHERE if i == 1 else None)
            with open(os.path.join(other, "ledger.jsonl"), "rb") as fh:
                rewritten = fh.read()
        if rewritten == b"".join(w.lines()):
            return ["the rewrite equals the honest file, so nothing was rewritten"]
        with open(w.file, "wb") as fh:
            fh.write(rewritten)
        return refused(_restart(w), catch=(delta_pkg.StoreError,), state=w.state)


def a_checkpoint_that_does_not_extend_the_stored_one_is_refused() -> List[str]:
    """A rewritten history one entry longer than the stored checkpoint, checkpointed on its own: forward by length, but not
    an extension of what the stored checkpoint vouches for."""
    with world() as w:
        w.produce(4)
        ledger = DecisionLedger(require_context=True)
        for i in range(5):
            record(ledger, i, SICK_ELSEWHERE if i == 1 else None)
        store = delta_pkg.CheckpointStore(w.checkpoint)
        return refused(lambda: store.write(ledger.checkpoint(), history=ledger, verify=_store_verifier(w)),
                       catch=(delta_pkg.StoreError,), state=w.state)


def a_restart_by_the_readme_recipe_after_the_file_was_deleted_cannot_launder_the_loss() -> List[str]:
    """The ledger file is deleted. The restarted writer follows the README recipe (a fresh ledger recording to the same
    store, with no load and so no comparison), records past the old length and takes a checkpoint of that ledger. The
    checkpoint remembers the ledger it came from, so the store sees that it does not extend the one it holds."""
    with world() as w:
        w.produce(4)
        os.remove(w.file)
        ledger = DecisionLedger(require_context=True, sink=delta_pkg.FileLedgerStore(w.ledger).sink)
        for i in range(10, 15):
            record(ledger, i)
        store = delta_pkg.CheckpointStore(w.checkpoint)
        return refused(lambda: store.write(ledger.checkpoint(), verify=_store_verifier(w)), catch=(delta_pkg.StoreError,),
                       state=lambda: _tree_digest(os.path.dirname(w.checkpoint)))


def _tree_digest(base: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for folder, _, names in os.walk(base):
        for name in names:
            with open(os.path.join(folder, name), "rb") as fh:
                found[os.path.relpath(os.path.join(folder, name), base)] = hashlib.sha256(fh.read()).hexdigest()
    return found


def an_honest_restart_attaches_and_carries_on() -> List[str]:
    """The same restart over an intact file attaches, records another run, and the store loads back one entry longer."""
    with world() as w:
        w.produce(3)
        ledger, _ = delta_pkg.FileLedgerStore(w.ledger).load(True, attach=True, against=delta_pkg.CheckpointStore(w.checkpoint),
                                                             verify=_store_verifier(w))
        record(ledger, 3)
        again, _ = delta_pkg.FileLedgerStore(w.ledger).load(True)
        if len(again) != 4:
            return [f"the restarted producer recorded one more entry, but the store holds {len(again)}"]
        return []


def a_checkpoint_replaced_by_an_older_signed_one(*more: str, expect_refusal: bool = True) -> List[str]:
    with world() as w:
        with tempfile.TemporaryDirectory() as old:
            snapshot = (os.path.join(old, "checkpoint.json"), os.path.join(old, "handoff"))
            w.produce(4, "--snapshot-at", "2", "--snapshot-checkpoint", snapshot[0], "--snapshot-handoff", snapshot[1])
            os.replace(snapshot[0], w.checkpoint)
        if expect_refusal:
            return refused(consumer_refusal(w, *more), state=w.state)
        before = w.state()
        done = w.consume(*more)
        if done.returncode != 0:
            return [f"the consumer refused: {done.stderr.strip()}"]
        answer = consumer_answer(done)
        out = [] if answer.get("status") == "UNWITNESSED_TAIL" and answer.get("unwitnessed") == 2 else [f"the consumer reported {answer}"]
        return out + ([] if w.state() == before else ["the consumer changed the store or the checkpoint"])


def GAP_an_older_signed_checkpoint_is_accepted_as_an_unwitnessed_tail() -> List[str]:
    """KNOWN GAP, a recorded limit. A signature carries no freshness: the checkpoint at two entries, validly signed by the
    deployer's key and put back over the one at four, verifies. `reconcile` reports UNWITNESSED_TAIL (two entries nothing
    independent vouches for) and does not refuse. A consumer that insists on OK refuses it (the scenario above); one that
    accepts a tail is told, and gets no root, but nothing in the store or the signature says the checkpoint is old."""
    return a_checkpoint_replaced_by_an_older_signed_one("--accept-unwitnessed", expect_refusal=False)


def GAP_a_ledger_rolled_back_to_an_older_signed_package_is_accepted() -> List[str]:
    """KNOWN GAP, a recorded limit and the sharp end of the one above. The attacker has an older, complete, validly signed
    package (checkpoint at two entries, the hand-off for entry two) and cuts the ledger file back to two lines. Every check
    passes and a root is issued for the older state; the two later, acknowledged entries are gone and nothing here says so.
    Freshness (a counter, a clock or a monitor that remembers the newest checkpoint) is the deployer's, outside CNS."""
    with world() as w:
        with tempfile.TemporaryDirectory() as old:
            snapshot = (os.path.join(old, "checkpoint.json"), os.path.join(old, "handoff"))
            w.produce(4, "--snapshot-at", "2", "--snapshot-checkpoint", snapshot[0], "--snapshot-handoff", snapshot[1])
            os.replace(snapshot[0], w.checkpoint)
            for name in ("contents.json", "receipt_signature.hex"):
                shutil.copy(os.path.join(snapshot[1], name), os.path.join(w.handoff, name))
        w.write_lines(w.lines()[:2])
        done = w.consume()
        if done.returncode != 0:
            return [f"the rollback was refused, so the gap has closed: {done.stderr.strip()}"]
        answer = consumer_answer(done)
        return [] if answer.get("entries") == 2 and answer.get("root") else [f"the consumer reported {answer}"]


def a_checkpoint_with_no_signature_when_one_is_required() -> List[str]:
    with world() as w:
        w.produce(4)
        store = delta_pkg.CheckpointStore(w.checkpoint)
        history, _ = delta_pkg.FileLedgerStore(w.ledger).load(True)
        store.write(store.read(), history=history)  # the same value, written without a signature
        return refused(consumer_refusal(w), state=w.state)


def a_producer_killed_mid_run_loses_no_acknowledged_entry() -> List[str]:
    """SIGKILL of a producer that is recording as fast as it can. A fresh process loads the store: every entry the producer had
    acknowledged is there, in order, with at most one more (appended, not yet reported), and the chain verifies on load."""
    with world() as w:
        proc = subprocess.Popen([sys.executable, WORKER, "producer", "--ledger", w.ledger, "--checkpoint", w.checkpoint,
                                 "--handoff", w.handoff, "--forever"], stdout=subprocess.PIPE, text=True, env=dict(os.environ))
        timer = threading.Timer(120, proc.kill)
        timer.start()
        acked: List[str] = []
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if line.startswith("ACK ") and line.endswith("\n"):
                    acked.append(line.split()[1])
                if len(acked) >= 15:
                    break
            proc.kill()  # SIGKILL: no handler runs, nothing is flushed that was not already
            proc.wait()
            for line in proc.stdout:  # what was written before the kill and not yet read
                if line.startswith("ACK ") and line.endswith("\n"):
                    acked.append(line.split()[1])
        finally:
            timer.cancel()
            if proc.stdout is not None:
                proc.stdout.close()
        out: List[str] = []
        if proc.returncode != -9:
            out.append(f"the producer was not killed by SIGKILL (exit {proc.returncode})")
        done = worker("load", "--ledger", w.ledger)
        if done.returncode != 0:
            return out + [f"the consumer could not load the killed store: {done.stderr.strip()[-300:]}"]
        loaded = consumer_answer(done)["ids"]
        if loaded[: len(acked)] != acked:
            out.append(f"{len(acked)} entries were acknowledged and the store does not begin with them ({len(loaded)} loaded)")
        if len(loaded) - len(acked) not in (0, 1):
            out.append(f"{len(loaded)} entries loaded for {len(acked)} acknowledged")
        return out


# --- the verify command, end to end as two commands in two processes (Step 4) ----------------------------------------------

CHAINS = os.path.dirname(os.path.abspath(__file__))
MAKE_PACKAGE, VERIFY_PACKAGE = os.path.join(CHAINS, "make_package.py"), os.path.join(CHAINS, "verify_package.py")


def run_script(path: str, *args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run([sys.executable, path, *args], capture_output=True, text=True, timeout=180, env=dict(os.environ))


class Package:
    """A package made by `make_package.py` in a temporary place: the package directory, the checkpoint directory (a different
    one) and the trust list, and the commands to verify it."""

    def __init__(self, root: str, name: str = "a", *make_args: str) -> None:
        self.root = root
        self.dir = os.path.join(root, name, "package")
        self.checkpoint_dir = os.path.join(root, name, "checkpoint-storage")
        self.checkpoint = os.path.join(self.checkpoint_dir, "checkpoint.json")
        self.trust = os.path.join(root, name, "trust.json")
        made = run_script(MAKE_PACKAGE, self.dir, "--checkpoint-dir", self.checkpoint_dir, "--trust-out", self.trust, *make_args)
        if made.returncode != 0:
            raise RuntimeError(f"make_package exited {made.returncode}: {made.stderr.strip()[-400:]}")

    def verify(self, *more: str, package: Optional[str] = None, checkpoint: Optional[str] = None,
               trust: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        return run_script(VERIFY_PACKAGE, package or self.dir, "--checkpoint", checkpoint or self.checkpoint,
                          "--public-keys", trust or self.trust, *more)

    def state(self) -> Dict[str, str]:
        """Every byte of the package, the checkpoint storage and the trust list: a refusal must change none of them."""
        found: Dict[str, str] = {}
        for base in (self.dir, self.checkpoint_dir, os.path.dirname(self.trust)):
            for folder, _, names in os.walk(base):
                for name in names:
                    with open(os.path.join(folder, name), "rb") as fh:
                        found[os.path.relpath(os.path.join(folder, name), self.root)] = hashlib.sha256(fh.read()).hexdigest()
        return found

    def edit(self, name: str, change: Callable[[Any], Any]) -> None:
        path = os.path.join(self.dir, name)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        change(data)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True)

    def edit_trust(self, change: Callable[[Dict[str, Any], set], Any]) -> None:
        with open(self.trust, encoding="utf-8") as fh:
            trust, revoked = receipt_keys.trust_from_json(fh.read())
        revoked = set(revoked)
        change(trust, revoked)
        with open(self.trust, "w", encoding="utf-8") as fh:
            fh.write(receipt_keys.trust_to_json(trust, revoked))


@contextlib.contextmanager
def packages(*makes: Tuple[str, ...]):
    """One or more packages in one temporary place; each `makes` entry is the extra arguments for one `make_package.py`."""
    with tempfile.TemporaryDirectory() as root:
        yield [Package(root, "abcdefgh"[i], *args) for i, args in enumerate(makes)]


def verify_refusal(pkg: Package, *more: str, **where: str) -> Callable[[], None]:
    """The verify command as a thunk: ValueError carrying everything it printed to stderr when it refuses (exit 1); anything
    else that is not a pass (a usage error, an unreadable input) is a RuntimeError, which no scenario here declares."""
    def thunk() -> None:
        done = pkg.verify(*more, **where)
        if done.returncode == 1:
            raise ValueError(f"verify_package refused (exit 1): {done.stderr.strip()}")
        if done.returncode != 0:
            raise RuntimeError(f"verify_package exited {done.returncode}, not 1: {done.stderr.strip()[-300:]}")
    return thunk


def refused_package(*makes: Tuple[str, ...], attack: Callable[..., Tuple[Tuple[str, ...], Dict[str, str]]]) -> List[str]:
    """Make the packages, let `attack(*packages)` damage them and say how to verify (extra arguments, replacement paths), and
    return what the verify command refused, with the state of every file checked before and after."""
    with packages(*makes) as made:
        more, where = attack(*made)
        return refused(verify_refusal(made[0], *more, **where), state=made[0].state)


SIGNED = ("--require-signed",)
SUMMARY = re.compile(r"verified: root=[0-9a-f]{64} entries=3 checkpoint=3 entry=2 run_id=run_2 event_id=event_2 receipt_signature=(verified|absent \(allowed\))")


def an_honest_package_verifies_in_another_process() -> List[str]:
    out: List[str] = []
    with packages((), ("--no-receipt-signature", "--no-checkpoint-signature")) as (signed, unsigned):
        before = signed.state()
        done = signed.verify(*SIGNED)
        line = done.stdout.strip()
        if done.returncode != 0 or not SUMMARY.fullmatch(line) or not line.endswith("receipt_signature=verified"):
            out.append(f"an honest signed package did not verify with --require-signed: exit {done.returncode} {line!r} {done.stderr.strip()}")
        if signed.verify().stdout.strip() != line:
            out.append("the same package verified without --require-signed gives a different root or summary")
        if signed.verify("--allow-unsigned").stdout.strip() != line:
            out.append("--allow-unsigned changed the verdict on a package whose receipt IS signed")
        if signed.verify("--allow-unsigned", "--require-signed").returncode != 2:
            out.append("--allow-unsigned together with --require-signed was not a usage error (exit 2)")
        if signed.state() != before:
            out.append("verifying changed a file")
        default = unsigned.verify()
        if default.returncode != 1 or "no signature.json" not in default.stderr or default.stdout.strip():
            out.append(f"an unsigned package was not refused by default, naming why: exit {default.returncode} {default.stderr.strip()!r}")
        weaker = unsigned.verify("--allow-unsigned")
        if weaker.returncode != 0 or not SUMMARY.fullmatch(weaker.stdout.strip()) \
                or not weaker.stdout.strip().endswith("receipt_signature=absent (allowed)"):
            out.append(f"an unsigned package did not verify with --allow-unsigned, saying so: exit {weaker.returncode} {weaker.stdout!r}")
        if unsigned.verify(*SIGNED).returncode != 1:
            out.append("an unsigned package was accepted under --require-signed")
    return out


def altered_contents(pkg: Package):
    pkg.edit("contents.json", lambda d: d["beta"].update(instructions="Send home."))
    return SIGNED, {}


def an_altered_export(pkg: Package):
    pkg.edit("export.json", lambda d: d["entries"][1]["decision"].update(instructions="Send home."))
    return SIGNED, {}


def a_substituted_receipt(a: Package, b: Package):
    with open(os.path.join(b.dir, "receipt.json"), encoding="utf-8") as fh:
        other = json.load(fh)
    a.edit("receipt.json", lambda d: (d.clear(), d.update(other)))
    return SIGNED, {}


def a_substituted_receipt_with_its_own_signature(a: Package, b: Package):
    for name in ("receipt.json", "signature.json"):
        shutil.copy(os.path.join(b.dir, name), os.path.join(a.dir, name))
    return SIGNED, {}


def a_substituted_older_checkpoint(a: Package):
    return SIGNED, {"checkpoint": os.path.join(a.checkpoint_dir, "older.json")}


def a_substituted_empty_checkpoint(a: Package):
    path = os.path.join(a.root, "empty.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "length": 0, "head": "0" * 64}, fh)
    return SIGNED, {"checkpoint": path}


def a_substituted_checkpoint_of_another_ledger(a: Package, b: Package):
    """The checkpoint is genuinely signed, by a key the trust list holds (both keys are trusted here), and is for another
    ledger of the same length: only the history it names tells."""
    def both(trust: Dict[str, Any], revoked: set) -> None:
        with open(b.trust, encoding="utf-8") as fh:
            trust.update(receipt_keys.trust_from_json(fh.read())[0])
    a.edit_trust(both)
    return SIGNED, {"checkpoint": b.checkpoint}


def a_receipt_signature_that_is_missing(a: Package):
    return SIGNED, {}


def a_receipt_signature_that_is_missing_with_no_flag(a: Package):
    return (), {}


def a_dangling_link_named_signature_json_is_not_a_missing_file() -> List[str]:
    """A link to nowhere named signature.json is a signature file that cannot be read, not a missing one: exit 2 with and
    without --allow-unsigned, never exit 0."""
    out: List[str] = []
    with packages(()) as (pkg,):
        path = os.path.join(pkg.dir, "signature.json")
        os.remove(path)
        os.symlink(os.path.join(pkg.root, "nowhere"), path)
        for more in ((), ("--allow-unsigned",)):
            done = pkg.verify(*more)
            if done.returncode != 2:
                out.append(f"a dangling signature.json with {more or 'no flag'}: exit {done.returncode}, not 2")
    return out


def a_signature_file_that_holds_null(a: Package):
    """`null` parses, and an earlier verify_package took it for a missing file: the message said so, and --allow-unsigned accepted it."""
    with open(os.path.join(a.dir, "signature.json"), "w", encoding="utf-8") as fh:
        fh.write("null")
    return (), {}


def a_signature_file_that_holds_null_under_allow_unsigned(a: Package):
    a_signature_file_that_holds_null(a)
    return ("--allow-unsigned",), {}


def a_signature_file_with_an_extra_key(a: Package):
    a.edit("signature.json", lambda d: d.update(note="ignored before"))
    return SIGNED, {}


def a_verifier_that_answers_differently_the_second_time() -> List[str]:
    """A verifier that accepts the receipt signature once and then refuses it. strict_problems finds nothing, strict_root
    then raises; the command must turn that into a named refusal, not a traceback."""
    import io
    from unittest import mock
    import verify_package as command
    with packages(()) as (a,):
        real = receipt_keys.make_verifier

        def flipping(trust, revoked):
            inner = real(trust, revoked)
            seen = [0]

            def verify(data, signature):
                ok = inner(data, signature)
                if data.startswith(delta_signing.RECEIPT_SIGNATURE_DOMAIN):
                    seen[0] += 1
                    return ok and seen[0] == 1
                return ok
            return verify

        def run() -> None:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), mock.patch.object(receipt_keys, "make_verifier", flipping):
                try:
                    command.main([a.dir, "--checkpoint", a.checkpoint, "--public-keys", a.trust, "--require-signed"])
                except SystemExit as exc:
                    if exc.code == 0:
                        return
                    raise ValueError(f"verify_package refused (exit {exc.code}): {err.getvalue().strip()}") from None

        return refused(run, state=a.state)


def a_bad_receipt_signature_under_allow_unsigned(a: Package):
    a.edit_trust(lambda trust, revoked: trust.update(k2=Ed25519PrivateKey.generate().public_key()))
    return ("--allow-unsigned",), {}


def a_checkpoint_signature_that_is_missing(a: Package):
    return SIGNED, {}


def a_receipt_key_that_is_the_wrong_key(a: Package):
    a.edit_trust(lambda trust, revoked: trust.update(k2=Ed25519PrivateKey.generate().public_key()))
    return SIGNED, {}


def a_receipt_key_that_is_untrusted(a: Package):
    a.edit_trust(lambda trust, revoked: trust.pop("k2"))
    return SIGNED, {}


def a_receipt_key_that_is_revoked(a: Package):
    a.edit_trust(lambda trust, revoked: revoked.add("k2"))
    return SIGNED, {}


def a_checkpoint_key_that_is_untrusted(a: Package):
    a.edit_trust(lambda trust, revoked: trust.pop("k1"))
    return SIGNED, {}


def inputs_that_cannot_be_read_exit_two_not_one() -> List[str]:
    out: List[str] = []
    with packages(()) as (pkg,):
        def expect2(label: str, done: "subprocess.CompletedProcess[str]") -> None:
            if done.returncode != 2:
                out.append(f"{label}: exit {done.returncode}, not 2")

        expect2("a missing checkpoint file", pkg.verify(checkpoint=os.path.join(pkg.root, "nowhere.json")))
        expect2("a missing package directory", pkg.verify(package=os.path.join(pkg.root, "nowhere")))
        expect2("a missing trust file", pkg.verify(trust=os.path.join(pkg.root, "nowhere.json")))
        with open(os.path.join(pkg.root, "bad.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        expect2("a trust file that is not JSON", pkg.verify(trust=os.path.join(pkg.root, "bad.json")))
        with open(os.path.join(pkg.root, "shape.json"), "w", encoding="utf-8") as fh:
            fh.write('{"keys": []}')
        expect2("a trust file of the wrong shape", pkg.verify(trust=os.path.join(pkg.root, "shape.json")))
        with open(os.path.join(pkg.dir, "export.json"), "w", encoding="utf-8") as fh:
            fh.write("[1, 2")
        expect2("an export that is not JSON", pkg.verify())
        expect2("no arguments at all", run_script(VERIFY_PACKAGE))
        expect2("no checkpoint given", run_script(VERIFY_PACKAGE, pkg.dir, "--public-keys", pkg.trust))
        inside = run_script(MAKE_PACKAGE, os.path.join(pkg.root, "q"), "--checkpoint-dir", os.path.join(pkg.root, "q"),
                            "--trust-out", os.path.join(pkg.root, "q.json"))
        expect2("a producer told to put the checkpoint in the package", inside)
    return out


def a_duplicate_key_in_any_package_file_is_refused_naming_the_file_and_key() -> List[str]:
    """A JSON object with a key twice is read by Python as its last value; a reader that takes the first sees another file.
    The command refuses it: exit 1, the file and the key named, nothing else said."""
    out: List[str] = []
    with packages(()) as (pkg,):
        for name, key in (("export.json", "entries"), ("receipt.json", "index"), ("contents.json", "alpha"),
                          ("signature.json", "receipt_signature")):
            path = os.path.join(pkg.dir, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            first = text.index("{") + 1
            with open(path, "w", encoding="utf-8") as fh:  # the real object, with a decoy first value for the same key
                fh.write("{" + json.dumps(key) + ": null, " + text[first:].lstrip())
            done = pkg.verify()
            if done.returncode != 1 or name not in done.stderr or f"'{key}'" not in done.stderr or "duplicate" not in done.stderr:
                out.append(f"{name} with {key} twice: exit {done.returncode}, stderr {done.stderr.strip()[-200:]!r}")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        with open(pkg.checkpoint, encoding="utf-8") as fh:
            cp_text = fh.read()
        with open(pkg.checkpoint, "w", encoding="utf-8") as fh:
            fh.write('{"length": 0, ' + cp_text.lstrip()[1:])
        done = pkg.verify()
        if done.returncode != 1 or "checkpoint.json" not in done.stderr or "'length'" not in done.stderr or "duplicate" not in done.stderr:
            out.append(f"checkpoint.json with length twice: exit {done.returncode}, stderr {done.stderr.strip()[-200:]!r}")
        with open(pkg.checkpoint, "w", encoding="utf-8") as fh:
            fh.write(cp_text)
        if pkg.verify().returncode != 0:
            out.append("the package no longer verifies once the files are put back")
    return out


def a_validly_signed_receipt_for_an_older_entry_is_refused_unless_entry_names_it() -> List[str]:
    out: List[str] = []
    with packages(("--package-entry", "0")) as (pkg,):
        done = pkg.verify()
        if done.returncode != 1 or "receipt is for entry 0" not in done.stderr or "entry 2" not in done.stderr:
            out.append(f"an older entry's receipt, no --entry: exit {done.returncode}, stderr {done.stderr.strip()[-250:]!r}")
        done = pkg.verify("--entry", "0")
        if done.returncode != 0 or not done.stdout.startswith("verified:") or " entry=0 run_id=run_0 event_id=event_0 " not in done.stdout:
            out.append(f"the same package with --entry 0: exit {done.returncode}, {done.stdout.strip()!r} {done.stderr.strip()[-200:]!r}")
        for wrong in ("1", "2"):
            done = pkg.verify("--entry", wrong)
            if done.returncode != 1 or "receipt is for entry 0" not in done.stderr or f"entry {wrong}" not in done.stderr:
                out.append(f"--entry {wrong} on an entry 0 package: exit {done.returncode}, stderr {done.stderr.strip()[-250:]!r}")
        for outside in ("3", "-1"):
            done = pkg.verify("--entry", outside)
            if done.returncode != 1 or "no entry" not in done.stderr:
                out.append(f"--entry {outside} is outside the ledger: exit {done.returncode}, stderr {done.stderr.strip()[-250:]!r}")
    with packages(()) as (last,):
        done = last.verify("--entry", "2")
        if done.returncode != 0 or " entry=2 " not in done.stdout:
            out.append(f"--entry 2 on the last entry's package: exit {done.returncode}, {done.stdout.strip()!r}")
        done = last.verify("--entry", "0")
        if done.returncode != 1:
            out.append(f"--entry 0 on the last entry's package: exit {done.returncode}, not 1")
    return out


def a_deeply_nested_input_is_exit_two_or_a_named_refusal_never_a_traceback() -> List[str]:
    """Nesting past the interpreter's recursion limit, in the file being parsed (cannot be read: exit 2) and, at a depth the
    parser takes, in what the digest steps then walk (a named refusal: exit 1). No traceback either way."""
    out: List[str] = []
    deep = "[" * 100000 + "]" * 100000
    nested = "[" * 600 + "]" * 600

    def judge(label: str, done: "subprocess.CompletedProcess[str]", code: int) -> None:
        if done.returncode != code or "Traceback" in done.stderr or not done.stderr.strip() or done.stdout.strip():
            out.append(f"{label}: exit {done.returncode} (wanted {code}), stderr {done.stderr.strip()[-200:]!r}")

    def put(pkg: Package, name: str, change: Callable[[str], str]) -> None:
        path = os.path.join(pkg.dir, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(change(text))

    for name, key in (("contents.json", "x"), ("export.json", "x"), ("receipt.json", "x"), ("signature.json", "x")):
        with packages(()) as (pkg,):
            put(pkg, name, lambda t: t.rstrip()[:-1] + ', "' + key + '": ' + deep + "}")
            judge(f"{name} nested 100000 deep", pkg.verify(), 2)
    with packages(()) as (pkg,):
        with open(pkg.trust, "w", encoding="utf-8") as fh:
            fh.write(deep)
        judge("a trust list nested 100000 deep", pkg.verify(), 2)
    with packages(()) as (pkg,):
        with open(pkg.checkpoint, "w", encoding="utf-8") as fh:
            fh.write(deep)
        judge("a checkpoint nested 100000 deep", pkg.verify(), 1)
    for where in ("beta", "alpha", "delta"):
        with packages(()) as (pkg,):
            def plant(d: Dict[str, Any], where: str = where) -> None:
                d[where]["deep"] = json.loads(nested)
            pkg.edit("contents.json", plant)
            judge(f"contents.json with {where} holding a list nested 600 deep", pkg.verify(), 1)
    with packages(()) as (pkg,):
        pkg.edit("export.json", lambda d: d.update(deep=json.loads(nested)))
        judge("export.json with a list nested 600 deep", pkg.verify(), 1)
    return out


def the_checkpoint_and_the_trust_list_must_live_outside_the_package() -> List[str]:
    """The checkpoint is independent only if the package's author cannot write it. Given a path whose REAL location is inside
    the package directory (a copy, a symlink in the package to a file outside, a symlink outside to a file inside, a hard
    link), the command exits 2 and says so; the same files from outside the package still verify."""
    out: List[str] = []
    with packages((), ()) as (pkg, clean):
        def expect2(label: str, done: "subprocess.CompletedProcess[str]") -> None:
            if done.returncode != 2 or "inside the package" not in done.stderr or done.stdout.strip():
                out.append(f"{label}: exit {done.returncode}, stderr {done.stderr.strip()[-200:]!r}, stdout {done.stdout.strip()!r}")

        for flag, source, name in (("checkpoint", pkg.checkpoint, "cp.json"), ("trust", pkg.trust, "trust.json")):
            def use(path: str) -> "subprocess.CompletedProcess[str]":
                return pkg.verify("--require-signed", **{flag: path})  # type: ignore[arg-type]
            label = "the checkpoint" if flag == "checkpoint" else "the trust list"
            inside = os.path.join(pkg.dir, name)
            shutil.copy(source, inside)
            expect2(f"{label} copied into the package", use(inside))
            via_link = os.path.join(pkg.dir, "link-" + name)
            os.symlink(source, via_link)  # a name in the package, the file outside
            expect2(f"{label} reached through a symlink inside the package", use(via_link))
            outside_link = os.path.join(pkg.root, "outside-link-" + name)
            os.symlink(inside, outside_link)  # a name outside, the file inside
            expect2(f"{label} reached through a symlink outside that points into the package", use(outside_link))
            hard = os.path.join(pkg.dir, "hard-" + name)
            os.link(source, hard)
            expect2(f"{label} hard-linked into the package", use(hard))
            expect2(f"{label} reached by a path through ..", use(os.path.join(pkg.dir, "..", "package", name)))
        os.symlink(pkg.dir, os.path.join(pkg.root, "pkg-link"))  # the package itself named through a link
        expect2("the package given through a symlink and the checkpoint inside it",
                run_script(VERIFY_PACKAGE, os.path.join(pkg.root, "pkg-link"), "--checkpoint", os.path.join(pkg.dir, "cp.json"),
                           "--public-keys", pkg.trust))
        if clean.verify("--require-signed").returncode != 0:
            out.append("an untouched package no longer verifies with the checkpoint and trust list from outside")
    return out


# --- domain packs: a second, unrelated domain runs through the same four stages (alpha.packs, alpha.core) ----------------

DOMAIN_CTX = {"schema": CONTEXT_SCHEMA, "entity_id": "checkout_service", "event_id": "event_d1", "run_id": "run_d1"}
SERVICE_BAD = ServiceObservation(latency_p95_ms=1500.0, error_rate=0.10, queue_depth=500, tier="interactive")
SERVICE_OK = ServiceObservation(latency_p95_ms=120.0, error_rate=0.001, queue_depth=5, tier="interactive")


def domain_registry() -> PackRegistry:
    registry = PackRegistry()
    registry.register(PediatricVitalsPack())
    registry.register(ServiceHealthPack())
    return registry


def domain_build():
    """Locks and rules for the service pack. Beta's decisions are free-form text: nothing here is clinical."""
    locks = LockRegistry([
        LockSpec(lock_id="outage_lock", required_keys=("latency_critical", "error_burst", "degraded_service"),
                 combination=Combination.OR, dwell_threshold=1, force=True, lock_seconds=3600),
        LockSpec(lock_id="slow_lock", required_keys=("latency_high", "queue_backlog"), combination=Combination.OR, dwell_threshold=1),
    ])
    rules = DecisionRuleRegistry([
        DecisionRule(decision_id="page_oncall", decision="PAGE_ONCALL", open_locks=("outage_lock",), priority=10,
                     reasoning_template="{decision}: outage", instructions="Page the on-call engineer."),
        DecisionRule(decision_id="watch", decision="WATCH", open_locks=("slow_lock",), closed_locks=("outage_lock",), priority=5,
                     reasoning_template="{decision}: slow", instructions="Watch the dashboards."),
        DecisionRule(decision_id="normal", decision="NORMAL", closed_locks=("outage_lock", "slow_lock"), priority=0,
                     reasoning_template="{decision}: healthy", instructions="No action."),
    ])
    return locks, DecisionEngine(rules, locks)


def domain_origin(identity: str, at: datetime = T0 - timedelta(seconds=30)) -> Dict[str, str]:
    """An origin as a service-health producer states it. `transformation` carries the pack's identity, the producer's own claim."""
    return {"source": "metrics gateway 2", "producer": "service-ingest 1.0", "observed_at": at.isoformat(),
            "collection_context": "production, 1 minute window", "transformation": identity}


def domain_stages(raw=SERVICE_BAD, pack: str = "service_health", registry: Optional[PackRegistry] = None,
                  identity: Optional[str] = None, ctx=DOMAIN_CTX) -> Dict[str, Any]:
    """The four stages run for real on a pack's output, bound as `stages` binds them, with the pack's identity in origin."""
    registry = registry or domain_registry()
    locks, engine = domain_build()
    ledger = DecisionLedger(require_context=True)
    entity = ctx["entity_id"]
    keys = registry.observe(pack, raw)
    claimed = pack_identity(registry.get(pack)) if identity is None else identity
    alpha = alpha_cns.keyset_content(keys, context=ctx, origin=domain_origin(claimed))
    da = subject_digest(alpha)
    results = LockEvaluator(locks).evaluate_all(entity, keys, T0)
    zeta = {lid: zeta_cns.lock_result_content(r, context=ctx, keyset_digest=da) for lid, r in results.items()}
    decision = engine.decide(entity, keys, results, T0)
    beta = beta_cns.decision_content(
        decision, context=ctx, keyset_digest=da,
        lock_result_digests={lid: zeta_cns.lock_result_digest(r, context=ctx, keyset_digest=da) for lid, r in results.items()})
    entry = ledger.append(decision, context=ctx)
    delta = delta_cns.entry_content(entry, context=ctx, decision_digest=subject_digest(beta))
    return {"alpha": alpha, "zeta": zeta, "beta": beta, "delta": delta, "ledger": ledger, "decision": decision, "keys": keys,
            "checkpoint": ledger.checkpoint()}


def a_service_health_run_is_accepted_by_the_strict_check() -> List[str]:
    """A domain with no clinical word in it, through alpha's pack, zeta's locks, beta's decision and delta's ledger, and the same
    strict check that accepts the pediatric run. The decision is the free-form text the rules gave it."""
    p = domain_stages(SERVICE_BAD)
    out = check(p)
    if p["decision"].decision != "PAGE_ONCALL":
        out.append(f"the bad service reading did not page: {p['decision'].decision}")
    if domain_stages(SERVICE_OK)["decision"].decision != "NORMAL":
        out.append("the healthy service reading was not NORMAL")
    return out


def the_pack_identity_is_recorded_in_origin_and_bound_by_the_digest() -> List[str]:
    out: List[str] = []
    p = domain_stages(SERVICE_BAD)
    want = "pack:service_health/0.1.0"
    if p["alpha"].get("origin", {}).get("transformation") != want:
        out.append(f"origin.transformation is {p['alpha'].get('origin', {}).get('transformation')!r}, not {want!r}")
    other = domain_stages(SERVICE_BAD, identity="pack:service_health/0.2.0")
    if subject_digest(other["alpha"]) == subject_digest(p["alpha"]):
        out.append("a different pack identity did not change alpha's content digest, so a decision would not state which pack ran")
    return out


def the_pediatric_pack_runs_through_the_registry_with_its_identity() -> List[str]:
    """The reference pack, reached through the registry and recorded the same way: the second pack changed nothing for the first."""
    registry = domain_registry()
    keys = registry.observe("pediatric_vitals", SICK)
    identity = pack_identity(registry.get("pediatric_vitals"))
    alpha = alpha_cns.keyset_content(keys, context=CTX, origin={**origin_observed(T0 - timedelta(seconds=30)), "transformation": identity})
    direct = alpha_cns.keyset_content(observe(SICK), context=CTX)
    out = []
    if alpha["keys"] != direct["keys"]:
        out.append("the registry gave the pediatric pack's keys different from calling it directly")
    if alpha["origin"]["transformation"] != "pack:pediatric_vitals/0.2.0":
        out.append(f"unexpected pack identity {alpha['origin']['transformation']!r}")
    return out


def a_pack_with_an_out_of_bounds_threshold_is_refused() -> List[str]:
    class Loose(ServiceHealthPack):
        NAME = "loose_service"

        def parameters(self):
            first, *rest = super().parameters()
            return (dataclasses.replace(first, value=first.maximum * 10.0), *rest)

    return refused(lambda: PackRegistry().register(Loose()), catch=(PackValidationError,))


def a_pack_with_no_approval_is_refused() -> List[str]:
    class Unapproved(ServiceHealthPack):
        NAME = "unapproved_service"

        def parameters(self):
            first, *rest = super().parameters()
            return (dataclasses.replace(first, approved_by="", approval_date=""), *rest)

    return refused(lambda: PackRegistry().register(Unapproved()), catch=(PackValidationError,))


def a_pack_that_emits_an_undeclared_key_is_refused() -> List[str]:
    class Rogue(ServiceHealthPack):
        NAME = "rogue_service"

        def observe(self, raw):
            return KeySet([Key("surprise", present=True, confidence=1.0, reason="not declared")])

    registry = PackRegistry()
    registry.register(Rogue())
    return refused(lambda: registry.observe("rogue_service", SERVICE_BAD), catch=(PackError,))


def a_pack_name_cannot_be_registered_twice() -> List[str]:
    registry = domain_registry()
    return refused(lambda: registry.register(ServiceHealthPack()), catch=(PackError,))


def keys_of_one_pack_under_the_digest_of_another_are_refused() -> List[str]:
    """The pediatric run's alpha content presented with the service run's zeta, beta and delta: the stages do not describe one run."""
    service = domain_stages(SERVICE_BAD)
    pediatric_keys = domain_registry().observe("pediatric_vitals", SICK)
    swapped = {**service, "alpha": alpha_cns.keyset_content(pediatric_keys, context=DOMAIN_CTX,
                                                           origin=domain_origin("pack:pediatric_vitals/0.2.0"))}
    return check(swapped)


def GAP_a_pack_identity_is_the_producers_claim() -> List[str]:
    """KNOWN GAP, stated as a fact. origin.transformation names the pack, and the digest binds that text, but nothing authenticates
    it: keys the service pack produced under a run whose origin claims the pediatric pack are accepted. No problem is found when
    the fact holds; one is reported if CNS ever starts checking the claim."""
    p = domain_stages(SERVICE_BAD, identity="pack:pediatric_vitals/0.2.0")
    return check(p)


CLEAN = Expect("clean")
GAP = Expect("gap")
CHAIN_NOT_SHOWN = "the ledger chain was not shown to verify"
#: Per scenario: (name, how to run it, what it must produce: an Expect). Anything else fails when the table loads.
SCENARIOS: List[Tuple[str, Callable[[], List[str]], Expect]] = [
    ("a sick patient, end to end", lambda: clean(SICK), CLEAN),
    ("a well patient, end to end", lambda: clean(WELL), CLEAN),
    ("different runs have different roots", two_runs_have_different_roots, CLEAN),
    # lenient extras: the Decision was swapped after delta recorded the original, so the two digests also diverge
    ("the Decision cites a Key alpha never detected", cites_a_key_alpha_never_saw,
     Expect("problems", required=("did not detect as present: ghost_key",),
            allowed_extra=("beta's digest of the Decision differs from delta's digest",))),
    ("the Decision cites a Lock zeta never evaluated", cites_a_lock_zeta_never_evaluated,
     Expect("problems", required=("never evaluated: invented_lock",),
            allowed_extra=("beta's digest of the Decision differs from delta's digest",))),
    ("the ledger recorded a different Decision", ledger_recorded_another_decision,
     Expect("problems", required=("beta's digest of the Decision differs from delta's digest", "drifted apart"))),
    ("the entity differs between the run and the Decision", wrong_entity,
     Expect("problems", required=("the run is about 'patient_2' but the Decision is about 'patient_1'",))),
    # --- strict ---
    ("strict: a sick patient, end to end", lambda: strict_clean(SICK), CLEAN),
    ("strict: a well patient, end to end", lambda: strict_clean(WELL), CLEAN),
    ("strict: a sick patient with an origin record, end to end", an_origin_observed_before_the_decision, CLEAN),
    ("strict: the same readings in two runs have different roots", strict_roots_differ_by_run, CLEAN),
    ("strict: a strict root is never a lenient root", strict_root_is_not_a_lenient_root, CLEAN),
    ("strict: the four connectors agree with CNS on the context", connectors_agree_with_cns_on_what_a_context_is, CLEAN),
    # extras: beta's digests were taken over the original results, and each lock result also names the wrong entity itself
    ("strict: zeta's results are bound to another subject", subject_substituted_between_alpha_and_zeta,
     Expect("problems",
            required=("zeta lock sepsis_lock is bound to a different run than alpha's: entity_id 'patient_2' vs 'patient_1'",
                      "zeta lock abnormal_vitals_lock is bound to a different run than alpha's: entity_id 'patient_2' vs 'patient_1'"),
            allowed_extra=("beta's Decision rests on a different lock result than zeta produced for",
                           "records entity 'patient_2' but the run is about 'patient_1'"))),
    # extra: delta's decision_digest named beta's original content, which the substituted beta no longer matches
    ("strict: beta's Decision is bound to another event", event_substituted_between_zeta_and_beta,
     Expect("problems", required=("beta is bound to a different run than alpha's: event_id 'event_2' vs 'event_1'",),
            allowed_extra=("delta recorded a Decision other than the one beta produced",))),
    # extras: beta and delta of run 2 also rest on run 2's KeySet, lock results and ledger entry, all consequences of the swap
    ("strict: alpha and zeta from one run, beta and delta from another", alpha_and_zeta_from_one_run_beta_and_delta_from_another,
     Expect("problems",
            required=("beta is bound to a different run than alpha's: run_id 'run_2' vs 'run_1'",
                      "delta is bound to a different run than alpha's: run_id 'run_2' vs 'run_1'"),
            allowed_extra=("beta's Decision was made from a different KeySet than alpha produced",
                           "beta's Decision rests on a different lock result than zeta produced for",
                           "delta's entry was recorded under run_id 'run_2' but the run is 'run_1'", CHAIN_NOT_SHOWN,
                           # run 2's content against run 1's ledger: delta refuses to build a receipt across runs
                           "delta issued no verification receipt: ValueError: the ledger entry was recorded under run"))),
    # extras: beta's Decision was made from the real KeySet, so it also disagrees with the altered alpha
    ("strict: the KeySet is altered after zeta evaluated it", keyset_altered_after_zeta_evaluated_it,
     Expect("problems",
            required=("zeta lock sepsis_lock was evaluated from a different KeySet than alpha produced",
                      "zeta lock abnormal_vitals_lock was evaluated from a different KeySet than alpha produced",
                      "(its recorded KeySet fingerprint differs from alpha's)"),
            allowed_extra=("beta's Decision was made from a different KeySet than alpha produced",
                           "the Decision cites key(s) alpha did not list as present"))),
    # extra: the swapped-in result came from the well run, so zeta's own KeySet check also fires on that lock
    ("strict: a lock result is altered after beta decided on it", lock_result_altered_after_beta_decided_on_it,
     Expect("problems", required=("beta's Decision rests on a different lock result than zeta produced for sepsis_lock",),
            allowed_extra=("zeta lock sepsis_lock was evaluated from a different KeySet than alpha produced",))),
    ("strict: the Decision is altered after delta recorded it", decision_altered_after_delta_recorded_it,
     Expect("problems", required=("delta recorded a Decision other than the one beta produced",
                                  "the Decision delta recorded differs from beta's in: instructions"))),
    ("strict: beta is given another lock state's results", beta_decided_from_another_lock_result,
     Expect("refused", required=("evaluated from a different KeySet than the one given",), raises=("KeySetMismatchError",))),
    # extra: the foreign entry is not a member of the ledger the run holds
    ("strict: delta recorded another Decision, quoting beta's digest", delta_recorded_another_decision,
     Expect("problems", required=("the Decision delta recorded differs from beta's in:",),
            allowed_extra=("the ledger receipt is for other content", "entry_hash is not the delta content's immutable_hash",
                           "previous_hash is not the delta content's previous_hash", CHAIN_NOT_SHOWN))),
    ("strict: beta refuses a Decision whose basis contradicts its keys", contradictory_basis_is_refused_by_beta,
     Expect("refused", required=("confidence_basis is 'absence' but triggered_by_keys implies 'keys'",), raises=("ValueError",))),
    ("strict: delta refuses a contradictory Decision that skipped construction",
     contradictory_basis_that_skips_construction_is_refused_by_delta,
     Expect("refused", required=("confidence_basis is 'absence' but triggered_by_keys implies 'keys'",), raises=("ValueError",))),
    ("strict: beta refuses to decide from a stale replay", stale_replay_is_refused_by_beta,
     Expect("refused", required=("zeta refused the observation behind lock result(s) as stale",),
            raises=("StaleLockResultError",))),
    ("strict: the same Decision recorded twice in one run", the_same_decision_is_recorded_twice_in_one_run,
     Expect("refused", required=("already recorded a Decision",), raises=("DuplicateRecordError",))),
    # extra: a missing context also leaves out the decision_digest that the context carries
    ("strict: a stage carries no context", a_stage_carries_no_context,
     Expect("problems", required=("delta carries no context",),
            allowed_extra=("delta names no decision_digest", "delta issued no verification receipt: TypeError", CHAIN_NOT_SHOWN))),
    # extras: invented contents disagree with themselves in every way a real run would not (no fingerprint, no newly
    # triggered locks, keys the invented alpha does not hold, a Decision that differs from the entry, an unverified chain)
    ("strict: a run fabricated with digests that do not chain", a_run_fabricated_with_digests_that_do_not_chain,
     Expect("problems",
            required=("zeta lock any_lock was evaluated from a different KeySet than alpha produced",
                      "alpha carries no keyset_fingerprint", CHAIN_NOT_SHOWN),
            allowed_extra=("beta's Decision was made from a different KeySet than alpha produced",
                           "beta's Decision rests on a different lock result than zeta produced for any_lock",
                           "delta recorded a Decision other than the one beta produced",
                           "the Decision delta recorded differs from beta's in:",
                           "alpha lists present_names that its own keys do not hold as present: anything",
                           "beta's Decision lists no newly_triggered_locks",
                           # an invented run has no fingerprint to carry (Step 11: a legacy Decision is refused by the strict check)
                           "carries no content_fingerprint",
                           # there is no ledger and no checkpoint behind an invented run, so no receipt can be asked for
                           "delta issued no verification receipt: this scenario holds no checkpoint"))),
    ("strict: a ledger truncated with its head reset", a_ledger_truncated_with_its_head_reset,
     Expect("refused", required=("cause: ledger shorter than the checkpoint: it holds 2 entries and the checkpoint covers 3",),
            raises=("ValueError",))),
    ("strict: a ledger rolled back without resetting its head", a_ledger_rolled_back_without_resetting_its_head,
     Expect("refused", required=("the ledger's chain does not verify, so no receipt is issued", "cause: ledger's own chain check fails"),
            raises=("ValueError",))),
    ("strict: an empty checkpoint against an honest ledger", an_empty_checkpoint_against_an_honest_ledger,
     Expect("refused", required=("cause: empty checkpoint: length 0",), raises=("ValueError",))),
    ("strict: a checkpoint taken from another ledger", a_checkpoint_taken_from_another_ledger,
     Expect("refused", required=("cause: unmatched checkpoint: its head names no entry of this ledger",), raises=("ValueError",))),
    ("strict: a lock result zeta refused as stale is rested on", a_stale_lock_result_is_rested_on,
     Expect("problems", required=("zeta lock sepsis_lock was refused as stale", "zeta lock abnormal_vitals_lock was refused as stale"))),
    ("strict: a lock result is filed under another lock's id", a_lock_result_filed_under_another_locks_id,
     Expect("problems", required=("zeta lock sepsis_lock carries lock_id 'abnormal_vitals_lock'",
                                  "zeta lock abnormal_vitals_lock carries lock_id 'sepsis_lock'"))),
    ("strict: alpha lists a present key its own keys do not hold", alpha_lists_a_key_it_does_not_hold_as_present,
     Expect("problems",
            required=("alpha lists present_names that its own keys do not hold as present: invented_key",))),
    ("strict: zeta and beta named the digest of another KeySet", zeta_and_beta_named_the_digest_of_another_keyset,
     Expect("problems",
            required=("zeta lock sepsis_lock was evaluated from a different KeySet than alpha produced (its recorded KeySet fingerprint differs",
                      "zeta lock abnormal_vitals_lock was evaluated from a different KeySet than alpha produced (its recorded KeySet fingerprint differs",
                      "beta's Decision was made from a different KeySet than alpha produced (its recorded KeySet fingerprint differs"))),
    ("strict: alpha's origin says it was observed after the Decision", an_origin_observed_after_the_decision,
     Expect("problems", required=("alpha origin observed_at", "is later than the Decision's timestamp"))),
    ("strict: a KeySet substituted under a copied fingerprint string is recomputed", a_keyset_substituted_under_a_copied_fingerprint_is_recomputed,
     Expect("problems", required=("alpha's KeySet fingerprint does not match a recomputation from alpha's keys",))),
    # Each of the next five fails to verify, and now says why. Delta refuses to issue a receipt where the ledger is not
    # what the checkpoint held outside it recorded, and CNS refuses a receipt that is not for the content it was given.
    # CHAIN_NOT_SHOWN is the consequence of either, so it is an allowed extra beside the named cause.
    ("strict: delta's content names a hash the ledger never wrote", delta_content_names_a_hash_the_ledger_never_wrote,
     Expect("problems", required=("the ledger receipt is for other content",),
            allowed_extra=("entry_hash is not the delta content's immutable_hash", CHAIN_NOT_SHOWN))),
    ("strict: delta content of another Decision under the ledger's hashes", delta_content_of_another_decision_under_the_ledgers_hashes,
     Expect("problems", required=("the ledger receipt is for other content",), allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: the ledger chain is broken after the run", the_ledger_chain_is_broken_after_the_run,
     Expect("problems", required=("delta issued no verification receipt: ValueError: the ledger's chain does not verify",),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: nobody asked delta whether the chain verifies", nobody_asked_delta_whether_the_chain_verifies,
     Expect("problems", required=(CHAIN_NOT_SHOWN,))),
    ("strict: a scenario that holds no checkpoint is refused", a_scenario_that_holds_no_checkpoint_is_refused,
     Expect("problems", required=("holds no checkpoint taken before the attack", CHAIN_NOT_SHOWN))),
    ("strict: an unbound append to a ledger that requires a context", an_unbound_append_to_a_ledger_that_requires_a_context,
     Expect("refused", required=("requires a context",), raises=("ContextRequiredError",))),
    ("strict: a second Decision for an event already recorded", a_second_decision_for_an_event_already_recorded,
     Expect("refused", required=("already has a Decision recorded under run",), raises=("DuplicateRecordError",))),
    ("strict: one run spanning two events", one_run_spanning_two_events,
     Expect("refused", required=("belongs to event 'event_1', not 'event_9'",), raises=("ValueError",))),
    ("strict: an older Decision after a newer one for the same entity", an_older_decision_after_a_newer_one_for_the_same_entity,
     Expect("refused", required=("older than the newest Decision recorded for 'patient_1'",), raises=("StaleDecisionError",))),
    ("strict: an append onto a head that does not match", an_append_onto_a_head_that_does_not_match,
     Expect("refused", required=("head does not match",), raises=("LedgerCorruptError",))),
    # --- the receipt itself: each starts from delta's real receipt and alters it in one way; no root may be issued ---
    ("strict: a receipt whose heads are not the entry's own hash", a_receipt_with_both_heads_zeroed,
     Expect("problems", required=("its ledger_head is not the entry's own hash",),
            allowed_extra=("its checkpoint_head is not the entry's own hash", CHAIN_NOT_SHOWN))),
    ("strict: a receipt whose index is beyond the ledger", a_receipt_with_an_index_beyond_its_ledger_and_its_checkpoint,
     Expect("problems", required=("index 4 is not within a ledger of 1 entries",),
            allowed_extra=("is not covered by its checkpoint_length 1", CHAIN_NOT_SHOWN))),
    ("strict: a receipt for entry 4 of 9 under a checkpoint that covers one", a_receipt_for_entry_four_of_nine_under_a_checkpoint_that_covers_one,
     Expect("problems", required=("index 4 is not covered by its checkpoint_length 1",), allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: a receipt that names another entry's hashes", a_receipt_naming_another_entrys_hashes,
     Expect("problems", required=("entry_hash is not the delta content's immutable_hash",
                                  "previous_hash is not the delta content's previous_hash"),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: another run's receipt relabelled, its entry digest a lying str subclass",
     a_receipt_relabelled_with_another_runs_context_and_a_lying_entry_digest,
     Expect("problems", required=("the ledger receipt's entry_digest is not a full lowercase SHA-256 (an exact str)",),
            allowed_extra=("entry_hash is not the delta content's immutable_hash", CHAIN_NOT_SHOWN))),
    ("strict: a receipt with a str-subclass head", a_receipt_with_a_str_subclass_head,
     Expect("problems", required=("the ledger receipt's ledger_head is not a full lowercase SHA-256 (an exact str)",),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: a receipt with an extra key that prints as a field", a_receipt_with_an_extra_key_that_prints_as_a_field,
     Expect("problems", required=("as plain str keys; these differ",), allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: a receipt whose real key is replaced by one that prints alike", a_receipt_whose_real_key_is_replaced_by_one_that_prints_alike,
     Expect("problems", required=("as plain str keys; these differ",), allowed_extra=(CHAIN_NOT_SHOWN,))),
    # --- attacks on the hardened components (the matrix rows), each with the boundary that must refuse it ---
    ("strict: delta refuses a narrative edit that keeps the old content fingerprint", a_narrative_edit_under_the_old_content_fingerprint,
     Expect("refused", required=("Decision.content_fingerprint does not match the Decision's own fields",), raises=("ValueError",))),
    ("strict: a legacy Decision with no content fingerprint is refused", a_legacy_decision_with_no_content_fingerprint_is_refused_by_the_strict_check,
     Expect("problems", required=("beta's Decision carries no content_fingerprint", "delta's embedded Decision carries no content_fingerprint"))),
    # extra: delta's embedded copy of the Decision no longer equals the content_fingerprint beta carries
    ("strict: a content fingerprint altered in beta's content only", a_content_fingerprint_altered_in_beta_content_only,
     Expect("problems", required=("the Decision delta recorded differs from beta's in: content_fingerprint",),
            allowed_extra=("delta recorded a Decision other than the one beta produced",))),
    ("strict: a stale content fingerprint in an unbound ledger cannot be bound to a run",
     a_stale_content_fingerprint_in_an_unbound_ledger_cannot_be_bound_to_a_run,
     Expect("refused", required=("recorded under no run, so it cannot be bound to one",), raises=("ValueError",))),
    # extra: the ledger's chain is broken, so no receipt could be wanted either way
    ("strict: a forged chain_verified flag is not evidence", a_forged_chain_verified_flag,
     Expect("problems", required=("chain_verified is a bare assertion and is not evidence; pass chain= a delta verification receipt",),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: a complete rewrite against an empty checkpoint", a_complete_rewrite_against_an_empty_checkpoint,
     Expect("problems", required=("delta issued no verification receipt: ValueError: the checkpoint is empty, foreign, mistyped or not contained",
                                  "cause: empty checkpoint: length 0"),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: a complete rewrite against a checkpoint head that equals everything",
     a_complete_rewrite_against_a_checkpoint_head_that_equals_everything,
     Expect("problems", required=("delta issued no verification receipt: ValueError: the checkpoint is empty, foreign, mistyped or not contained",
                                  "cause: mistyped checkpoint"),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: the identical Decision replayed under a fresh event and run", the_identical_decision_replayed_under_a_fresh_event_and_run,
     Expect("refused", required=("replay: this Decision is already recorded",), raises=("DuplicateRecordError",))),
    ("strict: a backdated entry timestamp", a_backdated_entry_timestamp,
     Expect("refused", required=("backdated entry",), raises=("ValueError",))),
    ("strict: an injected failure during append leaves the ledger as it was", an_injected_failure_during_append_leaves_the_ledger_as_it_was,
     Expect("refused", required=("the store refused the write",), raises=("RuntimeError",))),
    ("strict: beta refuses lock results recorded for another entity", lock_results_from_another_entity_are_refused_by_beta,
     Expect("refused", required=("lock result(s) record another entity",), raises=("EntityMismatchError",))),
    ("strict: str-subclass ids in a context are refused", str_subclass_ids_in_a_context_are_refused,
     Expect("refused", required=("context field event_id must be a str",), raises=("TypeError",))),
    ("strict: a context that changes between reads is recorded as its first read",
     a_context_mapping_that_changes_between_reads_is_recorded_as_first_read, CLEAN),
    ("strict: a list the caller mutates after recording does not reach the stored Decision",
     a_list_the_caller_mutates_after_recording_does_not_reach_the_stored_decision, CLEAN),
    # --- the reviewers' attacks, with real objects ---
    ("strict: a replay with the content fingerprint blanked is refused as a downgrade", a_replay_with_the_content_fingerprint_blanked,
     Expect("refused", required=("content_fingerprint is empty", "downgrade"), raises=("ValueError",))),
    ("strict: an entity id that lies about its equality is refused", an_entity_id_that_lies_about_its_equality,
     Expect("refused", required=("Decision.entity_id must be exactly a str",), raises=("TypeError",))),
    ("strict: a list that changes between reads is stored as its first read", a_list_that_changes_between_reads_is_stored_as_its_first_read, CLEAN),
    ("strict: a datetime subclass that backdates an entry is refused", a_datetime_subclass_that_backdates_an_entry,
     Expect("refused", required=("timestamp must be exactly a datetime",), raises=("TypeError",))),
    ("strict: a sink that appends to its own ledger is refused", a_sink_that_appends_to_its_own_ledger,
     Expect("refused", required=("append from inside a sink is not allowed",), raises=("RuntimeError",))),
    ("strict: a checkpoint subclass that answers honestly only once", a_checkpoint_subclass_that_answers_honestly_only_once, CLEAN),
    ("strict: a receipt asked for an entry beyond the checkpoint is refused", a_receipt_asked_for_an_entry_beyond_the_checkpoint,
     Expect("refused", required=("is not covered by the checkpoint (length 1)",), raises=("ValueError",))),
    ("strict: a receipt whose checkpoint ends at the entry but names no such head", a_receipt_whose_checkpoint_ends_at_the_entry_but_names_no_such_head,
     Expect("problems", required=("its checkpoint_head is not the entry's own hash",), allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: a rewritten ledger with a fresh checkpoint is refused against the checkpoint held outside",
     a_rewritten_ledger_with_a_fresh_checkpoint_is_refused_against_the_checkpoint_held_outside,
     Expect("problems", required=("the ledger receipt's checkpoint_head is not the checkpoint held outside the ledger",),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: an honest run against the checkpoint held outside", an_honest_run_against_the_checkpoint_held_outside, CLEAN),
    ("strict: GAP, a rewritten ledger with a fresh checkpoint and no checkpoint held outside",
     GAP_a_rewritten_ledger_with_a_fresh_checkpoint_and_no_checkpoint_held_outside, GAP),
    ("strict: an export verified outside the producer, with the checkpoint held outside", an_honest_export_is_verified_outside_the_producer, CLEAN),
    ("strict: an export with an edited entry is refused by verify_export", an_export_with_an_edited_entry_is_refused,
     Expect("refused", required=("Decision.content_fingerprint does not match",), raises=("ValueError",))),
    ("strict: an export with an edited hash is refused by verify_export", an_export_with_an_edited_hash_is_refused,
     Expect("refused", required=("immutable_hash does not match the entry's content",), raises=("ValueError",))),
    ("strict: an export with a removed entry is refused by verify_export", an_export_with_a_removed_entry_is_refused,
     Expect("refused", required=("previous_hash does not continue the chain",), raises=("ValueError",))),
    ("strict: a truncated export is refused against a held checkpoint", a_truncated_export_is_refused_against_a_held_checkpoint,
     Expect("refused", required=("the export holds 1 entries but the held checkpoint names 2",), raises=("ValueError",))),
    ("strict: GAP, a truncated export with no held checkpoint", GAP_a_truncated_export_without_a_held_checkpoint, GAP),
    ("strict: an export checked against an empty checkpoint is refused", an_export_checked_against_an_empty_checkpoint_is_refused,
     Expect("refused", required=("does not contain the history the held checkpoint recorded",), raises=("ValueError",))),
    ("strict: an export checked against the checkpoint of another ledger is refused",
     an_export_checked_against_the_checkpoint_of_another_ledger_is_refused,
     Expect("refused", required=("does not contain the history the held checkpoint recorded",), raises=("ValueError",))),
    ("strict: GAP, a rewritten and rechained export with a fresh checkpoint and none held",
     GAP_a_rewritten_rechained_export_with_a_fresh_checkpoint_and_none_held, GAP),
    ("strict: a rewritten and rechained export is refused against the honest checkpoint by verify_export",
     a_rewritten_rechained_export_is_refused_by_verify_export_against_the_honest_checkpoint,
     Expect("refused", required=("does not contain the history the held checkpoint recorded",), raises=("ValueError",))),
    ("strict: a rewritten and rechained export with a fresh checkpoint is refused against the held one",
     a_rewritten_rechained_export_with_a_fresh_checkpoint_is_refused_against_the_held_one,
     Expect("problems", required=("the ledger receipt's checkpoint_head is not the checkpoint held outside the ledger",),
            allowed_extra=(CHAIN_NOT_SHOWN,))),
    ("strict: an export with require_context cleared is refused by verify_export", an_export_with_require_context_cleared_is_refused,
     Expect("refused", required=("the export says require_context=False; the verifier requires True",), raises=("ValueError",))),
    ("strict: zeta refuses a lock result bound to another entity's context", zeta_refuses_to_bind_a_lock_result_to_another_entitys_context,
     Expect("refused", required=("the LockResult was evaluated for entity 'patient_1'",), raises=("ValueError",))),
    ("strict: a verifier is asked once inside one root evaluation", a_verifier_is_asked_once_inside_one_root_evaluation,
     Expect("problems", required=("alpha's KeySet fingerprint does not match a recomputation from alpha's keys",))),
    ("strict: a required verifier that is missing is a named problem", a_required_verifier_that_is_missing,
     Expect("problems", required=("no keyset_fingerprint_of was supplied, and require_keyset_verifier is set",))),
    ("strict: an honest run with a required verifier", an_honest_run_with_a_required_verifier, CLEAN),
    # --- known gaps, stated as facts ---
    ("strict: GAP, a narrative forged by someone who recomputes the content fingerprint",
     GAP_a_decisions_narrative_forged_by_someone_who_recomputes_the_content_fingerprint, GAP),
    ("strict: GAP, a Decision cites a lock that is closed", GAP_a_decision_cites_a_lock_that_is_closed, GAP),
    ("strict: GAP, a legacy lock result with no entity id is accepted for any entity",
     GAP_a_legacy_lock_result_with_no_entity_id_is_accepted, GAP),
    ("strict: GAP, a KeySet substituted under a copied fingerprint, no recomputation supplied",
     GAP_a_keyset_substituted_under_a_copied_fingerprint_without_a_recomputation, GAP),
    ("strict: GAP, a fully hand-built consistent receipt is accepted", GAP_a_fully_hand_built_consistent_receipt_is_accepted, GAP),
    ("strict: GAP, a sink keeps a write the ledger does not have", GAP_a_sink_keeps_a_write_the_ledger_does_not_have, GAP),
    ("strict: GAP, contents fabricated by someone who recomputes the digests",
     GAP_contents_fabricated_by_someone_who_recomputes_the_digests, GAP),
    ("keys: the reference deployer signs, verifies, rotates and revokes", the_reference_keys_sign_verify_rotate_and_revoke, CLEAN),
    ("keys: an ambiguous trust list is refused (one key under two ids, a revocation naming nothing, a duplicate id, a non-ASCII id)",
     a_trust_list_that_is_ambiguous_is_refused, CLEAN),
    # --- signed receipts: Delta signs through its hook, the deployer's keys decide, CNS asks one verifier once ---
    ("signed: an honest receipt is verified and a root is issued, different from the unsigned root",
     a_receipt_signed_by_the_deployer_is_verified_and_a_root_issued, CLEAN),
    ("signed: an unsigned receipt is refused when a signature is required", an_unsigned_receipt_is_refused_when_a_signature_is_required,
     Expect("problems", required=(VERIFIER_NO_SIGNATURE,))),
    ("signed: a verifier without a signature is refused even without the requirement",
     a_verifier_without_a_signature_is_refused_without_the_requirement, Expect("problems", required=(VERIFIER_NO_SIGNATURE,))),
    ("signed: the requirement with no verifier and no signature is refused",
     a_requirement_with_no_verifier_and_no_signature_is_refused, Expect("problems", required=(SIGNATURE_REQUIRED,))),
    ("signed: a hand-built consistent receipt with no delta call and no key is refused",
     a_hand_built_consistent_receipt_with_no_delta_call_and_no_key_is_refused, Expect("problems", required=(VERIFIER_NO_SIGNATURE,))),
    ("signed: a receipt signed by an untrusted key", a_receipt_signed_by_an_untrusted_key, Expect("problems", required=(BAD_SIGNATURE,))),
    ("signed: a receipt signed by a key that claims the deployer's id", a_receipt_signed_by_a_key_claiming_the_deployers_id,
     Expect("problems", required=(BAD_SIGNATURE,))),
    ("signed: a receipt signed by a revoked key", a_receipt_signed_by_a_revoked_key, Expect("problems", required=(BAD_SIGNATURE,))),
    ("signed: a signature over another receipt", a_signature_over_another_receipt, Expect("problems", required=(BAD_SIGNATURE,))),
    ("signed: a receipt edited after signing, each of ten fields", a_receipt_edited_after_signing,
     Expect("problems", required=(BAD_SIGNATURE,))),
    ("signed: rotation, the old key and the new key both verify while both are trusted",
     rotation_keeps_the_old_key_verifying_until_it_is_retired, CLEAN),
    ("signed: rotation, a receipt of the retired key is refused", a_receipt_of_a_retired_key_is_refused_after_rotation,
     Expect("problems", required=(BAD_SIGNATURE,))),
    ("signed: DRIFT, CNS's and delta's receipt signing inputs are byte-equal and refuse alike",
     the_two_receipt_signing_inputs_do_not_drift, CLEAN),
    ("signed: GAP, a holder of a trusted key signs a forged receipt", GAP_a_holder_of_a_trusted_key_signs_a_forged_receipt, GAP),
    # --- the durable store across separate processes: a producer, then a fresh consumer ---
    ("store: a producer's store, checkpoint and signature are accepted by a fresh consumer, which issues a root",
     a_producer_and_a_fresh_consumer_agree, CLEAN),
    ("store: a hand-off signature with one digit changed",
     lambda: a_tampered_handoff_is_refused_by_cns(lambda w: _edit_handoff(w, "receipt_signature.hex", _flip_last_hex_digit)),
     Expect("refused", required=("the consumer exited 1", "strict check:", BAD_SIGNATURE), raises=("ValueError",))),
    ("store: a hand-off signature that is empty",
     lambda: a_tampered_handoff_is_refused_by_cns(lambda w: _edit_handoff(w, "receipt_signature.hex", lambda t: "\n")),
     Expect("refused", required=("the consumer exited 1", "strict check:", "receipt_signature must be a non-empty bytes"), raises=("ValueError",))),
    ("store: hand-off contents with another Decision",
     lambda: a_tampered_handoff_is_refused_by_cns(lambda w: _edit_handoff(w, "contents.json", _another_decision)),
     Expect("refused", required=("the consumer exited 1", "strict check:", "differs"), raises=("ValueError",))),
    ("store: hand-off contents with another KeySet",
     lambda: a_tampered_handoff_is_refused_by_cns(lambda w: _edit_handoff(w, "contents.json", _another_keyset)),
     Expect("refused", required=("the consumer exited 1", "strict check:", "fingerprint"), raises=("ValueError",))),
    ("store: a ledger file truncated below the checkpoint", a_ledger_file_truncated_below_the_checkpoint,
     Expect("refused", required=("reconcile LOST",), raises=("ValueError",))),
    ("store: an entry rewritten and the file rechained", an_entry_rewritten_and_the_file_rechained,
     Expect("refused", required=("reconcile DIVERGED",), raises=("ValueError",))),
    ("store: a restart after acknowledged entries were deleted is refused", a_restart_after_acknowledged_entries_were_deleted_is_refused,
     Expect("refused", required=("refused to attach: reconcile says LOST",), raises=("StoreError",))),
    ("store: a restart after the history was rewritten is refused", a_restart_after_the_history_was_rewritten_is_refused,
     Expect("refused", required=("refused to attach: reconcile says DIVERGED",), raises=("StoreError",))),
    ("store: a checkpoint that does not extend the stored one is refused", a_checkpoint_that_does_not_extend_the_stored_one_is_refused,
     Expect("refused", required=("does not extend the stored one",), raises=("StoreError",))),
    ("store: a restart by the README recipe after the file was deleted cannot launder the loss",
     a_restart_by_the_readme_recipe_after_the_file_was_deleted_cannot_launder_the_loss,
     Expect("refused", required=("does not extend the stored one",), raises=("StoreError",))),
    ("store: an honest restart attaches and carries on", an_honest_restart_attaches_and_carries_on, CLEAN),
    ("store: a torn final line is recovered, reported, and the root is issued", a_torn_final_line_is_recovered_and_reported, CLEAN),
    ("store: damage in the middle of the file", mid_file_damage_is_refused,
     Expect("refused", required=("StoreCorruptError", "damaged before the end of the file"), raises=("ValueError",))),
    ("store: a checkpoint replaced by an older signed one is refused by a consumer that requires OK",
     a_checkpoint_replaced_by_an_older_signed_one,
     Expect("refused", required=("reconcile UNWITNESSED_TAIL",), raises=("ValueError",))),
    ("store: a checkpoint with no signature when one is required", a_checkpoint_with_no_signature_when_one_is_required,
     Expect("refused", required=("the checkpoint is not signed but a signature check was asked for",), raises=("ValueError",))),
    ("store: a producer killed with SIGKILL loses no acknowledged entry", a_producer_killed_mid_run_loses_no_acknowledged_entry, CLEAN),
    ("store: GAP, an older signed checkpoint carries no freshness", GAP_an_older_signed_checkpoint_is_accepted_as_an_unwitnessed_tail, GAP),
    ("store: GAP, a ledger rolled back to an older signed package", GAP_a_ledger_rolled_back_to_an_older_signed_package_is_accepted, GAP),
    # --- the verify command: make_package.py and verify_package.py as two processes, files only between them ---
    ("package: an honest package verifies in another process; an unsigned one only with --allow-unsigned",
     an_honest_package_verifies_in_another_process, CLEAN),
    ("package: altered contents", lambda: refused_package((), attack=altered_contents),
     Expect("refused", required=("verify_package refused (exit 1)", "the Decision delta recorded differs from beta's in: instructions"), raises=("ValueError",))),
    ("package: altered export", lambda: refused_package((), attack=an_altered_export),
     Expect("refused", required=("verify_package refused (exit 1)", 'the ledger export is refused:'), raises=("ValueError",))),
    ("package: a substituted receipt", lambda: refused_package((), ("--run-offset", "10"), attack=a_substituted_receipt),
     Expect("refused", required=("verify_package refused (exit 1)", 'the receipt in the package is not the one Delta issues for this export and checkpoint'), raises=("ValueError",))),
    ("package: a substituted receipt with its own signature", lambda: refused_package((), ("--run-offset", "10"), attack=a_substituted_receipt_with_its_own_signature),
     Expect("refused", required=("verify_package refused (exit 1)", 'the receipt in the package is not the one Delta issues for this export and checkpoint', 'receipt signature does not verify'), raises=("ValueError",))),
    ("package: a substituted checkpoint, older and genuinely signed", lambda: refused_package(("--older-checkpoint-length", "1"), attack=a_substituted_older_checkpoint),
     Expect("refused", required=("verify_package refused (exit 1)", 'is not covered by the checkpoint (length 1)', "is not the held checkpoint's length 1"), raises=("ValueError",))),
    ("package: a substituted checkpoint, empty", lambda: refused_package((), attack=a_substituted_empty_checkpoint),
     Expect("refused", required=("verify_package refused (exit 1)", 'the checkpoint is refused:', 'names no entry (length 0)'), raises=("ValueError",))),
    ("package: a substituted checkpoint, of another ledger", lambda: refused_package((), ("--run-offset", "10"), attack=a_substituted_checkpoint_of_another_ledger),
     Expect("refused", required=("verify_package refused (exit 1)", 'the ledger export is refused:', 'does not contain the history the held checkpoint recorded'), raises=("ValueError",))),
    ("package: no receipt signature under --require-signed", lambda: refused_package(("--no-receipt-signature",), attack=a_receipt_signature_that_is_missing),
     Expect("refused", required=("verify_package refused (exit 1)", 'a verifier was supplied but the receipt has no signature'), raises=("ValueError",))),
    ("package: no receipt signature and no flag is refused, naming why", lambda: refused_package(("--no-receipt-signature",), attack=a_receipt_signature_that_is_missing_with_no_flag),
     Expect("refused", required=("verify_package refused (exit 1)", 'no signature.json', '--allow-unsigned'), raises=("ValueError",))),
    ("package: a dangling link named signature.json is not a missing file", a_dangling_link_named_signature_json_is_not_a_missing_file, CLEAN),
    ("package: a signature file that holds null is wrong, not missing", lambda: refused_package((), attack=a_signature_file_that_holds_null),
     Expect("refused", required=("verify_package refused (exit 1)", 'signature.json is not {"receipt_signature": <hex>}'), forbidden=("no signature.json",), raises=("ValueError",))),
    ("package: --allow-unsigned does not excuse a signature file that holds null", lambda: refused_package((), attack=a_signature_file_that_holds_null_under_allow_unsigned),
     Expect("refused", required=("verify_package refused (exit 1)", 'signature.json is not {"receipt_signature": <hex>}'), raises=("ValueError",))),
    ("package: a signature file with an extra key is refused", lambda: refused_package((), attack=a_signature_file_with_an_extra_key),
     Expect("refused", required=("verify_package refused (exit 1)", 'signature.json is not {"receipt_signature": <hex>}'), raises=("ValueError",))),
    ("package: a verifier that answers differently the second time is refused, not a traceback", a_verifier_that_answers_differently_the_second_time,
     Expect("refused", required=("verify_package refused (exit 1)", "answered differently the second time"), raises=("ValueError",))),
    ("package: --allow-unsigned does not excuse a signature that is there and wrong", lambda: refused_package(("--receipt-key-id", "k2"), attack=a_bad_receipt_signature_under_allow_unsigned),
     Expect("refused", required=("verify_package refused (exit 1)", 'receipt signature does not verify'), raises=("ValueError",))),
    ("package: no checkpoint signature under --require-signed", lambda: refused_package(("--no-checkpoint-signature",), attack=a_checkpoint_signature_that_is_missing),
     Expect("refused", required=("verify_package refused (exit 1)", 'the checkpoint is not signed but a signature check was asked for'), raises=("ValueError",))),
    ("package: a receipt signed by the wrong key under a trusted id", lambda: refused_package(("--receipt-key-id", "k2"), attack=a_receipt_key_that_is_the_wrong_key),
     Expect("refused", required=("verify_package refused (exit 1)", 'receipt signature does not verify'), raises=("ValueError",))),
    ("package: a receipt signed by an untrusted key", lambda: refused_package(("--receipt-key-id", "k2"), attack=a_receipt_key_that_is_untrusted),
     Expect("refused", required=("verify_package refused (exit 1)", 'receipt signature does not verify'), raises=("ValueError",))),
    ("package: a receipt signed by a revoked key", lambda: refused_package(("--receipt-key-id", "k2"), attack=a_receipt_key_that_is_revoked),
     Expect("refused", required=("verify_package refused (exit 1)", 'receipt signature does not verify'), raises=("ValueError",))),
    ("package: a checkpoint signed by an untrusted key", lambda: refused_package((), attack=a_checkpoint_key_that_is_untrusted),
     Expect("refused", required=("verify_package refused (exit 1)", 'the checkpoint signature does not verify'), raises=("ValueError",))),
    ("package: a checkpoint or trust list whose real path is inside the package exits 2",
     the_checkpoint_and_the_trust_list_must_live_outside_the_package, CLEAN),
    ("package: a duplicate key in any package file is refused naming the file and the key",
     a_duplicate_key_in_any_package_file_is_refused_naming_the_file_and_key, CLEAN),
    ("package: a validly signed receipt for an older entry is refused unless --entry names it",
     a_validly_signed_receipt_for_an_older_entry_is_refused_unless_entry_names_it, CLEAN),
    ("package: a deeply nested input is exit 2 or a named refusal, never a traceback",
     a_deeply_nested_input_is_exit_two_or_a_named_refusal_never_a_traceback, CLEAN),
    ("package: inputs that cannot be read, and usage errors, exit 2 and not 1", inputs_that_cannot_be_read_exit_two_not_one, CLEAN),
    # --- domain packs: a second, unrelated domain through the same four stages, and the pack contract's refusals ---
    ("domain: a service-health run is accepted by the strict check, with a free-form decision",
     a_service_health_run_is_accepted_by_the_strict_check, CLEAN),
    ("domain: the pack identity is recorded in origin and bound by alpha's digest",
     the_pack_identity_is_recorded_in_origin_and_bound_by_the_digest, CLEAN),
    ("domain: the pediatric pack reached through the registry gives the same keys and records its identity",
     the_pediatric_pack_runs_through_the_registry_with_its_identity, CLEAN),
    ("domain: a pack with a threshold outside its bounds is refused at registration", a_pack_with_an_out_of_bounds_threshold_is_refused,
     Expect("refused", required=("outside",), raises=("PackValidationError",))),
    ("domain: a pack whose parameter has no approval is refused at registration", a_pack_with_no_approval_is_refused,
     Expect("refused", required=("approved_by",), raises=("PackValidationError",))),
    ("domain: a pack that emits a key it did not declare is refused", a_pack_that_emits_an_undeclared_key_is_refused,
     Expect("refused", required=("surprise",), raises=("PackError",))),
    ("domain: a pack name cannot be registered twice", a_pack_name_cannot_be_registered_twice,
     Expect("refused", required=("already registered",), raises=("PackError",))),
    ("domain: keys of one pack presented with another run's stages are refused", keys_of_one_pack_under_the_digest_of_another_are_refused,
     Expect("problems", required=("zeta lock outage_lock was evaluated from a different KeySet than alpha produced",
                                  "beta's Decision was made from a different KeySet than alpha produced",
                                  "the Decision cites key(s) alpha did not list as present: latency_critical"),
            allowed_extra=("zeta lock slow_lock was evaluated from a different KeySet than alpha produced",
                           "its recorded KeySet fingerprint differs from alpha's"))),
    ("domain: GAP, a pack identity is the producer's claim and nothing authenticates it",
     GAP_a_pack_identity_is_the_producers_claim, GAP),
    # --- the oracle held to account with real objects ---
    ("oracle: a component that exits fails its own scenario only", the_oracle_flags_a_component_that_exits, CLEAN),
    ("oracle: a refusal that edited an entry's content is a state change", the_oracle_flags_a_refusal_that_edited_an_entrys_content, CLEAN),
    ("oracle: refusal text returned while the attack succeeded fails", the_oracle_flags_refusal_text_returned_while_the_attack_succeeded, CLEAN),
    ("oracle: an Expect text that matches anything is refused", the_oracle_refuses_expect_texts_that_match_anything, CLEAN),
    ("oracle: a rewrite of the ledger itself is not called a wrong ledger", a_rewrite_of_the_ledger_itself_is_not_called_a_wrong_ledger, CLEAN),
    ("oracle: a checkpoint row cannot pass on an unrelated refusal", a_checkpoint_row_cannot_pass_on_an_unrelated_refusal,
     Expect("problems", required=("delta refused for a reason other than the checkpoint",))),
    # --- the manifest checks ---
    ("manifest: a dependency hidden behind a bracket in a comment", a_dependency_hidden_behind_a_bracket_in_a_comment,
     Expect("problems", required=("interconnected_delta",))),
    ("manifest: a decoy dependency list in a multi-line string", a_decoy_dependency_list_in_a_multiline_string,
     Expect("problems", required=("interconnected_delta",))),
    ("manifest: a checkout at the pinned commit with an edited file", a_checkout_at_the_pinned_commit_with_an_edited_file,
     Expect("problems", required=("interconnected_zeta has 2 uncommitted or untracked change(s) in its checkout",))),
    ("manifest: an older zeta installed beside the others", an_older_zeta_installed_beside_the_others,
     Expect("problems", required=("zeta is installed from commit f416b02",))),
]


check_table(SCENARIOS)  # a row that is not (name, scenario, Expect), or a repeated name, stops the script before it runs


def main() -> int:
    wrong: List[str] = []
    for name, scenario, expect in SCENARIOS:
        found, why = judge(expect, scenario)
        ok = not why
        print(f"{'ok  ' if ok else 'FAIL'} {name:52} -> {'no problems' if not found else str(len(found)) + ' named'}")
        if not ok:
            wrong.append(f"{name}: {'; '.join(why)}; got {found}")
    for line in wrong:
        print(f"spine: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

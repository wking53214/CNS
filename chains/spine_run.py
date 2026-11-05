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
should be refused, if it crashes without declaring it, or if a refusal changed the state it guarded. Seven scenarios,
marked GAP, record what the strict check does NOT catch as facts that expect no problem: authorship (a forger who
recomputes every digest and fingerprint and writes a consistent receipt), a receipt written by hand over real contents
with no ledger behind it, a narrative forged by someone who also recomputes the keyless content fingerprint, a Decision
citing a closed lock, a legacy lock result with no entity id, a KeySet swapped under a copied fingerprint when no
recomputation is supplied, and a sink whose own store keeps a write the ledger does not have (delta's idempotency
contract). They go red the day the gap closes and are then updated on purpose.

The run also attacks the receipt itself (zeroed heads, an index beyond the ledger or the checkpoint, another entry's
hashes, a lying str-subclass digest or head, a key that only prints like a field name) starting from the receipt delta
really issues, and the hardened ledger (a replay with the fingerprint blanked, a lying entity id, a list that changes
between reads, a datetime subclass, a sink that appends, a checkpoint that answers honestly once, a receipt for an entry
the checkpoint does not cover). Delta's refusal of a checkpoint is one sentence for five causes; the runner's own wrapper
(`ask_delta`) names the cause so each scenario requires its own.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sys
import threading
import warnings
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Tuple

from spine_oracle import Expect, check_table, judge
from spine_oracle import refused as _refused

import alpha.cns_connector as alpha_cns
import beta.cns_connector as beta_cns
import delta.cns_connector as delta_cns
import delta.context as delta_context
import zeta.cns_connector as zeta_cns
from alpha import VitalsObservation, observe
from beta import (
    Decision, DecisionEngine, DecisionRule, DecisionRuleRegistry, KeySetMismatchError,
    StaleLockResultError, decision_fingerprint)
from beta.fingerprint import content_fingerprint
from cns.gate import subject_digest
from cns_composition.spine_trace import (
    CONTEXT_SCHEMA, SpineRecord, context_problems, problems, root, strict_problems, strict_root)
from delta import DecisionLedger
from delta.ledger import LedgerCheckpoint
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


def stages(vitals=SICK, ctx=CTX, results_from=None, keys_for_decision=None, bind_keyset_of=None, origin=None) -> Dict[str, Any]:
    """Run the four stages for real, binding each to the context and to the digest of the stage before it."""
    locks, engine = build()
    ledger = DecisionLedger(require_context=True)
    entity = ctx["entity_id"]
    keys = observe(vitals)
    alpha = alpha_cns.keyset_content(keys, context=ctx, origin=origin)
    # zeta and beta are told which KeySet digest to name; nothing in either can check it against what they evaluated.
    da = subject_digest(alpha if bind_keyset_of is None else alpha_cns.keyset_content(observe(bind_keyset_of), context=ctx))
    results = LockEvaluator(locks).evaluate_all(entity, keys, T0)
    zeta = {lid: zeta_cns.lock_result_content(r, context=ctx, keyset_digest=da) for lid, r in results.items()}
    decided_on = results if results_from is None else results_from
    decision = engine.decide(entity, keys if keys_for_decision is None else keys_for_decision, decided_on, T0)
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
    return "wrong-ledger checkpoint: its head names no entry of this ledger"


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


def refused(thunk: Callable[[], Any], state: Callable[[], Any] | None = None, catch: Tuple[type, ...] = ()) -> List[str]:
    """What a boundary refused, as a problem string, or nothing if it let the call through. `state` is compared before
    and after: a refusal that changed it is a second problem (see spine_oracle.refused). `catch` adds exception classes
    beyond the ValueErrors, TypeErrors and OverflowErrors the oracle already treats as refusals."""
    return _refused(thunk, catch=(StaleLockResultError, KeySetMismatchError) + tuple(catch), state=state)


def ledger_state(ledger: DecisionLedger) -> Callable[[], Any]:
    """What a refusal must leave alone: the length, the head AND a digest of every entry's hash in order, so a refusal that
    swapped one entry for another of the same count and head still shows."""
    def state() -> Any:
        entries = list(ledger.entries)
        return (len(entries), ledger.chain_head,
                hashlib.sha256("\n".join(e.immutable_hash for e in entries).encode("ascii")).hexdigest())
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
    """Zeta's results are bound to another patient's context, though they cite alpha's KeySet digest."""
    p = stages(SICK)
    other = {**CTX, "entity_id": "patient_2"}
    p["zeta"] = {lid: zeta_cns.lock_result_content(r, context=other, keyset_digest=p["da"]) for lid, r in p["results"].items()}
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
    empty = LedgerCheckpoint(0, DecisionLedger().chain_head)
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
    """Beta's decision_fingerprint covers 5 of a Decision's 15 fields; a separate content_fingerprint covers 13 (all but
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
    worker = threading.Thread(
        target=lambda: result.append(refused(lambda: ledger.append(p["decision"], context=CTX), ledger_state(ledger), catch=(RuntimeError,))),
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


def a_checkpoint_subclass_that_answers_honestly_only_once() -> List[str]:
    """Delta may refuse it, or issue a receipt; if it issues one, every length and head on it must be the ones it verified."""
    p = stages(SICK)
    real = p["ledger"].checkpoint()
    sneaky = AnswersHonestlyOnce(real.length, real.head)
    object.__setattr__(sneaky, "_seen", {})
    try:
        receipt = delta_cns.verification_receipt(p["ledger"], sneaky, context=CTX, decision_digest=p["delta"]["decision_digest"])
    except (ValueError, TypeError):
        return []
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
    if "wrong-ledger checkpoint" not in why:
        raise AssertionError(f"the original checkpoint was refused, but not as one naming no entry of the rewrite: {why}")
    return p


def a_complete_rewrite_against_an_empty_checkpoint() -> List[str]:
    """Row 11b. The run is rewritten completely (ledger and exports) and verified against a checkpoint of length 0, which
    fits every self-consistent ledger. Delta refuses to issue a receipt against it."""
    q = rewrite_the_run_completely()
    q["checkpoint"] = LedgerCheckpoint(0, DecisionLedger().chain_head)
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
     Expect("refused", required=("cause: wrong-ledger checkpoint: its head names no entry of this ledger",), raises=("ValueError",))),
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
     Expect("problems", required=("its ledger_head is not the entry's own hash",), allowed_extra=(CHAIN_NOT_SHOWN,))),
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

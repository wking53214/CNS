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
replay, a repeat, a truncated ledger, a missing context, a fabricated run) and state, as an `Expect` (see
`spine_oracle.py`), the problems the boundary that should refuse each one must name and the only extras it may add.
A scenario fails if a required problem is missing, if an unlisted problem appears, if it returns nothing when it
should be refused, if it crashes without declaring it, or if a refusal changed the state it guarded. Three scenarios,
marked GAP, record what the strict check does NOT catch as facts that expect no problem: they go red the day the
gap closes and are then updated on purpose.
"""

from __future__ import annotations

import dataclasses
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Tuple

from spine_oracle import Expect, Expectation, judge
from spine_oracle import refused as _refused

import alpha.cns_connector as alpha_cns
import beta.cns_connector as beta_cns
import delta.cns_connector as delta_cns
import delta.context as delta_context
import zeta.cns_connector as zeta_cns
from alpha import VitalsObservation, observe
from beta import (
    Decision, DecisionEngine, DecisionRule, DecisionRuleRegistry, KeySetMismatchError, StaleLockResultError,
    decision_fingerprint)
from cns.gate import subject_digest
from cns_composition.spine_trace import (
    CONTEXT_SCHEMA, SpineRecord, context_problems, problems, root, strict_problems, strict_root)
from delta import DecisionLedger
from zeta import Combination, LockEvaluator, LockRegistry, LockSpec

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


def stages(vitals=SICK, ctx=CTX, results_from=None, keys_for_decision=None, bind_keyset_of=None) -> Dict[str, Any]:
    """Run the four stages for real, binding each to the context and to the digest of the stage before it."""
    locks, engine = build()
    ledger = DecisionLedger(require_context=True)
    entity = ctx["entity_id"]
    keys = observe(vitals)
    alpha = alpha_cns.keyset_content(keys, context=ctx)
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


def ledger_verified(parts) -> bool:
    """Ask delta itself: the chain verifies, it still contains the history held outside it, and the content the run
    carries IS what the ledger's last entry exports, field for field (so content cannot name the hashes of an entry
    while describing a different Decision, run or time)."""
    try:
        ledger, held, content = parts["ledger"], parts["checkpoint"], parts["delta"]
        entry = ledger.entries[-1]
        exported = delta_cns.entry_content(entry, context=content.get("context"), decision_digest=content.get("decision_digest"))
        return (ledger.verify_chain_integrity() is True and ledger.verify_against(held) is True
                and subject_digest(exported) == subject_digest(content))
    except Exception:  # noqa: BLE001 - nothing to ask, or the ledger refused to answer: not shown to verify
        return False


def check(parts) -> List[str]:
    return strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], chain_verified=ledger_verified(parts))


def refused(thunk: Callable[[], Any], state: Callable[[], Any] | None = None) -> List[str]:
    """What a boundary refused, as a problem string, or nothing if it let the call through. `state` is compared before
    and after: a refusal that changed it is a second problem (see spine_oracle.refused)."""
    return _refused(thunk, catch=(StaleLockResultError, KeySetMismatchError), state=state)


def ledger_state(ledger: DecisionLedger) -> Callable[[], Any]:
    return lambda: (len(ledger.entries), ledger.chain_head)


def strict_clean(vitals) -> List[str]:
    return check(stages(vitals))


def strict_roots_differ_by_run() -> List[str]:
    a, b = stages(SICK), stages(SICK, ctx={**CTX, "run_id": "run_2"})
    ra, rb = (strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], chain_verified=ledger_verified(p)) for p in (a, b))
    return [] if ra != rb else ["the same readings in two runs produced one root"]


def strict_root_is_not_a_lenient_root() -> List[str]:
    p = stages(SICK)
    strict = strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"], chain_verified=ledger_verified(p))
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


def a_ledger_truncated_with_its_head_reset() -> List[str]:
    ledger = DecisionLedger()
    for i, vitals in enumerate((SICK, WELL, SICK)):
        engine = build()[1]
        keys = observe(vitals)
        results = LockEvaluator(build()[0]).evaluate_all("patient_1", keys, T0)
        ledger.append(engine.decide("patient_1", keys, results, T0), context={**CTX, "run_id": f"run_{i}", "event_id": f"event_{i}"})
    held = ledger.checkpoint()
    ledger.entries.pop()
    ledger.chain_head = ledger.entries[-1].immutable_hash
    assert ledger.verify_chain_integrity(), "the chain alone is expected to accept this: that is the gap"
    return [] if ledger.verify_against(held) else ["the ledger does not match the checkpoint held outside it"]


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


def GAP_contents_fabricated_by_someone_who_recomputes_the_digests() -> List[str]:
    """KNOWN GAP, stated as a fact. There is no key in this check: four contents that agree with each other, carry one
    KeySet fingerprint, chain by digest and are reported by the caller as ledger-verified pass whether or not any
    component produced them. It verifies agreement, not authorship. (Without the fingerprints, or without the
    chain claim, it is refused; the other scenarios hold that.) No problem is found."""
    ctx = dict(CTX)
    fp = "e" * 64
    alpha = {"min_confidence": 0.0, "keys": [{"name": "anything", "present": True, "confidence": 1.0, "reason": "made up"}],
             "context": dict(ctx), "present_names": ["anything"], "keyset_fingerprint": fp}
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
    beta = {**core, "context": dict(ctx), "keyset_digest": da,
            "lock_result_digests": {k: subject_digest(v) for k, v in zeta.items()}}
    delta = {"audit_id": "0" * 16, "timestamp": "2026-10-01T08:00:00", "previous_hash": "0" * 64, "immutable_hash": "1" * 64,
             "decision": dict(core), "run_id": ctx["run_id"], "event_id": ctx["event_id"], "context": dict(ctx),
             "decision_digest": subject_digest(beta)}
    return strict_problems(alpha, zeta, beta, delta, chain_verified=True)


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


def GAP_a_decisions_narrative_forged_with_a_valid_fingerprint() -> List[str]:
    """KNOWN GAP, stated as a fact. decision_fingerprint covers 5 of a Decision's 13 fields, so instructions, confidence
    and reasoning can be rewritten and the Decision still validates, records, binds and chains. (A forger who changes
    the verdict, locks or keys must recompute the fingerprint, and beta's fingerprint function is public and keyless.)
    No problem is found. Widening the fingerprint is a native Beta change that has not been made."""
    p = stages(SICK)
    forged = dataclasses.replace(p["decision"], instructions="Send home.", confidence=0.01, reasoning="vitals normal")
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
    (The forger recomputes beta's public, keyless fingerprint.) No problem is found. Recording the partition is a
    native Beta change that has not been made."""
    p = stages(WELL)
    locks, engine = build()
    d = p["decision"]
    forged = dataclasses.replace(
        d, decision="ESCALATE", decision_id="escalate_sepsis", triggered_by_locks=("sepsis_lock",),
        decision_fingerprint=decision_fingerprint({
            "entity_id": d.entity_id, "decision_id": "escalate_sepsis", "decision": "ESCALATE",
            "triggered_by_locks": ["sepsis_lock"], "triggered_by_keys": list(d.triggered_by_keys)}))
    ledger = DecisionLedger(require_context=True)
    entry = ledger.append(forged, context=CTX)
    p.update(ledger=ledger, checkpoint=ledger.checkpoint())
    p["beta"] = beta_cns.decision_content(
        forged, context=CTX, keyset_digest=p["da"], lock_result_digests=p["beta"]["lock_result_digests"])
    p["delta"] = delta_cns.entry_content(entry, context=CTX, decision_digest=subject_digest(p["beta"]))
    return check(p)


class StrSub(str):
    """A str subclass. A context built from one is refused everywhere: a subclass can lie about equality, hash or text."""


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
#: Per scenario: (name, how to run it, what it must produce). A plain string is the older, looser form (see spine_oracle).
SCENARIOS: List[Tuple[str, Callable[[], List[str]], Expectation]] = [
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
                           "delta's entry was recorded under run_id 'run_2' but the run is 'run_1'", CHAIN_NOT_SHOWN))),
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
     Expect("problems", required=("the Decision delta recorded differs from beta's in:",), allowed_extra=(CHAIN_NOT_SHOWN,))),
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
     Expect("problems", required=("delta carries no context",), allowed_extra=("delta names no decision_digest",))),
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
                           "beta's Decision lists no newly_triggered_locks"))),
    ("strict: a ledger truncated with its head reset", a_ledger_truncated_with_its_head_reset,
     Expect("problems", required=("the ledger does not match the checkpoint held outside it",))),
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
    # The next four share one problem: CNS has one question for the ledger ("was the chain shown to verify"), so only the
    # scenario itself (and ledger_verified, which compares the whole entry) tells the attacks apart.
    ("strict: delta's content names a hash the ledger never wrote", delta_content_names_a_hash_the_ledger_never_wrote,
     Expect("problems", required=(CHAIN_NOT_SHOWN,))),
    ("strict: delta content of another Decision under the ledger's hashes", delta_content_of_another_decision_under_the_ledgers_hashes,
     Expect("problems", required=(CHAIN_NOT_SHOWN,))),
    ("strict: the ledger chain is broken after the run", the_ledger_chain_is_broken_after_the_run,
     Expect("problems", required=(CHAIN_NOT_SHOWN,))),
    ("strict: nobody asked delta whether the chain verifies", nobody_asked_delta_whether_the_chain_verifies,
     Expect("problems", required=(CHAIN_NOT_SHOWN,))),
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
    ("strict: GAP, a Decision's narrative forged under a valid fingerprint", GAP_a_decisions_narrative_forged_with_a_valid_fingerprint, GAP),
    ("strict: GAP, a Decision cites a lock that is closed", GAP_a_decision_cites_a_lock_that_is_closed, GAP),
    ("strict: GAP, contents fabricated by someone who recomputes the digests",
     GAP_contents_fabricated_by_someone_who_recomputes_the_digests, GAP),
]


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

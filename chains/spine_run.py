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
replay, a repeat, a truncated ledger, a missing context, a fabricated run) and state the problem the boundary that
should refuse each one must name. A scenario passes when one of its problems contains that text, so an extra,
unrelated problem does not fail it. Two scenarios, marked GAP, record what the strict check does NOT catch as facts
that expect no problem: they go red the day the gap closes and are then updated on purpose.
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Tuple

import alpha.cns_connector as alpha_cns
import beta.cns_connector as beta_cns
import delta.cns_connector as delta_cns
import delta.context as delta_context
import zeta.cns_connector as zeta_cns
from alpha import VitalsObservation, observe
from beta import Decision, DecisionEngine, DecisionRule, DecisionRuleRegistry, StaleLockResultError
from cns.gate import subject_digest
from cns_composition.spine_trace import (
    CONTEXT_SCHEMA, SpineRecord, context_problems, problems, root, strict_problems, strict_root)
from delta import DecisionLedger, DuplicateRecordError
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
    well = observe(WELL)  # another decision, made from keys and lock results that belong together
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
    ledger = DecisionLedger()
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
            "decision": decision, "keys": keys, "results": results, "da": da}


def check(parts) -> List[str]:
    return strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])


def refused(thunk: Callable[[], Any]) -> List[str]:
    """What a boundary refused, as a problem string, or nothing if it let the call through."""
    try:
        thunk()
    except (ValueError, TypeError, StaleLockResultError) as exc:
        return [f"{type(exc).__name__}: {exc}"]
    return []


def strict_clean(vitals) -> List[str]:
    return check(stages(vitals))


def strict_roots_differ_by_run() -> List[str]:
    a, b = stages(SICK), stages(SICK, ctx={**CTX, "run_id": "run_2"})
    ra, rb = (strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"]) for p in (a, b))
    return [] if ra != rb else ["the same readings in two runs produced one root"]


def strict_root_is_not_a_lenient_root() -> List[str]:
    p = stages(SICK)
    strict = strict_root(p["alpha"], p["zeta"], p["beta"], p["delta"])
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
    """Beta's content names the well patient's lock results; zeta's contents and the KeySet are the sick patient's.

    Beta itself now refuses to decide over lock results evaluated from another KeySet (see
    `beta_refuses_lock_results_from_another_keyset`), so the content is edited here, as a beta that did not refuse
    would have produced it: the trace must still name it, because it cannot know what beta refused."""
    locks, _ = build()
    well_results = LockEvaluator(locks).evaluate_all("patient_1", observe(WELL), T0)
    p = stages(SICK)
    p["beta"] = {**p["beta"], "lock_result_digests": {
        lid: zeta_cns.lock_result_digest(r, context=CTX, keyset_digest=p["da"]) for lid, r in well_results.items()}}
    return check(p)


def beta_refuses_lock_results_from_another_keyset() -> List[str]:
    """The stage's own boundary: the problem the refusal names, or nothing if beta let it through."""
    locks, _ = build()
    well_results = LockEvaluator(locks).evaluate_all("patient_1", observe(WELL), T0)
    try:
        stages(SICK, results_from=well_results)
    except Exception as exc:  # only beta's own refusal counts; anything else is a defect in this script
        if type(exc).__name__ != "KeySetMismatchError":
            raise
        return [f"{type(exc).__name__}: {exc}"]
    return []


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
    return refused(lambda: DecisionLedger().append(bad, context=CTX))


def stale_replay_is_refused_by_beta() -> List[str]:
    locks, engine = build()
    ev = LockEvaluator(locks)
    ev.evaluate_all("patient_1", observe(WELL), T0)
    stale = ev.evaluate_all("patient_1", observe(SICK), T0 - timedelta(hours=2))
    return refused(lambda: engine.decide("patient_1", observe(SICK), stale, T0))


def the_same_decision_is_recorded_twice_in_one_run() -> List[str]:
    p = stages(SICK)
    try:
        p["ledger"].append(p["decision"], context=CTX)
    except DuplicateRecordError as exc:
        return [f"DuplicateRecordError: {exc}"]
    return []


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


def GAP_zeta_and_beta_named_the_digest_of_another_keyset() -> List[str]:
    """KNOWN GAP, stated as a fact. Zeta and beta evaluated and decided on one set of readings and were bound with the
    digest of a different KeySet that lists the same present Keys. Neither sees the other's KeySet, so keyset_digest is
    asserted by whoever binds the result, and the strict check verifies that the supplied contents agree, not where they
    came from. No problem is found. The day zeta records the KeySet it evaluated, this goes red and is updated on purpose."""
    p = stages(SICK, bind_keyset_of=SICK_ELSEWHERE)
    p["alpha"] = alpha_cns.keyset_content(observe(SICK_ELSEWHERE), context=CTX)
    return check(p)


def GAP_contents_fabricated_by_someone_who_recomputes_the_digests() -> List[str]:
    """KNOWN GAP, stated as a fact. There is no key in this check: four contents that agree with each other and chain by
    digest pass whether or not any component produced them. It verifies agreement, not authorship. No problem is found."""
    ctx = dict(CTX)
    alpha = {"min_confidence": 0.0, "keys": [{"name": "anything", "present": True, "confidence": 1.0, "reason": "made up"}],
             "context": dict(ctx), "present_names": ["anything"]}
    da = subject_digest(alpha)
    zeta = {"any_lock": {"entity_id": "patient_1", "lock_id": "any_lock", "open": True, "changed": True, "forced": False,
                         "reasons": ["made up"], "context": dict(ctx), "keyset_digest": da}}
    core = {"entity_id": "patient_1", "decision_id": "d", "decision": "DISCHARGE_SAFE", "timestamp": "2026-10-01T08:00:00",
            "confidence": 1.0, "triggered_by_locks": ["any_lock"], "triggered_by_keys": ["anything"],
            "newly_triggered_locks": [], "decision_fingerprint": "0" * 64, "reasoning": "made up",
            "reversal_conditions": [], "instructions": "made up"}
    beta = {**core, "context": dict(ctx), "keyset_digest": da,
            "lock_result_digests": {k: subject_digest(v) for k, v in zeta.items()}}
    delta = {"audit_id": "0" * 16, "timestamp": "2026-10-01T08:00:00", "previous_hash": "0" * 64, "immutable_hash": "1" * 64,
             "decision": dict(core), "run_id": ctx["run_id"], "event_id": ctx["event_id"], "context": dict(ctx),
             "decision_digest": subject_digest(beta)}
    return check({"alpha": alpha, "zeta": zeta, "beta": beta, "delta": delta})


CONTEXT_CASES: List[Any] = [
    dict(CTX), {k: v for k, v in CTX.items() if k != "run_id"}, {**CTX, "extra": "x"}, {**CTX, "run_id": ""},
    {**CTX, "event_id": 4}, {**CTX, "schema": "spine-context/2"}, {**CTX, "entity_id": None}, "run_1", None, [], {},
]


def connectors_agree_with_cns_on_what_a_context_is() -> List[str]:
    """Four repositories each validate their own copy of the context. CNS states the contract; they must agree with it."""
    out: List[str] = []
    checks = {"alpha": alpha_cns._context, "zeta": zeta_cns._context, "beta": beta_cns._context,
              "delta": delta_context.check_context}
    for case in CONTEXT_CASES:
        cns_accepts = not context_problems(case)
        for name, validate in checks.items():
            try:
                validate(case)
                accepts = True
            except (ValueError, TypeError):
                accepts = False
            if accepts != cns_accepts:
                out.append(f"{name} {'accepts' if accepts else 'refuses'} {case!r} and CNS {'accepts' if cns_accepts else 'refuses'} it")
    return out


#: (name, how to run it, text every problem must contain, or "" if there must be none)
SCENARIOS: List[Tuple[str, Callable[[], List[str]], str]] = [
    ("a sick patient, end to end", lambda: clean(SICK), ""),
    ("a well patient, end to end", lambda: clean(WELL), ""),
    ("different runs have different roots", two_runs_have_different_roots, ""),
    ("the Decision cites a Key alpha never detected", cites_a_key_alpha_never_saw, "did not detect as present: ghost_key"),
    ("the Decision cites a Lock zeta never evaluated", cites_a_lock_zeta_never_evaluated, "never evaluated: invented_lock"),
    ("the ledger recorded a different Decision", ledger_recorded_another_decision, "drifted apart"),
    ("the entity differs between the run and the Decision", wrong_entity, "the Decision is about 'patient_1'"),
    # --- strict ---
    ("strict: a sick patient, end to end", lambda: strict_clean(SICK), ""),
    ("strict: a well patient, end to end", lambda: strict_clean(WELL), ""),
    ("strict: the same readings in two runs have different roots", strict_roots_differ_by_run, ""),
    ("strict: a strict root is never a lenient root", strict_root_is_not_a_lenient_root, ""),
    ("strict: the four connectors agree with CNS on the context", connectors_agree_with_cns_on_what_a_context_is, ""),
    ("strict: zeta's results are bound to another subject", subject_substituted_between_alpha_and_zeta,
     "is bound to a different run: entity_id 'patient_2' vs 'patient_1'"),
    ("strict: beta's Decision is bound to another event", event_substituted_between_zeta_and_beta,
     "beta is bound to a different run: event_id 'event_2' vs 'event_1'"),
    ("strict: alpha and zeta from one run, beta and delta from another", alpha_and_zeta_from_one_run_beta_and_delta_from_another,
     "is bound to a different run: run_id 'run_2' vs 'run_1'"),
    ("strict: the KeySet is altered after zeta evaluated it", keyset_altered_after_zeta_evaluated_it,
     "was evaluated from a different KeySet than alpha produced"),
    ("strict: a lock result is altered after beta decided on it", lock_result_altered_after_beta_decided_on_it,
     "rests on a different lock result than zeta produced for sepsis_lock"),
    ("strict: the Decision is altered after delta recorded it", decision_altered_after_delta_recorded_it,
     "delta recorded a Decision other than the one beta produced"),
    ("strict: beta decided from another lock state's results", beta_decided_from_another_lock_result,
     "rests on a different lock result than zeta produced"),
    ("strict: beta refuses to decide over lock results from another KeySet", beta_refuses_lock_results_from_another_keyset,
     "evaluated from a different KeySet than the one given"),
    ("strict: delta recorded another Decision, quoting beta's digest", delta_recorded_another_decision,
     "the Decision delta recorded differs from beta's in:"),
    ("strict: beta refuses a Decision whose basis contradicts its keys", contradictory_basis_is_refused_by_beta,
     "confidence_basis is 'absence' but triggered_by_keys implies 'keys'"),
    ("strict: delta refuses a contradictory Decision that skipped construction",
     contradictory_basis_that_skips_construction_is_refused_by_delta, "triggered_by_keys implies 'keys'"),
    ("strict: beta refuses to decide from a stale replay", stale_replay_is_refused_by_beta,
     "zeta refused the observation behind lock result(s) as stale"),
    ("strict: the same Decision recorded twice in one run", the_same_decision_is_recorded_twice_in_one_run,
     "already recorded a Decision"),
    ("strict: a stage carries no context", a_stage_carries_no_context, "delta carries no context"),
    ("strict: a run fabricated with digests that do not chain", a_run_fabricated_with_digests_that_do_not_chain,
     "evaluated from a different KeySet"),
    ("strict: a ledger truncated with its head reset", a_ledger_truncated_with_its_head_reset,
     "does not match the checkpoint held outside it"),
    ("strict: a lock result zeta refused as stale is rested on", a_stale_lock_result_is_rested_on, "was refused as stale"),
    ("strict: a lock result is filed under another lock's id", a_lock_result_filed_under_another_locks_id,
     "carries lock_id 'abnormal_vitals_lock'"),
    ("strict: alpha lists a present key its own keys do not hold", alpha_lists_a_key_it_does_not_hold_as_present,
     "alpha lists present_names that its own keys do not hold as present: invented_key"),
    ("strict: GAP, zeta and beta named the digest of another KeySet", GAP_zeta_and_beta_named_the_digest_of_another_keyset, ""),
    ("strict: GAP, contents fabricated by someone who recomputes the digests",
     GAP_contents_fabricated_by_someone_who_recomputes_the_digests, ""),
]


def main() -> int:
    wrong: List[str] = []
    for name, scenario, expect in SCENARIOS:
        found = scenario()
        ok = (not found) if not expect else any(expect in p for p in found)
        print(f"{'ok  ' if ok else 'FAIL'} {name:52} -> {'no problems' if not found else str(len(found)) + ' named'}")
        if not ok:
            wrong.append(f"{name}: wanted {'no problems' if not expect else expect!r}, got {found}")
    for line in wrong:
        print(f"spine: {line}", file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The decision spine, run for real, then checked at its seams.

alpha detects Keys from vitals, zeta evaluates Locks over them, beta turns lock states into a Decision, delta
records the Decision in a hash-chained ledger. Each repository binds its own output with its optional CNS
connector. `cns_composition.spine_trace` checks that the four stages describe one run: the Decision cites only
Keys that were detected and Locks that were evaluated, belongs to the entity the run was about, and beta's digest of the
Decision equals delta's digest of the Decision it recorded.

Every scenario states what it must produce and the script exits 1 if any differs. Run in the `chains` workflow
against the four repositories' default branches, so it fails the day one of them drifts from the others.
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime
from typing import Callable, List, Tuple

import alpha.cns_connector as alpha_cns
import beta.cns_connector as beta_cns
import delta.cns_connector as delta_cns
import zeta.cns_connector as zeta_cns
from alpha import VitalsObservation, observe
from beta import DecisionEngine, DecisionRule, DecisionRuleRegistry
from cns.gate import subject_digest
from cns_composition.spine_trace import SpineRecord, problems, root
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
    other = engine.decide("patient_1", observe(WELL), results, T0)
    return problems(facts(keys, results, decision, ledger.append(other)))


def wrong_entity() -> List[str]:
    _, _, keys, results, decision, entry = run()
    return problems(facts(keys, results, decision, entry, entity="patient_2"))


def two_runs_have_different_roots() -> List[str]:
    a, b = run(SICK), run(WELL)
    ra, rb = root(facts(a[2], a[3], a[4], a[5])), root(facts(b[2], b[3], b[4], b[5]))
    return [] if ra != rb else ["two different runs produced the same root"]


#: (name, how to run it, text every problem must contain, or "" if there must be none)
SCENARIOS: List[Tuple[str, Callable[[], List[str]], str]] = [
    ("a sick patient, end to end", lambda: clean(SICK), ""),
    ("a well patient, end to end", lambda: clean(WELL), ""),
    ("different runs have different roots", two_runs_have_different_roots, ""),
    ("the Decision cites a Key alpha never detected", cites_a_key_alpha_never_saw, "did not detect as present: ghost_key"),
    ("the Decision cites a Lock zeta never evaluated", cites_a_lock_zeta_never_evaluated, "never evaluated: invented_lock"),
    ("the ledger recorded a different Decision", ledger_recorded_another_decision, "drifted apart"),
    ("the entity differs between the run and the Decision", wrong_entity, "the Decision is about 'patient_1'"),
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

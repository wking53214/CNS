"""strict spine verification: the four stages' actual contents, not a caller's account of them.

`problems` (the lenient check) takes digests and summaries the caller read off the objects. A caller can hand it
a mutually consistent set that describes nothing, and it issues a root. The strict check takes each stage's
content mapping (the plain dict its connector produces), recomputes every digest itself, and requires that every
stage names the same entity, event and run and that each stage's lineage digest is the digest of the stage
before it. Every property below was shown to fail on the lenient check before this existed.
"""

import copy
from typing import Any, Dict

import pytest
from cns.gate import subject_digest

from cns_composition.spine_trace import (
    CONTEXT_SCHEMA, TRACE_SCHEMA, context_problems, strict_problems, strict_root)

CTX = {"schema": CONTEXT_SCHEMA, "entity_id": "p1", "event_id": "ev-1", "run_id": "run-1"}
DECISION_ONLY = ("entity_id", "decision_id", "decision", "timestamp", "confidence", "triggered_by_locks",
                 "triggered_by_keys", "newly_triggered_locks", "decision_fingerprint", "reasoning",
                 "reversal_conditions", "instructions")


def build(ctx=CTX, **over) -> Dict[str, Any]:
    """Four contents shaped exactly as the connectors produce them, consistent with each other."""
    alpha = {
        "min_confidence": 0.0,
        "keys": [{"name": "septic_shock", "present": True, "confidence": 1.0, "reason": "r"},
                 {"name": "fever", "present": False, "confidence": 1.0, "reason": "r"}],
        "context": dict(ctx), "present_names": ["septic_shock"],
    }
    da = subject_digest(alpha)
    zeta = {}
    for lock, is_open in (("sepsis_lock", True), ("abnormal_vitals_lock", False)):
        zeta[lock] = {"entity_id": ctx["entity_id"], "lock_id": lock, "open": is_open, "changed": True, "forced": False,
                      "reasons": ["x"], "context": dict(ctx), "keyset_digest": da}
    core = {"entity_id": ctx["entity_id"], "decision_id": "escalate", "decision": "ESCALATE",
            "timestamp": "2026-01-01T12:00:00", "confidence": 0.9, "triggered_by_locks": ["sepsis_lock"],
            "triggered_by_keys": ["septic_shock"], "newly_triggered_locks": ["sepsis_lock"],
            "decision_fingerprint": "f" * 64, "reasoning": "r", "reversal_conditions": [], "instructions": "i"}
    beta = {**core, "context": dict(ctx), "keyset_digest": da,
            "lock_result_digests": {k: subject_digest(v) for k, v in sorted(zeta.items())}}
    delta = {"audit_id": "a" * 16, "timestamp": "2026-01-01T12:00:00", "previous_hash": "p" * 64,
             "immutable_hash": "h" * 64, "decision": dict(core), "run_id": ctx["run_id"], "event_id": ctx["event_id"],
             "context": dict(ctx), "decision_digest": subject_digest(beta)}
    out = {"alpha": alpha, "zeta": zeta, "beta": beta, "delta": delta}
    out.update(over)
    return out


def problems_of(parts) -> list:
    return strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])


def relink(parts, *, keep_decision_digest=False):
    """Recompute the lineage after an edit, so the edit is the only thing wrong."""
    da = subject_digest(parts["alpha"])
    for c in parts["zeta"].values():
        c["keyset_digest"] = da
    parts["beta"]["keyset_digest"] = da
    parts["beta"]["lock_result_digests"] = {k: subject_digest(v) for k, v in sorted(parts["zeta"].items())}
    if not keep_decision_digest:
        parts["delta"]["decision_digest"] = subject_digest(parts["beta"])
    return parts


def has(found, text):
    assert any(text in p for p in found), found


# --- a consistent run -------------------------------------------------------------------------------------------

def test_a_consistent_run_has_no_problems_and_a_root():
    parts = build()
    assert problems_of(parts) == []
    assert len(strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])) == 64


def test_the_root_is_stable_and_ignores_the_order_locks_were_listed_in():
    a = build()
    b = build()
    b["zeta"] = dict(reversed(list(b["zeta"].items())))
    args = lambda p: (p["alpha"], p["zeta"], p["beta"], p["delta"])  # noqa: E731
    assert strict_root(*args(a)) == strict_root(*args(b)) == strict_root(*args(build()))


def test_the_root_changes_when_any_stage_changes_and_is_not_a_lenient_root():
    base = build()
    root = strict_root(base["alpha"], base["zeta"], base["beta"], base["delta"])
    other = relink(build())
    other["alpha"]["keys"][0]["reason"] = "a different reading"
    relink(other)
    assert strict_root(other["alpha"], other["zeta"], other["beta"], other["delta"]) != root
    assert TRACE_SCHEMA == "spine-trace/2"


# --- identity: subject, event, run ------------------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["alpha", "beta", "delta"])
@pytest.mark.parametrize("field, value", [("entity_id", "p2"), ("event_id", "ev-2"), ("run_id", "run-2")])
def test_a_stage_bound_to_another_subject_event_or_run_is_named(stage, field, value):
    parts = build()
    parts[stage]["context"][field] = value
    if stage == "delta" and field in ("event_id", "run_id"):
        parts[stage][field] = value  # the entry is consistent with its own context, only the run is wrong
    has(problems_of(parts), f"{stage} is bound to a different run")
    with pytest.raises(ValueError, match="does not hold together"):
        strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"])


@pytest.mark.parametrize("field, value", [("entity_id", "p2"), ("event_id", "ev-2"), ("run_id", "run-2")])
def test_a_zeta_lock_from_another_subject_event_or_run_is_named(field, value):
    parts = build()
    parts["zeta"]["sepsis_lock"]["context"][field] = value
    has(problems_of(parts), "zeta lock sepsis_lock is bound to a different run")


def test_a_zeta_lock_whose_own_entity_field_disagrees_with_its_context_is_named():
    parts = build()
    parts["zeta"]["sepsis_lock"]["entity_id"] = "p2"
    has(problems_of(parts), "zeta lock sepsis_lock records entity 'p2' but the run is about 'p1'")


def test_a_decision_about_another_entity_than_the_run_is_named():
    parts = build()
    parts["beta"]["entity_id"] = "p2"
    relink(parts)
    has(problems_of(parts), "beta's Decision is about 'p2' but the run is about 'p1'")


def test_the_whole_run_replayed_under_another_run_id_is_a_different_run_not_a_valid_copy():
    replay = build(ctx={**CTX, "run_id": "run-2"})
    assert problems_of(replay) == []  # internally consistent
    a, b = build(), replay
    assert strict_root(a["alpha"], a["zeta"], a["beta"], a["delta"]) != strict_root(b["alpha"], b["zeta"], b["beta"], b["delta"])


def test_stages_taken_from_two_different_runs_are_refused_even_though_each_is_consistent():
    run1, run2 = build(), build(ctx={**CTX, "run_id": "run-2"})
    mixed = {**run1, "beta": run2["beta"], "delta": run2["delta"]}
    found = problems_of(mixed)
    has(found, "beta is bound to a different run")
    has(found, "beta's Decision was made from a different KeySet")


# --- lineage: the digest of the stage before ---------------------------------------------------------------------

def test_a_keyset_altered_after_zeta_evaluated_it_is_named_even_if_every_summary_is_unchanged():
    parts = build()
    parts["alpha"]["keys"][0]["confidence"] = 0.5  # altered; zeta's and beta's keyset_digest still name the old one
    found = problems_of(parts)
    has(found, "zeta lock sepsis_lock was evaluated from a different KeySet than alpha produced")
    has(found, "beta's Decision was made from a different KeySet than alpha produced")


def test_a_lock_result_altered_after_beta_decided_on_it_is_named():
    parts = build()
    parts["zeta"]["sepsis_lock"]["reasons"] = ["altered"]
    has(problems_of(parts), "beta's Decision rests on a different lock result than zeta produced for sepsis_lock")


def test_a_decision_altered_after_delta_recorded_it_is_named():
    parts = build()
    parts["beta"]["instructions"] = "do something else"
    has(problems_of(parts), "delta recorded a Decision other than the one beta produced")


def test_a_ledger_entry_whose_embedded_decision_has_drifted_names_the_fields():
    parts = build()
    parts["delta"]["decision"]["reasoning"] = "rewritten"
    has(problems_of(parts), "the Decision delta recorded differs from beta's in: reasoning")


def test_a_lock_result_beta_did_not_digest_or_that_zeta_did_not_produce_is_named():
    parts = build()
    parts["beta"]["lock_result_digests"]["ghost_lock"] = subject_digest({"x": 1})
    has(problems_of(parts), "beta's Decision names lock result(s) zeta did not produce: ghost_lock")
    parts = build()
    del parts["beta"]["lock_result_digests"]["abnormal_vitals_lock"]
    has(problems_of(parts), "beta's Decision does not digest zeta's lock result(s): abnormal_vitals_lock")


# --- what the Decision cites -----------------------------------------------------------------------------------

def test_a_decision_citing_a_key_alpha_did_not_report_present_is_named():
    parts = build()
    parts["beta"]["triggered_by_keys"] = ["septic_shock", "ghost_key"]
    parts["delta"]["decision"]["triggered_by_keys"] = ["septic_shock", "ghost_key"]
    relink(parts)
    has(problems_of(parts), "the Decision cites key(s) alpha did not list as present: ghost_key")


def test_a_decision_citing_a_lock_zeta_never_evaluated_is_named():
    parts = build()
    parts["beta"]["triggered_by_locks"] = ["sepsis_lock", "invented_lock"]
    parts["delta"]["decision"]["triggered_by_locks"] = ["sepsis_lock", "invented_lock"]
    relink(parts)
    has(problems_of(parts), "the Decision cites lock(s) zeta never evaluated: invented_lock")


def test_alpha_content_without_present_names_is_refused_not_guessed_from_the_keys():
    parts = build()
    del parts["alpha"]["present_names"]
    relink(parts)
    has(problems_of(parts), "alpha lists no present_names")


# --- the ledger entry ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["run_id", "event_id"])
def test_an_entry_recorded_under_another_run_or_event_than_the_context_is_named(field):
    parts = build()
    parts["delta"][field] = "other"
    has(problems_of(parts), f"delta's entry was recorded under {field} 'other' but the run is")


def test_an_entry_that_records_no_run_is_named():
    parts = build()
    del parts["delta"]["run_id"]
    has(problems_of(parts), "delta's entry records no run_id")


# --- missing, malformed, fabricated ----------------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["alpha", "beta", "delta"])
def test_a_stage_with_no_context_is_refused_not_skipped(stage):
    parts = build()
    del parts[stage]["context"]
    has(problems_of(parts), f"{stage} carries no context")


def test_a_zeta_lock_with_no_context_or_no_keyset_digest_is_refused():
    parts = build()
    del parts["zeta"]["sepsis_lock"]["context"]
    has(problems_of(parts), "zeta lock sepsis_lock carries no context")
    parts = build()
    del parts["zeta"]["sepsis_lock"]["keyset_digest"]
    has(problems_of(parts), "zeta lock sepsis_lock names no keyset_digest")


@pytest.mark.parametrize("bad, text", [
    ({k: v for k, v in CTX.items() if k != "run_id"}, "exactly the fields"),
    ({**CTX, "extra": "x"}, "exactly the fields"),
    ({**CTX, "run_id": ""}, "non-empty"),
    ({**CTX, "run_id": 3}, "must be a str"),
    ({**CTX, "schema": "spine-context/9"}, "unsupported schema"),
    ("not a mapping", "must be a mapping"),
])
def test_a_malformed_context_is_named_by_context_problems_and_by_the_run_check(bad, text):
    has(context_problems(bad), text)
    parts = build()
    parts["alpha"]["context"] = bad
    has(problems_of(parts), "alpha context")


def test_a_valid_context_has_no_problems():
    assert context_problems(CTX) == []


def test_a_fabricated_run_with_no_consistent_lineage_is_refused():
    """What the lenient check accepted: four stages stating whatever agrees with itself, no real objects behind it."""
    d = lambda n: subject_digest({"fab": n})  # noqa: E731
    fake = {
        "alpha": {"context": dict(CTX), "present_names": ["anything"], "keys": [], "min_confidence": 0.0},
        "zeta": {"any_lock": {"context": dict(CTX), "entity_id": "p1", "keyset_digest": d(1)}},
        "beta": {"context": dict(CTX), "entity_id": "p1", "triggered_by_keys": ["anything"],
                 "triggered_by_locks": ["any_lock"], "keyset_digest": d(1), "lock_result_digests": {"any_lock": d(2)}},
        "delta": {"context": dict(CTX), "run_id": "run-1", "event_id": "ev-1", "decision_digest": d(3),
                  "decision": {"entity_id": "p1"}},
    }
    found = problems_of(fake)
    assert found
    has(found, "evaluated from a different KeySet")
    with pytest.raises(ValueError):
        strict_root(fake["alpha"], fake["zeta"], fake["beta"], fake["delta"])


@pytest.mark.parametrize("stage", ["alpha", "beta", "delta"])
def test_a_stage_that_is_not_a_mapping_is_named_not_raised(stage):
    parts = build()
    parts[stage] = None
    has(problems_of(parts), f"{stage} content is not a mapping")


def test_zeta_with_no_lock_or_a_non_mapping_lock_is_named():
    parts = build()
    parts["zeta"] = {}
    has(problems_of(parts), "zeta evaluated no lock")
    parts = build()
    parts["zeta"]["sepsis_lock"] = "text"
    has(problems_of(parts), "zeta lock sepsis_lock content is not a mapping")


def test_content_that_cannot_be_digested_is_named_not_raised():
    parts = build()
    parts["alpha"]["keys"] = {1, 2}  # a set is not content subject_digest accepts
    found = problems_of(parts)
    has(found, "alpha content cannot be digested")


def test_inputs_are_not_modified():
    parts = build()
    before = copy.deepcopy(parts)
    problems_of(parts)
    assert parts == before

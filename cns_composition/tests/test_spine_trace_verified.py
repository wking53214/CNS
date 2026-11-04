"""spine_trace.verify: the seam check with the stages' own content in hand.

`problems` takes four small facts and four digests that a caller typed and checks that they agree with each other. A
caller that types forged facts beside genuine digests gets the genuine root, because nothing ties a fact to the digest
next to it. `verify` takes the content each stage digested (the `*_content` function of its own connector), recomputes
every digest from it, and reads the facts off the content. These tests run the attacks that agreement alone cannot see.

What it still cannot see is written as assertions at the end: that a stage consumed its predecessor's real output, and
that a stage's own rules were right, belong to the stages.
"""

import copy
import dataclasses
from typing import Any

import pytest
from cns.gate import subject_digest

from cns_composition.spine_trace import SpineContents, SpineRecord, problems, root, verified_root, verify

ENTITY = "patient_1"


def lock(lock_id, open_, **extra):
    return {"entity_id": ENTITY, "lock_id": lock_id, "open": open_, "changed": False, "forced": False,
            "reasons": [], **extra}


def decision_content(keys=("septic_shock",), locks=("sepsis_lock",), entity=ENTITY, decision="ESCALATE", **extra):
    return {"entity_id": entity, "decision_id": "escalate_sepsis", "decision": decision,
            "timestamp": "2026-10-01T08:00:00", "confidence": 1.0, "triggered_by_locks": sorted(locks),
            "triggered_by_keys": sorted(keys), "newly_triggered_locks": [], "decision_fingerprint": "fp",
            "reasoning": "r", "reversal_conditions": [], "instructions": "go", **extra}


def contents(**over):
    base: dict[str, Any] = dict(
        keyset={"min_confidence": 0.5, "keys": [
            {"name": "fever", "present": True, "confidence": 1.0, "reason": "t"},
            {"name": "septic_shock", "present": True, "confidence": 1.0, "reason": "s"},
            {"name": "calm", "present": False, "confidence": 1.0, "reason": "c"}]},
        lock_results={"sepsis_lock": lock("sepsis_lock", True), "abnormal_vitals_lock": lock("abnormal_vitals_lock", True)},
        decision=decision_content(),
        entry=None,
        ledger_chain_verified=True)
    base.update(over)
    if base["entry"] is None:
        base["entry"] = {"audit_id": "a1", "timestamp": "2026-10-01T08:00:01", "previous_hash": "0" * 64,
                         "immutable_hash": "1" * 64, "decision": copy.deepcopy(base["decision"])}
    return SpineContents(**base)


def record_for(c: SpineContents, **over) -> SpineRecord:
    base: dict[str, Any] = dict(
        entity_id=ENTITY,
        keyset_digest=subject_digest(c.keyset),
        keys_present=tuple(sorted(k["name"] for k in c.keyset["keys"] if k["present"])),
        lock_result_digests={i: subject_digest(x) for i, x in c.lock_results.items()},
        open_locks=tuple(i for i, x in c.lock_results.items() if x["open"]),
        decision_entity_id=c.decision["entity_id"], decision_keys=tuple(c.decision["triggered_by_keys"]),
        decision_locks=tuple(c.decision["triggered_by_locks"]), decision_digest=subject_digest(c.decision),
        ledger_decision_digest=subject_digest(c.entry["decision"]), entry_digest=subject_digest(c.entry))
    base.update(over)
    return SpineRecord(**base)


def found(record, c, **kw):
    return verify(record, c, **kw)


def named(problem_list, text):
    return any(text in p for p in problem_list)


# ----------------------------------------------------------------------------- an honest run has nothing to name

def test_a_run_whose_content_backs_its_record_has_no_problems_and_the_same_root_problems_alone_gives():
    c = contents()
    r = record_for(c)
    assert found(r, c) == [] and problems(r) == []
    assert verified_root(r, c) == root(r), "verifying adds a check and leaves every root as it was"


# ------------------------------------------------- facts typed beside genuine digests are no longer taken on trust

def test_forged_facts_beside_genuine_digests_are_named():
    c = contents()
    forged = record_for(c, keys_present=("fever", "septic_shock", "ghost_key"), decision_keys=("ghost_key",))
    assert problems(forged) == [] and len(root(forged)) == 64, "agreement alone is satisfied by the forgery"
    assert named(found(forged, c), "keys_present is not the keys alpha's content shows present")


def test_a_present_key_is_one_the_keyset_content_says_is_present():
    c = contents()
    r = record_for(c, keys_present=("septic_shock",))
    assert named(found(r, c), "keys alpha's content shows present")


def test_open_locks_are_the_ones_the_lock_content_says_are_open():
    c = contents()
    r = record_for(c, open_locks=("sepsis_lock",))
    assert named(found(r, c), "open locks")


def test_a_digest_that_is_not_the_digest_of_the_content_supplied_is_named_for_each_stage():
    c = contents()
    base = record_for(c)
    for over, stage in (({"keyset_digest": subject_digest({"x": 1})}, "alpha"),
                        ({"decision_digest": subject_digest({"x": 2}), "ledger_decision_digest": subject_digest({"x": 2})},
                         "beta"),
                        ({"entry_digest": subject_digest({"x": 3})}, "delta"),
                        ({"lock_result_digests": {**base.lock_result_digests, "sepsis_lock": subject_digest({"x": 4})}},
                         "zeta lock sepsis_lock")):
        assert named(found(dataclasses.replace(base, **over), c), f"{stage}: the digest is not the digest of the content")


def test_a_digest_taken_from_another_run_with_this_runs_facts_is_named():
    well = contents(keyset={"min_confidence": 0.5, "keys": [{"name": "calm", "present": True, "confidence": 1.0, "reason": "c"}]})
    sick = contents()
    mixed = dataclasses.replace(record_for(sick), keyset_digest=subject_digest(well.keyset))
    assert named(found(mixed, sick), "alpha: the digest is not the digest of the content")


def test_lock_results_swapped_between_ids_are_named():
    c = contents()
    swapped = contents(lock_results={"sepsis_lock": lock("abnormal_vitals_lock", True),
                                     "abnormal_vitals_lock": lock("sepsis_lock", True)})
    assert named(found(record_for(swapped), swapped), "names lock")
    assert found(record_for(c), c) == []


def test_the_digests_of_two_different_stages_may_not_coincide_including_a_lock_digest():
    c = contents()
    r = record_for(c)
    lock_digest = r.lock_result_digests["sepsis_lock"]
    clash = dataclasses.replace(r, keyset_digest=lock_digest)
    assert named(problems(clash), "same digest")
    twin = dataclasses.replace(r, lock_result_digests={"sepsis_lock": lock_digest, "abnormal_vitals_lock": lock_digest})
    assert named(problems(twin), "same digest")


@pytest.mark.parametrize("field", ["keys_present", "open_locks", "decision_keys", "decision_locks"])
def test_a_bare_string_where_names_belong_is_named_and_not_read_as_letters(field):
    c = contents()
    assert named(problems(dataclasses.replace(record_for(c), **{field: "septic_shock"})), "tuple of names")


# ------------------------------------------------------------- the entity belongs to the content, not the caller

def test_a_lock_result_digested_without_an_entity_cannot_be_tied_to_the_run():
    anonymous = contents(lock_results={"sepsis_lock": lock("sepsis_lock", True, entity_id=None),
                                       "abnormal_vitals_lock": lock("abnormal_vitals_lock", True, entity_id=None)})
    assert named(found(record_for(anonymous), anonymous), "digested without an entity")


def test_a_lock_result_for_another_entity_is_named():
    other = contents(lock_results={"sepsis_lock": lock("sepsis_lock", True, entity_id="patient_2"),
                                   "abnormal_vitals_lock": lock("abnormal_vitals_lock", True)})
    assert named(found(record_for(other), other), "patient_2")


def test_a_decision_for_another_entity_than_the_run_is_named_from_the_content():
    c = contents(decision=decision_content(entity="patient_2"))
    assert named(found(record_for(c, decision_entity_id=ENTITY), c), "patient_2")


# ------------------------------------------------ the decision, the ledger entry and the chain are one thing each

def test_a_ledger_entry_that_holds_another_decision_than_the_one_decided_is_named_by_content():
    c = contents()
    other = contents(entry={"audit_id": "a1", "timestamp": "t", "previous_hash": "0" * 64, "immutable_hash": "1" * 64,
                            "decision": decision_content(decision="DISCHARGE_SAFE")})
    r = record_for(other, decision_digest=subject_digest(c.decision))
    assert named(found(r, other), "recorded a different Decision")


def test_a_stage_that_never_ran_has_no_content_and_is_named():
    c = contents()
    r = record_for(c)
    for missing in ({"entry": {}}, {"keyset": {}}, {"decision": {}}, {"lock_results": {}}):
        broken = dataclasses.replace(c, **missing)
        assert found(r, broken), missing


def test_a_ledger_chain_nobody_checked_is_named_and_so_is_one_that_failed():
    c = contents(ledger_chain_verified=False)
    assert named(found(record_for(c), c), "ledger chain")
    unset = SpineContents(keyset=c.keyset, lock_results=c.lock_results, decision=c.decision, entry=c.entry)
    assert named(found(record_for(c), unset), "ledger chain")


def test_a_lock_result_zeta_marked_stale_is_named():
    stale = contents(lock_results={"sepsis_lock": lock("sepsis_lock", False, stale=True),
                                   "abnormal_vitals_lock": lock("abnormal_vitals_lock", False)})
    assert named(found(record_for(stale), stale), "stale")


def test_the_locks_policy_expects_must_all_have_been_evaluated_and_none_invented():
    c = contents()
    r = record_for(c)
    assert found(r, c, expected_locks=("sepsis_lock", "abnormal_vitals_lock")) == []
    assert named(found(r, c, expected_locks=("sepsis_lock", "abnormal_vitals_lock", "perfusion_lock")), "perfusion_lock")
    assert named(found(r, c, expected_locks=("sepsis_lock",)), "abnormal_vitals_lock")


def test_content_that_cannot_be_digested_is_named_and_does_not_raise():
    c = dataclasses.replace(contents(), keyset={"min_confidence": float("nan"), "keys": []})
    assert named(found(record_for(contents()), c), "cannot be digested")


def test_verified_root_refuses_what_verify_names():
    c = contents(ledger_chain_verified=False)
    with pytest.raises(ValueError, match="does not hang together"):
        verified_root(record_for(c), c)


# ------------------------------------------------ what still needs the stages, recorded so it cannot rot

def test_GAP_a_stage_fed_something_other_than_its_predecessors_output_is_not_seen_because_no_content_names_its_input():
    """zeta and beta judged WELL vitals; alpha's content says SICK. Every digest is genuine and the facts agree. Only a
    stage that records the digest of the input it consumed can close this; that is the stage's change."""
    c = contents(lock_results={"sepsis_lock": lock("sepsis_lock", False), "abnormal_vitals_lock": lock("abnormal_vitals_lock", False)},
                 decision=decision_content(keys=(), locks=("sepsis_lock", "abnormal_vitals_lock"), decision="DISCHARGE_SAFE"))
    r = record_for(c)
    assert "septic_shock" in r.keys_present and r.open_locks == ()
    assert found(r, c) == []


def test_GAP_a_decision_that_ignores_the_rule_for_its_locks_is_not_seen_because_the_rule_is_not_in_the_content():
    c = contents(decision=decision_content(keys=(), locks=("sepsis_lock",), decision="DISCHARGE_SAFE"))
    assert found(record_for(c), c) == []

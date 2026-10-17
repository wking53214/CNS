"""spine_trace: the four stages of the decision spine must describe one run."""

import dataclasses

import pytest
from cns.gate import subject_digest

from cns_composition.spine_trace import SPINE, SpineRecord, problems, root


def d(label: str) -> str:
    return subject_digest({"label": label})


def record(**over) -> SpineRecord:
    base = dict(
        entity_id="patient_1",
        keyset_digest=d("keys"), keys_present=("fever", "septic_shock", "tachycardia"),
        lock_result_digests={"sepsis_lock": d("sepsis"), "abnormal_vitals_lock": d("abnormal")},
        open_locks=("sepsis_lock", "abnormal_vitals_lock"),
        decision_entity_id="patient_1", decision_keys=("septic_shock",), decision_locks=("sepsis_lock",),
        decision_digest=d("decision"), ledger_decision_digest=d("decision"), entry_digest=d("entry"),
    )
    base.update(over)
    return SpineRecord(**base)


def test_the_spine_names_its_four_repositories_in_run_order():
    assert list(SPINE) == ["interconnected_alpha", "interconnected_zeta", "interconnected_beta", "interconnected_delta"]
    assert list(SPINE.values()) == ["alpha", "zeta", "beta", "delta"]


def test_a_run_whose_stages_agree_has_no_problems_and_a_root():
    r = record()
    assert problems(r) == [] and len(root(r)) == 64


@pytest.mark.parametrize("over, expect", [
    ({"decision_keys": ("septic_shock", "ghost_key")}, "key(s) alpha did not detect as present: ghost_key"),
    ({"decision_locks": ("sepsis_lock", "invented_lock")}, "lock(s) zeta did not report open: invented_lock"),
    ({"decision_locks": ("sepsis_lock",), "open_locks": ("abnormal_vitals_lock",)}, "did not report open: sepsis_lock"),
    ({"decision_entity_id": "patient_2"}, "the Decision is about 'patient_2'"),
    ({"entity_id": ""}, "the run is about ''"),
    ({"ledger_decision_digest": d("another decision")}, "drifted apart"),
    ({"open_locks": ("sepsis_lock", "unevaluated_lock")}, "no result for: unevaluated_lock"),
    ({"lock_result_digests": {}}, "evaluated no lock"),
    ({"keyset_digest": "abc"}, "alpha keyset digest is not a full SHA-256"),
    ({"entry_digest": d("keys")}, "same digest"),
    ({"lock_result_digests": {"sepsis_lock": "short", "abnormal_vitals_lock": d("abnormal")}}, "zeta lock sepsis_lock digest"),
])
def test_each_seam_that_does_not_hold_is_named(over, expect):
    found = problems(record(**over))
    assert any(expect in p for p in found), found


def test_root_refuses_a_run_that_does_not_hang_together():
    with pytest.raises(ValueError, match="does not hang together"):
        root(record(decision_keys=("ghost_key",)))


def test_root_changes_when_any_stage_changes():
    base = root(record())
    for over in ({"keyset_digest": d("other keys")}, {"entry_digest": d("other entry")},
                 {"lock_result_digests": {"sepsis_lock": d("x"), "abnormal_vitals_lock": d("abnormal")}},
                 {"entity_id": "patient_9", "decision_entity_id": "patient_9"}):
        assert root(record(**over)) != base


def test_root_ignores_the_order_the_locks_were_listed_in():
    a = record(lock_result_digests={"a": d("1"), "b": d("2")}, open_locks=("a",), decision_locks=("a",))
    b = record(lock_result_digests={"b": d("2"), "a": d("1")}, open_locks=("a",), decision_locks=("a",))
    assert root(a) == root(b)


def test_a_record_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        record().entity_id = "x"  # type: ignore[misc]

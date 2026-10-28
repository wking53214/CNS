"""cns.run: the run record contract. Readers rely on exactly what is named here."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cns.run import RunRecord


def _good(**over: object) -> dict:
    base = {
        "schema": "cns.run/1", "contract": "1", "decision": "ACCEPT_UNVERIFIED", "reason": "held",
        "converged": True, "finished": True, "put_back": True, "held_digest": "ab" * 32,
        "unmeasured": ["ghost_partial"], "notes": ["one note"], "observed": ["ghost-1"],
        "verdict": {"decision": "INSUFFICIENT", "reasons": ["some tests did not run"]},
        "ghost_scan": {"status": "incomplete", "gaps": ["boundary"]},
        "versions": {"warden": {"version": "0.11.3"}}, "cycles": [{"number": 1}],
    }
    base.update(over)
    return base


def test_a_good_record_reads_and_keeps_its_named_fields():
    r = RunRecord.from_dict(_good())
    assert r.decision == "ACCEPT_UNVERIFIED" and r.unmeasured == ("ghost_partial",)
    assert r.verdict["decision"] == "INSUFFICIENT" and r.versions["warden"]["version"] == "0.11.3"
    assert r.problems() == ()


def test_extra_keys_are_allowed_and_ignored():
    r = RunRecord.from_dict(_good(cycles=[], brand_new_field="anything"))
    assert not hasattr(r, "cycles") and r.decision == "ACCEPT_UNVERIFIED"


def test_a_record_without_the_schema_is_refused_with_the_reason():
    data = _good()
    del data["schema"]
    with pytest.raises(ValueError, match="missing schema"):
        RunRecord.from_dict(data)
    with pytest.raises(ValueError, match="predates the contract"):
        RunRecord.from_dict(_good(schema="cns.run/0"))


@pytest.mark.parametrize("key", ["contract", "decision", "reason", "converged", "finished", "put_back"])
def test_each_required_field_is_required(key):
    data = _good()
    del data[key]
    with pytest.raises(ValueError, match=f"missing {key}"):
        RunRecord.from_dict(data)


def test_an_unknown_decision_is_refused():
    with pytest.raises(ValueError, match="not one Warden ends a run with"):
        RunRecord.from_dict(_good(decision="PROBABLY_FINE"))


def test_flags_must_be_true_or_false_not_truthy_text():
    with pytest.raises(ValueError, match="converged is str"):
        RunRecord.from_dict(_good(converged="yes"))


def test_lists_must_be_lists_of_text():
    with pytest.raises(ValueError, match="unmeasured is str, not a list"):
        RunRecord.from_dict(_good(unmeasured="ghost_partial"))
    with pytest.raises(ValueError, match="not text"):
        RunRecord.from_dict(_good(notes=["ok", 3]))


def test_verdict_and_versions_must_be_objects_when_present():
    with pytest.raises(ValueError, match="verdict is list, not an object"):
        RunRecord.from_dict(_good(verdict=["INSUFFICIENT"]))
    with pytest.raises(ValueError, match="versions is str, not an object"):
        RunRecord.from_dict(_good(versions="0.11.3"))


def test_problems_names_an_empty_contract_and_is_pure():
    r = RunRecord(schema="cns.run/1", contract="  ", decision="ACCEPT", reason="", converged=True,
                  finished=True, put_back=False)
    assert r.problems() == ("contract is empty",)
    assert r.problems() == r.problems()


def test_the_module_holds_no_state_and_reads_no_file():
    text = (Path(__file__).resolve().parents[1] / "cns" / "run.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assigned = [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                for t in ([n.target] if isinstance(n, ast.AnnAssign) else n.targets) if isinstance(t, ast.Name)]
    assert all(name.startswith("__") and name.endswith("__") for name in assigned), assigned
    assert "open(" not in text and "import json" not in text and "pathlib" not in text


def test_a_null_reason_is_refused_not_read_as_the_word_none():
    with pytest.raises(ValueError, match="reason is missing or null, not text"):
        RunRecord.from_dict(_good(reason=None))
    with pytest.raises(ValueError, match="decision is int, not text"):
        RunRecord.from_dict(_good(decision=3))


# ---------------------------------------------------------------------------------------------------------------
# 2.0.0: what a reader can say about a run beyond its named fields. The first fixture is a real record (Warden
# 0.13.6, kept by WATCHER_MCU as tests/fixtures/warden_0_13_6_declined_record.json): unmeasured is empty, converged
# is true, and seven checks were declined. A narrator that read only the named fields said "gaps: none" of it.
# ---------------------------------------------------------------------------------------------------------------

FIXTURE = Path(__file__).with_name("fixtures") / "warden_0_13_6_declined_record.json"
DECLINED = ("mutate", "kernel", "structure", "tests", "project", "secrets", "correlate")


def _real() -> RunRecord:
    return RunRecord.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_the_real_declined_record_reads_and_says_what_was_declined():
    r = _real()
    assert r.decision == "FINISH_REJECTED" and r.converged is True and r.unmeasured == ()
    assert r.declined == DECLINED
    assert r.swizzle_sound is True


def test_gaps_names_every_declined_check_even_when_unmeasured_is_empty():
    assert _real().gaps() == tuple(f"declined: {name}" for name in DECLINED)


def test_converged_is_not_zero_findings():
    r = _real()
    assert r.converged and r.findings_remaining == 27 and len(r.reobserved) == 27
    assert not r.clean


def test_participants_is_the_commit_set_that_took_part():
    parts = _real().participants()
    names = [name for name, _, _ in parts]
    assert names[:4] == ["warden", "ghost_tools", "swizzle", "assay"]
    assert names[4:7] == ["drafter seat", "finisher seat", "judge seat"]
    assert len(names) == 14 and all(n.startswith("join /stack/") for n in names[7:])
    assert all(len(commit) == 40 for _, commit, _ in parts)
    assert {dirty for _, _, dirty in parts} == {False}
    assert _real().dirty_parts() == ()


def _accept(**over: object) -> dict:
    base = {"schema": "cns.run/1", "contract": "1", "decision": "ACCEPT", "reason": "", "converged": True,
            "finished": True, "put_back": False, "unmeasured": [], "observed": ["g1"], "reobserved": [],
            "ghost_scan": {"status": "ok", "gaps": [], "declined": []}, "swizzle_sound": True,
            "versions": {"warden": {"commit": "a" * 40, "dirty": False},
                         "seats": {"judge": {"commit": "b" * 40, "dirty": False}},
                         "joins": [{"path": "/s/JUDGE", "commit": "b" * 40, "dirty": False}]}}
    base.update(over)
    return base


def test_clean_is_accept_converged_nothing_put_back_no_gap_and_nothing_remaining():
    assert RunRecord.from_dict(_accept()).clean


@pytest.mark.parametrize("change", [
    {"decision": "ACCEPT_UNVERIFIED"},
    {"converged": False},
    {"put_back": True},
    {"unmeasured": ["assay"]},
    {"reobserved": ["g1"]},
    {"ghost_scan": {"status": "ok", "gaps": ["parse: 1 file(s) could not be parsed"], "declined": []}},
    {"ghost_scan": {"status": "ok", "gaps": [], "declined": ["mutate"]}},
    {"versions": {"warden": {"commit": "a" * 40, "dirty": True}}},
])
def test_anything_less_than_fully_measured_is_not_clean(change):
    assert not RunRecord.from_dict(_accept(**change)).clean


def test_a_dirty_part_is_a_gap_and_is_named_and_a_null_flag_is_not_dirty():
    r = RunRecord.from_dict(_accept(versions={
        "warden": {"commit": "a" * 40, "dirty": None},
        "seats": {"judge": {"commit": "b" * 40, "dirty": True}, "drafter": None},
        "joins": [{"path": "/s/JUDGE", "commit": "b" * 40, "dirty": True}]}))
    assert r.dirty_parts() == ("judge seat", "join /s/JUDGE")
    assert r.gaps() == ("dirty: judge seat", "dirty: join /s/JUDGE")
    assert r.participants()[0] == ("warden", "a" * 40, None)


def test_a_part_without_a_commit_is_reported_with_an_empty_one_not_dropped():
    r = RunRecord.from_dict(_accept(versions={"assay": {"version": "0.11.3"}}))
    assert r.participants() == (("assay", "", None),)


def test_the_new_fields_are_typed_like_the_old_ones():
    with pytest.raises(ValueError, match="ghost_scan.declined is str, not a list"):
        RunRecord.from_dict(_good(ghost_scan={"declined": "mutate"}))
    with pytest.raises(ValueError, match="ghost_scan.declined holds something that is not text"):
        RunRecord.from_dict(_good(ghost_scan={"declined": ["mutate", 3]}))
    with pytest.raises(ValueError, match="reobserved is dict, not a list"):
        RunRecord.from_dict(_good(reobserved={}))
    with pytest.raises(ValueError, match="swizzle_sound is str, not a true or false value or null"):
        RunRecord.from_dict(_good(swizzle_sound="yes"))


def test_a_record_that_does_not_say_leaves_the_new_fields_unknown():
    r = RunRecord.from_dict(_good())
    assert r.reobserved == () and r.declined == () and r.swizzle_sound is None
    assert r.gaps() == ("unmeasured: ghost_partial", "ghost: boundary")


def test_the_pure_functions_are_pure():
    r = _real()
    assert r.gaps() == r.gaps() and r.participants() == r.participants()
    assert r == _real()


# ---------------------------------------------------------------------------------------------------------------
# 2.1.0: the claim row (which commit, which diff, which actor the run governed) and the Judge's input as written.
# Both optional, both read when present, None when absent; the schema stays cns.run/1.
# ---------------------------------------------------------------------------------------------------------------

CLAIM = {"origin": "https://example.invalid/o/r", "base_commit": "a" * 40, "claimed_commit": "b" * 40,
         "diff_sha256": "c" * 64, "actor": "someone", "files": [{"path": "x.py", "status": "M"}]}
EVIDENCE = {"target": "/t", "scope": "code", "ghost_before": ["g1"], "ghost_after": ["g1", "g2"],
            "ghost_severity": {"g2": "minor"}, "finisher_ran": True}


def test_a_record_with_a_claim_and_evidence_reads_them_back_as_written():
    r = RunRecord.from_dict(_good(claim=CLAIM, evidence=EVIDENCE))
    assert r.claim == CLAIM and r.evidence == EVIDENCE
    assert r.claim is not CLAIM and r.evidence is not EVIDENCE
    assert r.problems() == () and r.decision == "ACCEPT_UNVERIFIED"


def test_a_record_without_a_claim_or_evidence_reads_them_as_none():
    r = RunRecord.from_dict(_good())
    assert r.claim is None and r.evidence is None
    assert RunRecord.from_dict(_good(claim=None, evidence=None)).claim is None
    assert _real().claim is None and _real().evidence is None


def test_the_claim_and_evidence_are_typed_like_the_other_objects():
    with pytest.raises(ValueError, match="claim is list, not an object or null"):
        RunRecord.from_dict(_good(claim=["b" * 40]))
    with pytest.raises(ValueError, match="evidence is str, not an object or null"):
        RunRecord.from_dict(_good(evidence="held"))


def test_the_schema_is_still_cns_run_1_with_a_claim_present():
    r = RunRecord.from_dict(_good(claim=CLAIM, evidence=EVIDENCE, brand_new_field="anything"))
    assert r.schema == "cns.run/1" and not hasattr(r, "brand_new_field")

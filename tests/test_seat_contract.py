"""The seat contract's rows: what the governor writes, what the seats read and return."""
from __future__ import annotations

import dataclasses

import pytest

from cns.defect import Defect, DefectLifecycle, DefectSeverity
from cns.epistemic import EpistemicState
from cns.seat import Evidence, Facts, FileEdit, Verdict
from cns.suite import SuiteRun


def test_a_suite_run_is_green_only_when_it_ran_and_passed_clean():
    assert SuiteRun(ran=True, passed=3).green
    assert SuiteRun(ran=True, passed=3, exit_code=0).green
    assert not SuiteRun(ran=True, passed=0).green
    assert not SuiteRun(ran=True, passed=3, failed=1).green
    assert not SuiteRun(ran=True, passed=3, errors=1).green
    assert not SuiteRun(ran=True, passed=3, exit_code=1).green
    assert not SuiteRun(ran=False).green


def test_a_suite_run_says_what_happened_in_plain_words():
    assert SuiteRun(ran=False, reason="no tests").describe() == "did not run (no tests)"
    assert SuiteRun(ran=True, passed=2, skipped=1).describe() == (
        "2 passed, 0 failed, 0 errors, 1 skipped, 0 xfailed, 0 xpassed")
    assert "pytest exited 2 (collection)" in SuiteRun(ran=True, passed=1, exit_code=2, reason="collection").describe()


def test_a_defect_is_identified_by_the_scanner_first_then_the_label_then_the_summary():
    assert Defect("x", DefectSeverity.LOW, ghost_id="ghost-1", human_id="H1").identity == "ghost-1"
    assert Defect("x", DefectSeverity.LOW, human_id="H1").identity == "H1"
    assert Defect("the summary", DefectSeverity.LOW).identity == "the summary"


def test_defect_defaults_are_the_unmeasured_ones():
    d = Defect("x", DefectSeverity.HIGH)
    assert d.lifecycle is DefectLifecycle.IDENTIFIED and d.epistemic is EpistemicState.UNKNOWN
    assert d.evidence == () and d.attributes == {}


def test_the_rows_are_frozen_where_the_contract_says_so():
    rows = [
        (FileEdit("a", "write", "x"), "path"),
        (Facts(suite=None, remaining=(), cycles=0), "cycles"),
        (Verdict("ACCEPT", ()), "decision"),
    ]
    for row, field_name in rows:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(row, field_name, "changed")


def test_evidence_says_not_measured_with_none_and_never_with_a_default():
    e = Evidence(target="/t", scope="code", cycles=(), changed=(), judging_files_touched=(),
                 suite_before=None, suite_after=None, ghost_before=None, ghost_after=None, declined=(),
                 swizzle_proofs=None, attacks=None, unmeasured=("ghost",))
    assert e.ghost_before is None and e.suite_after is None and e.unmeasured == ("ghost",)
    assert e.notes == () and e.assay is None


def test_the_seat_rows_only_hold_the_types_the_contract_names():
    for cls in (FileEdit, Facts, Evidence, Verdict):
        assert all(not callable(getattr(cls, name, None)) or name.startswith("__") for name in vars(cls)
                   if not name.startswith("__")), cls

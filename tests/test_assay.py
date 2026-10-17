"""cns.assay: the ASSAY summary row. Readers rely on exactly what is named here."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cns.assay import AssaySummary


def _good(**over: object) -> dict:
    base = {
        "schema": "assay-summary/1", "all_claims_hold": False, "status": "MANIFEST_INCONSISTENT",
        "claims": {"total": 4, "passed": 3, "failed": 1, "skipped": 0},
        "entries": {"total": 2, "counts": {"EXECUTION": 1, "STATIC": 1, "UNVALIDATED": 0},
                    "status": {"E-1": "EXECUTION", "E-2": "STATIC"}},
        "failures": [{"claim": "C-3", "reason": "claim_failed", "detail": "the entry is not backed"}],
        "extra_from_a_newer_assay": True,
    }
    base.update(over)
    return base


def test_a_good_summary_reads_and_keeps_its_named_fields():
    s = AssaySummary.from_dict(_good())
    assert (s.schema, s.all_claims_hold, s.status) == ("assay-summary/1", False, "MANIFEST_INCONSISTENT")
    assert s.claims["failed"] == 1 and s.entries["status"]["E-1"] == "EXECUTION"
    assert s.failures[0]["claim"] == "C-3"
    assert s.problems() == ()


def test_extra_keys_are_allowed_and_ignored():
    assert not hasattr(AssaySummary.from_dict(_good()), "extra_from_a_newer_assay")


def test_claims_entries_and_failures_may_be_left_out():
    s = AssaySummary.from_dict({"schema": "assay-summary/1", "all_claims_hold": True, "status": "PROVEN"})
    assert dict(s.claims) == {} and dict(s.entries) == {} and s.failures == ()


@pytest.mark.parametrize("key", ["schema", "all_claims_hold", "status"])
def test_each_required_field_is_required(key):
    data = _good()
    del data[key]
    with pytest.raises(ValueError, match=f"{key} is missing or null"):
        AssaySummary.from_dict(data)


def test_a_summary_from_another_schema_is_refused_with_the_reason():
    with pytest.raises(ValueError, match="schema is 'assay-summary/0', not 'assay-summary/1'"):
        AssaySummary.from_dict(_good(schema="assay-summary/0"))


def test_flags_must_be_true_or_false_not_truthy_text():
    with pytest.raises(ValueError, match="all_claims_hold is str, not a true or false value"):
        AssaySummary.from_dict(_good(all_claims_hold="yes"))


def test_status_must_be_text_and_not_empty():
    with pytest.raises(ValueError, match="status is int, not text"):
        AssaySummary.from_dict(_good(status=3))
    with pytest.raises(ValueError, match="status is empty"):
        AssaySummary.from_dict(_good(status="  "))


def test_failures_must_be_a_list_of_objects():
    with pytest.raises(ValueError, match="failures is str, not a list"):
        AssaySummary.from_dict(_good(failures="C-3"))
    with pytest.raises(ValueError, match="failures holds something that is not an object"):
        AssaySummary.from_dict(_good(failures=["C-3"]))


def test_claims_and_entries_must_be_objects_when_present():
    with pytest.raises(ValueError, match="claims is list, not an object"):
        AssaySummary.from_dict(_good(claims=[1]))
    with pytest.raises(ValueError, match="entries is str, not an object"):
        AssaySummary.from_dict(_good(entries="E-1"))


def test_a_summary_that_is_not_an_object_is_refused():
    with pytest.raises(ValueError, match="an ASSAY summary is an object, not str"):
        AssaySummary.from_dict("ASSAY-SUMMARY")  # type: ignore[arg-type]


def test_the_row_is_frozen():
    s = AssaySummary(schema="assay-summary/1", all_claims_hold=True, status="PROVEN")
    with pytest.raises(FrozenInstanceError):
        s.status = "MANIFEST_INCONSISTENT"  # type: ignore[misc]


def test_the_module_holds_no_state_and_reads_no_file():
    text = (Path(__file__).resolve().parents[1] / "cns" / "assay.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assigned = [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                for t in ([n.target] if isinstance(n, ast.AnnAssign) else n.targets) if isinstance(t, ast.Name)]
    assert all(name.startswith("__") and name.endswith("__") for name in assigned), assigned
    assert "open(" not in text and "import json" not in text and "pathlib" not in text

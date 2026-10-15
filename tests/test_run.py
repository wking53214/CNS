"""cns.run: the run record contract. Readers rely on exactly what is named here."""
from __future__ import annotations

import ast
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

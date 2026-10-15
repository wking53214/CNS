"""cns.finding: the Ghost finding row. Readers rely on exactly what is named here."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cns.finding import Finding


def _good(**over: object) -> dict:
    base = {
        "id": "ghost-3f9a", "detector": "list_membership_in_loop", "category": "performance",
        "layer": "code", "severity": "minor", "status": "confirmed", "summary": "list used for membership",
        "detail": "a list is scanned on every pass", "attributes": {"container": "parse"},
        "evidence": {"file": "app/parse.py", "line_start": 12, "snippet": "if x in items:"},
        "confidence": 0.9, "first_seen": "2026-10-01",
    }
    base.update(over)
    return base


def test_a_good_finding_reads_and_keeps_its_named_fields():
    f = Finding.from_dict(_good())
    assert (f.id, f.detector, f.severity, f.status) == ("ghost-3f9a", "list_membership_in_loop", "minor", "confirmed")
    assert f.evidence["file"] == "app/parse.py" and f.attributes["container"] == "parse"
    assert f.problems() == ()


def test_detail_evidence_and_attributes_may_be_left_out():
    f = Finding.from_dict({k: _good()[k] for k in ("id", "detector", "severity", "status", "summary")})
    assert f.detail == "" and dict(f.evidence) == {} and dict(f.attributes) == {}


@pytest.mark.parametrize("key", ["id", "detector", "severity", "status", "summary"])
def test_each_named_text_field_is_required(key):
    data = _good()
    del data[key]
    with pytest.raises(ValueError, match=f"{key} is missing or null, not text"):
        Finding.from_dict(data)


def test_a_null_field_is_refused_not_read_as_the_word_none():
    with pytest.raises(ValueError, match="status is missing or null, not text"):
        Finding.from_dict(_good(status=None))


def test_a_text_field_that_is_not_text_is_refused():
    with pytest.raises(ValueError, match="id is int, not text"):
        Finding.from_dict(_good(id=7))


def test_detail_must_be_text_when_present():
    with pytest.raises(ValueError, match="detail is list, not text"):
        Finding.from_dict(_good(detail=["x"]))


@pytest.mark.parametrize("key", ["evidence", "attributes"])
def test_evidence_and_attributes_must_be_objects_when_present(key):
    with pytest.raises(ValueError, match=f"{key} is str, not an object"):
        Finding.from_dict(_good(**{key: "file.py"}))


def test_an_empty_identity_is_named_as_a_problem():
    with pytest.raises(ValueError, match="id is empty"):
        Finding.from_dict(_good(id="  "))
    assert Finding(id="", detector="d", severity="minor", status="confirmed", summary="s").problems() == ("id is empty",)


def test_extra_keys_are_allowed_and_ignored():
    f = Finding.from_dict(_good(brand_new_key=[1, 2]))
    assert not hasattr(f, "brand_new_key") and f.id == "ghost-3f9a"


def test_a_finding_that_is_not_an_object_is_refused():
    with pytest.raises(ValueError, match="a finding is an object, not str"):
        Finding.from_dict("ghost-3f9a")  # type: ignore[arg-type]


def test_the_row_is_frozen():
    f = Finding(id="g", detector="d", severity="minor", status="confirmed", summary="s")
    with pytest.raises(FrozenInstanceError):
        f.status = "rejected"  # type: ignore[misc]


def test_the_module_holds_no_state_and_reads_no_file():
    text = (Path(__file__).resolve().parents[1] / "cns" / "finding.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assigned = [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                for t in ([n.target] if isinstance(n, ast.AnnAssign) else n.targets) if isinstance(t, ast.Name)]
    assert all(name.startswith("__") and name.endswith("__") for name in assigned), assigned
    assert "open(" not in text and "import json" not in text and "pathlib" not in text

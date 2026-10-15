"""cns.attack: the attack result row. Readers rely on exactly what is named here."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cns.attack import AttackResult


def _good(**over: object) -> dict:
    base = {"scenario": "governor_writes_outside_target", "severity": "high", "status": "held",
            "proof": "some text SWIZZLE also reports", "attempts": 3}
    base.update(over)
    return base


def test_a_good_result_reads_and_keeps_its_named_fields():
    r = AttackResult.from_dict(_good())
    assert (r.scenario, r.severity, r.status) == ("governor_writes_outside_target", "high", "held")
    assert r.problems() == ()


def test_extra_keys_are_allowed_and_ignored():
    assert not hasattr(AttackResult.from_dict(_good()), "proof")


@pytest.mark.parametrize("key", ["scenario", "severity", "status"])
def test_each_named_field_is_required(key):
    data = _good()
    del data[key]
    with pytest.raises(ValueError, match=f"{key} is missing or null, not text"):
        AttackResult.from_dict(data)


def test_a_null_field_is_refused_not_read_as_the_word_none():
    with pytest.raises(ValueError, match="status is missing or null, not text"):
        AttackResult.from_dict(_good(status=None))


def test_a_field_that_is_not_text_is_refused_with_its_type():
    with pytest.raises(ValueError, match="severity is int, not text"):
        AttackResult.from_dict(_good(severity=3))


def test_an_empty_field_is_named_as_a_problem():
    with pytest.raises(ValueError, match="scenario is empty"):
        AttackResult.from_dict(_good(scenario="   "))
    assert AttackResult(scenario="", severity="high", status="held").problems() == ("scenario is empty",)


def test_a_result_that_is_not_an_object_is_refused():
    with pytest.raises(ValueError, match="an attack result is an object, not list"):
        AttackResult.from_dict(["held"])  # type: ignore[arg-type]


def test_the_row_is_frozen():
    r = AttackResult(scenario="s", severity="high", status="held")
    with pytest.raises(FrozenInstanceError):
        r.status = "violated"  # type: ignore[misc]


def test_the_module_holds_no_state_and_reads_no_file():
    text = (Path(__file__).resolve().parents[1] / "cns" / "attack.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    assigned = [t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                for t in ([n.target] if isinstance(n, ast.AnnAssign) else n.targets) if isinstance(t, ast.Name)]
    assert all(name.startswith("__") and name.endswith("__") for name in assigned), assigned
    assert "open(" not in text and "import json" not in text and "pathlib" not in text

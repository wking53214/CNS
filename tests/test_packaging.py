"""What the wheel is configured to carry, and the one rule that keeps the two packages apart.

The wheel itself is built and inspected by the `packaging` job in CI. These hold the configuration and the
direction of the dependency, so a change to either fails here first. tomllib is not used: this package
supports Python 3.10.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _list(key: str) -> list[str]:
    found = re.search(rf"^{key}\s*=\s*\[(.*?)\]", PYPROJECT, re.M | re.S)
    assert found, f"{key} is not set in pyproject.toml"
    return re.findall(r'"([^"]+)"', found.group(1))


def test_the_wheel_carries_cns_and_cns_composition():
    include = _list("include")
    assert "cns" in include and "cns.*" in include
    assert "cns_composition" in include


def test_the_composition_tests_do_not_ship():
    assert "cns_composition.tests" in _list("exclude")
    assert not (ROOT / "cns_composition" / "tests" / "__init__.py").exists(), (
        "an __init__.py there makes the tests a package, which find would pick up if exclude were dropped")


def test_cns_never_imports_cns_composition():
    """The shapes package must not depend on the behaviour package that sits on top of it."""
    for path in (ROOT / "cns").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            assert not any(n.split(".")[0] == "cns_composition" for n in names), f"{path.name} imports cns_composition"


def test_cns_composition_imports_only_cns_and_itself_and_the_standard_library():
    import sys
    allowed = set(sys.stdlib_module_names) | {"cns", "cns_composition", "__future__"}
    for path in (ROOT / "cns_composition").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for name in names:
                assert name.split(".")[0] in allowed, f"{path.name} imports {name}, which the wheel does not carry"

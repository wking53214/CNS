"""The public shape of the package, pinned to a golden file.

CNS cannot import its consumers in CI: they are separate private
repositories, and the README is right that their own tests are the check
that can fail. But "their tests are the check" only works if a shape change
here is visible to whoever makes it, and today a field can be renamed and
three repositories find out by breaking.

This is the substitute. It records every public class, its bases and kind,
its fields in order with their annotations and defaults, its enum members
and values, and its explicitly defined methods with their signatures. Any
change to any of that fails this test and prints what moved.

The point is not that the shape may never change. It is that changing it is
a deliberate act with a diff attached: you regenerate the golden file in the
same commit, and the review sees the contract move.

    python tests/test_public_shape.py --update

Under this package's versioning rule, a field added with a default is a
minor version and a field removed, renamed or given a new meaning is a
major one. The regenerated diff is the evidence for which of those it was.
"""
from __future__ import annotations

import dataclasses
import enum
import importlib
import inspect
import json
import pkgutil
import sys
from pathlib import Path

import cns

GOLDEN = Path(__file__).with_name("public_shape.json")

_MISSING = object()


def _default_of(f):
    if f.default is not dataclasses.MISSING:
        return repr(f.default)
    if f.default_factory is not dataclasses.MISSING:
        return f"factory:{getattr(f.default_factory, '__name__', repr(f.default_factory))}"
    return None


def _members(cls):
    """Public methods and properties the author wrote, with signatures.

    Underscored names are skipped on purpose. `@dataclass` and `Enum`
    synthesise `__init__`, `__eq__`, `__hash__`, `__new__` and friends, and
    the exact repr of those varies between interpreter versions; recording
    them would make this test fail across the CI matrix for reasons that have
    nothing to do with the contract. What they encode is pinned already, and
    more precisely, by `fields`, `enum_members`, `frozen` and `slots`."""
    out = {}
    for name, obj in sorted(vars(cls).items()):
        if name.startswith("_"):
            continue
        if isinstance(obj, property):
            out[name] = "property"
        elif inspect.isfunction(obj):
            try:
                out[name] = f"def{inspect.signature(obj)}"
            except (ValueError, TypeError):
                out[name] = "def(?)"
    return out


def _shape_of(cls):
    shape = {
        "bases": [b.__name__ for b in cls.__bases__],
        "members": _members(cls),
    }
    if isinstance(cls, enum.EnumMeta):
        shape["kind"] = "enum"
        shape["enum_members"] = [[m.name, m.value] for m in cls]
    elif dataclasses.is_dataclass(cls):
        shape["kind"] = "dataclass"
        params = getattr(cls, "__dataclass_params__", None)
        shape["frozen"] = bool(getattr(params, "frozen", False))
        shape["slots"] = "__slots__" in vars(cls)
        shape["fields"] = [
            {"name": f.name, "type": str(f.type), "default": _default_of(f)}
            for f in dataclasses.fields(cls)
        ]
    elif issubclass(cls, BaseException):
        shape["kind"] = "exception"
    elif getattr(cls, "_is_protocol", False):
        shape["kind"] = "protocol"
        shape["annotations"] = {k: str(v) for k, v in
                                sorted(vars(cls).get("__annotations__", {}).items())}
    else:
        shape["kind"] = "class"
        shape["annotations"] = {k: str(v) for k, v in
                                sorted(vars(cls).get("__annotations__", {}).items())}
    return shape


def public_shape():
    """Every exported name in every cns module, as plain JSON-able data."""
    out = {"version": cns.__version__, "modules": {}}
    names = [cns.__name__] + [i.name for i in pkgutil.walk_packages(cns.__path__, "cns.")]
    for modname in sorted(names):
        mod = importlib.import_module(modname)
        exported = getattr(mod, "__all__", None)
        if exported is None:
            continue
        entry = {"__all__": list(exported), "classes": {}, "functions": {}}
        for name in exported:
            obj = getattr(mod, name, _MISSING)
            assert obj is not _MISSING, f"{modname}.__all__ names {name}, which does not exist"
            if inspect.isclass(obj):
                entry["classes"][name] = _shape_of(obj)
            elif inspect.isfunction(obj):
                entry["functions"][name] = f"def{inspect.signature(obj)}"
        out["modules"][modname] = entry
    return out


def test_the_public_shape_is_the_one_on_record():
    assert GOLDEN.exists(), (
        f"{GOLDEN.name} is missing. Generate it with:\n"
        f"    python tests/test_public_shape.py --update")
    recorded = json.loads(GOLDEN.read_text())
    current = public_shape()
    if current == recorded:
        return

    lines = []
    for mod in sorted(set(recorded["modules"]) | set(current["modules"])):
        was, now = recorded["modules"].get(mod), current["modules"].get(mod)
        if was is None:
            lines.append(f"  module added: {mod}")
            continue
        if now is None:
            lines.append(f"  MODULE REMOVED: {mod}  (major version)")
            continue
        for kind in ("classes", "functions"):
            for nm in sorted(set(was[kind]) | set(now[kind])):
                a, b = was[kind].get(nm), now[kind].get(nm)
                if a == b:
                    continue
                if a is None:
                    lines.append(f"  added:   {mod}.{nm}")
                elif b is None:
                    lines.append(f"  REMOVED: {mod}.{nm}  (major version)")
                else:
                    lines.append(f"  changed: {mod}.{nm}")
                    lines.append(f"      was: {json.dumps(a, sort_keys=True)}")
                    lines.append(f"      now: {json.dumps(b, sort_keys=True)}")
    if recorded["version"] != current["version"]:
        lines.append(f"  version: {recorded['version']} -> {current['version']}")

    raise AssertionError(
        "The public shape changed. Every consumer joins on this.\n"
        + "\n".join(lines)
        + "\n\nIf the change is intended, record it in the same commit:\n"
          "    python tests/test_public_shape.py --update\n"
          "and set the version: a field added with a default is minor, a field\n"
          "removed, renamed or given a new meaning is major.")


def test_every_exported_name_resolves():
    """__all__ is the contract's index. A name in it that does not exist is a
    consumer's ImportError, and it is cheap to never ship one."""
    for modname, entry in public_shape()["modules"].items():
        mod = importlib.import_module(modname)
        for name in entry["__all__"]:
            assert hasattr(mod, name), f"{modname}.__all__ names missing {name}"


if __name__ == "__main__":
    if "--update" in sys.argv:
        GOLDEN.write_text(json.dumps(public_shape(), indent=2, sort_keys=True) + "\n")
        print(f"wrote {GOLDEN}")
    else:
        print(json.dumps(public_shape(), indent=2, sort_keys=True))

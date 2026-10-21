"""consumers: what each repository takes from CNS, held in CNS so CNS cannot take it away unnoticed.

WHY THIS EXISTS

Repositories pin CNS by commit or tag, so a rename in CNS does not break them the day it lands. It breaks them
the day somebody moves a pin, in a repository that did not change, found by a failing install. The pin hides the
dependency from CNS: nothing on this side says "Link needs `TriadOutput` from `ccc_admission`", so nothing on
this side stops it being renamed.

This module is that statement. `REQUIRED` lists, per repository, each CNS module its non-test code imports and
the names it takes from it, read from the repository's own source. `missing` says what CNS no longer provides
of that list, and CNS's own tests assert it is empty, so a change that would break a consumer fails here first,
naming the consumer. `drift` is the other direction: it re-reads the repositories' source and says where the list
has gone stale, so the list stays a fact and not a memory.

WHAT IT READS

Python files that are not tests, as text, with `ast`. A `from cns.x import y` records `y` under `cns.x`. An
`import cns.x` or `importlib.import_module("cns.x")` records the module with no names (attribute use cannot be
read from an import). A relative import is the repository's own. Nothing from any repository is executed.

WHAT IT DOES NOT DO

It does not check versions. A repository pinned to an old CNS is not checked against that old CNS; the question
here is only whether CNS as it is now still offers what the repository's current source asks for.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

__all__ = ["REQUIRED", "drift", "main", "missing", "scan"]

Imports = Mapping[str, Tuple[str, ...]]

#: repository -> CNS module -> the names it takes from that module (empty: the module itself).
REQUIRED: Mapping[str, Imports] = {
    "Link": {
        "cns_composition.ccc_admission": ("TriadOutput",),
        "cns_composition.resubmission": ("ResubmissionGuard",),
        "cns_composition.triad_admission": ("admit_candidates",),
    },
    "sentinel_os": {
        "cns.gate": ("GateOutcome", "GatePosition", "subject_digest"),
        "cns.graph": ("Edge", "Graph", "Node"),
    },
    "GSA-815": {
        "cns.caller": ("CallerState", "DynamicState"),
        "cns.governance": (
            "AuthorizationError", "ExecutionDomain", "GovernanceError", "IdentityContext", "IntegrityError",
            "IntentCategory", "KernelComponent", "KernelMetadata", "PolicyViolation", "QueueType",
            "RoutingDecision", "RoutingError", "TrustLevel", "ValidationError"),
        "cns.perception": ("CallOutcome", "CallPercept", "EmotionalState", "FrictionEvent"),
    },
    "ZTS": {
        "cns": (),
        "cns.gate": ("subject_digest",),
        "cns.governance": ("IdentityContext",),
    },
    "OBSERVE": {
        "cns.gate": (),
    },
    "observe-perceive": {
        "cns.gate": ("Gate", "GateChain", "GateOutcome", "GatePosition", "resolve", "subject_digest", "unbound"),
    },
    # Optional connectors that load cns.gate on demand: the module is all an import can show, and CNS's own
    # gate tests cover the names (subject_digest, GateResult, GateOutcome, GatePosition, GateChain) they use.
    "TIE": {"cns.gate": ()},
    "CCCb": {"cns.gate": ()},
    "Ecology": {"cns.gate": ()},
    "GSA": {"cns.gate": ()},
    "Triad-42": {"cns.gate": ()},
    "experimental": {"cns.gate": ()},
    "DGK": {"cns.gate": ()},
    "URE": {"cns.gate": ()},
    "interconnected_alpha": {"cns.gate": ()},
    "interconnected_zeta": {"cns.gate": ()},
    "interconnected_beta": {"cns.gate": ()},
    "interconnected_delta": {"cns.gate": ()},
    # Private repositories: the links workflow cannot clone them, so `drift` skips them when there is no checkout.
    "ATS": {"cns.gate": ()},
    "Resume_OS": {"cns.gate": ()},
}

_OURS = ("cns", "cns_composition")
#: Folders that are not the repository's own running code. `archive` holds preserved records (GSA keeps an old
#: file there that imports cns.governance on purpose); a record is not a consumer.
_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "site-packages", "__pycache__", "build", "dist", "archive"}
_MAX_BYTES = 2_000_000


def _is_test(rel: Tuple[str, ...]) -> bool:
    name = rel[-1]
    return (any(p.lower() in ("tests", "test") for p in rel[:-1]) or name.startswith("test_")
            or name.endswith("_test.py") or name == "conftest.py")


def scan(folder: Path) -> Dict[str, Tuple[str, ...]]:
    """Every CNS module the non-test Python in `folder` imports, with the names taken from it."""
    folder = Path(folder)
    found: Dict[str, set] = {}
    for path in sorted(folder.rglob("*.py")):
        rel = path.relative_to(folder).parts
        if any(p in _SKIP_DIRS for p in rel) or _is_test(rel) or path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > _MAX_BYTES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module \
                    and node.module.split(".")[0] in _OURS:
                found.setdefault(node.module, set()).update(a.name for a in node.names if a.name != "*")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _OURS:
                        found.setdefault(alias.name, set())
            elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str) and node.args[0].value.split(".")[0] in _OURS \
                    and getattr(node.func, "attr", getattr(node.func, "id", "")) == "import_module":
                found.setdefault(node.args[0].value, set())
    return {mod: tuple(sorted(names)) for mod, names in sorted(found.items())}


def missing(required: Optional[Mapping[str, Imports]] = None) -> List[str]:
    """What CNS, as it is now, no longer provides of what the repositories take from it. Empty is healthy."""
    out: List[str] = []
    for repo, modules in (REQUIRED if required is None else required).items():
        for module, names in modules.items():
            try:
                loaded = importlib.import_module(module)
            except ImportError:
                out.append(f"{repo} imports {module}, which CNS no longer has")
                continue
            out.extend(f"{repo} takes {name} from {module}, which CNS no longer has"
                       for name in names if not hasattr(loaded, name))
    return out


def drift(stack: Path, required: Optional[Mapping[str, Imports]] = None,
          private: Tuple[str, ...] = ()) -> List[str]:
    """Where `REQUIRED` no longer matches the source in `stack`, for each registered repository that is there.

    A repository named in `private` (the ledger's private ones) may have no checkout; it is skipped then."""
    stack = Path(stack)
    out: List[str] = []
    for repo, registered in (REQUIRED if required is None else required).items():
        folder = next((p for p in sorted(stack.iterdir())
                       if p.is_dir() and not p.is_symlink() and p.name.casefold() == repo.casefold()), None)
        if folder is None:
            if repo.casefold() not in {p.casefold() for p in private}:
                out.append(f"{repo} is registered but has no checkout in {str(stack)!r}")
            continue
        actual = scan(folder)
        for module in sorted(set(actual) | set(registered)):
            have, want = set(actual.get(module, ())), set(registered.get(module, ()))
            if module not in actual:
                out.append(f"{repo} no longer imports {module}; remove it from REQUIRED")
            elif module not in registered:
                out.append(f"{repo} now imports {module} ({', '.join(sorted(have)) or 'module only'}), "
                           "which REQUIRED does not list")
            elif have != want:
                if have - want:
                    out.append(f"{repo} now takes {', '.join(sorted(have - want))} from {module}, not in REQUIRED")
                if want - have:
                    out.append(f"{repo} no longer takes {', '.join(sorted(want - have))} from {module}; "
                               "remove from REQUIRED")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.consumers",
        description="Check that CNS still provides what the registered repositories take from it, "
                    "and (with --stack) that the registry still matches their source.")
    parser.add_argument("--stack", type=Path, default=None, help="a folder with one checkout per repository")
    args = parser.parse_args(argv)
    problems = missing()
    if args.stack is not None:
        if not args.stack.is_dir():
            print(f"consumers: the stack folder {str(args.stack)!r} does not exist", file=sys.stderr)
            return 2
        from cns_composition.link_ledger import LedgerError, read_ledger
        try:
            private = tuple(k.repo for k in read_ledger(Path(__file__).resolve().parents[1] / "contracts" / "cns-links.json")
                            if k.private)
        except LedgerError:
            private = ()
        problems += drift(args.stack, private=private)
    for line in problems:
        print(f"consumers: {line}", file=sys.stderr)
    if not problems:
        names = sum(len(n) or 1 for m in REQUIRED.values() for n in m.values())
        print(f"consumers: CNS provides everything {len(REQUIRED)} repositories take from it ({names} items)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

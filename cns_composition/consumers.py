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
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from cns_composition import delivery, repin

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
        # root_admission.py: the roster that must approve a root before the kernel registers it. These are the
        # consequential imports, and they were missing, so a rename here would have broken it unannounced.
        "cns_composition.decision_guard": ("DecisionGuard",),
        "cns_composition.super_gate": ("Judged", "SuperGate"),
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
    # Registered 2026-11-04 from each repository's own source (`scan`), after `drift` was changed to name an importer
    # that is not here. Until then 16 repositories took things from CNS that no check watched, among them the shapes
    # (`cns.seat`, `cns.suite`, `cns.defect`, `cns.run`) WARDEN, JUDGE, BURNISH, DRAFTER, ASSAY and WATCHER_MCU stand on.
    "ghost_tools": {"cns.gate": ()},
    "SWIZZLE": {"cns.gate": ()},
    "ASSAY": {"cns.assay": (), "cns.gate": ()},
    "DRAFTER": {"cns.defect": ("Defect",), "cns.seat": ("FileEdit",)},
    "JUDGE": {
        "cns.gate": ("GateChain", "GateOutcome", "GatePosition", "GateResult", "subject_digest"),
        "cns.seat": ("Evidence", "Verdict"),
        "cns.suite": ("SuiteRun",),
    },
    "BURNISH": {
        "cns.defect": ("Defect",), "cns.epistemic": ("EpistemicState",), "cns.seat": ("Facts", "FileEdit"),
        "cns.suite": ("SuiteRun",),
    },
    "WARDEN": {
        "cns.attack": ("AttackResult",), "cns.defect": ("Defect", "DefectLifecycle", "DefectSeverity"),
        "cns.epistemic": ("EpistemicState",), "cns.finding": ("Finding",),
        "cns.seat": ("Evidence", "Facts", "FileEdit", "Verdict"), "cns.suite": ("SuiteRun",),
    },
    "CCC": {"cns.gate": ()},
    "WATCHER_MCU": {"cns.run": ("RunRecord",)},
    "HERALD": {"cns.gate": ()},
    "Conservation_Kernel": {"cns.gate": ()},
    "GEMS": {"cns.gate": ()},
    "fortress-kernel": {"cns.gate": ()},
    "DIT": {"cns.gate": ()},
    "PERCEIVE": {"cns.gate": ()},
    "Governance_Gateway": {"cns.gate": ()},
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
          private: Tuple[str, ...] = (), expect: Iterable[str] = ()) -> List[str]:
    """Where `REQUIRED` no longer matches the source in `stack`, for each registered repository that is there.

    A repository named in `private` (the ledger's private ones) may have no checkout; it is skipped then.

    `expect` names the repositories the ledger says are connected. Each one that has a checkout, imports CNS in its
    non-test source and is NOT registered is named: without this the check only ever looked at repositories someone had
    already registered, so a consumer nobody listed could be broken by a rename in CNS without a test saying so."""
    stack = Path(stack)
    out: List[str] = []
    for repo, registered in (REQUIRED if required is None else required).items():
        folder = next((p for p in repin.stack_folders(stack) if p.name.casefold() == repo.casefold()), None)
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
    known = {r.casefold() for r in (REQUIRED if required is None else required)}
    for repo in expect:
        if repo.casefold() in known:
            continue
        folder = next((p for p in repin.stack_folders(stack) if p.name.casefold() == repo.casefold()), None)
        actual = scan(folder) if folder is not None else {}
        if actual:
            seen = ", ".join(f"{m} ({', '.join(n)})" if n else m for m, n in actual.items())
            out.append(f"{repo} imports {seen}, but is not registered in REQUIRED; list it so a rename in CNS "
                       "fails here and names it")
    return out


def _main(argv: Optional[List[str]] = None) -> int:
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
            links = read_ledger(delivery.CONTRACTS / "cns-links.json")
            private = tuple(k.repo for k in links if k.private)
            connected = tuple(k.repo for k in links if not k.hub and not k.exempt)
        except LedgerError as err:
            # Without the ledger the private repositories would be reported as missing checkouts, which is not
            # what is wrong. Say what is, and claim nothing.
            print(f"consumers: {err}", file=sys.stderr)
            return 2
        problems += drift(args.stack, private=private, expect=connected)
    for line in problems:
        print(f"consumers: {line}", file=sys.stderr)
    if not problems:
        names = sum(len(n) or 1 for m in REQUIRED.values() for n in m.values())
        print(f"consumers: CNS provides everything {len(REQUIRED)} repositories take from it ({names} items)")
    return 1 if problems else 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "consumers")


if __name__ == "__main__":
    raise SystemExit(main())

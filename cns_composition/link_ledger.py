"""link_ledger: which repositories are connected to CNS, in which direction, and the proof.

WHY THIS EXISTS

"Every repository is connected to CNS both ways" is a claim, and a claim nobody can run drifts. The atlas
that first counted the connections graded some of them by what a docstring said. This is the same count made
checkable: `contracts/cns-links.json` names every repository, the file that proves each direction, and the
reason for any repository that cannot be connected. The checker opens the files and fails on a claim they do
not support.

WHAT COUNTS AS EACH DIRECTION

  to_cns    The repository's own code or dependency list uses CNS: a Python file that imports `cns` or
            `cns_composition` (a lazy `importlib.import_module("cns...")` counts), or a dependency line in a
            pyproject.toml / requirements file that names `cns` or `cns_composition`. A repository that cannot
            import Python proves it by vendoring CNS's `contracts/digest-vectors.json` exactly (STACK-Kernel's
            Rust reproduction checks itself against that file). The proof is a path inside that repository,
            read with `--stack`.
  from_cns  CNS carries behaviour or a pin for the repository. CNS imports no repository (it is stdlib-only by
            rule), so this cannot be an import. The proof is a path inside CNS that is either
              - a JSON file under `contracts/` whose `repos` object names the repository (a pin the circuit
                refuses to run without), or
              - a Python module under `cns_composition/` that names the repository in code: an identifier or a
                string that is not a docstring. A repository mentioned only in a docstring is history, not a
                connection, and does not count. A module under `cns/` never counts: that package is shapes.

A repository that CNS knows by another name in code (Triad-42 is `triad`) lists it under `aka`.

A repository built to import nothing (Triad-42 is the example: a bridge, Link, is the one place that joins it to
CNS) says so with `via`: the bridge repository and the module of this repository the bridge imports. It is
`bridged` when it has a from_cns proof and a bridge that is itself `two_way` and, with `--stack`, whose
non-test source really imports that module. `bridged` is counted apart from `two_way` so nobody mistakes the
one for the other, and `--require-two-way` accepts both.

A repository whose source cannot be cloned with the checker's default token (a private repository) says
`"private": true`. With `--stack` and a checkout, its to_cns proof is checked like any other. Without a
checkout the proof is not checked and the run says so by name, because a claim nobody can check is not the same
as a claim that was checked. A private repository must still name a to_cns proof.

A repository is `two_way` with both, `to_cns` or `from_cns` with one, `none` with neither. A repository that
cannot be connected (empty, retired, documents only) says why under `exempt` and is left out of the count.

WHAT IT DOES NOT PROVE

That the proof file works. Each connector has its own tests for that. This proves the proof file exists and
says what the ledger says it does, so a connection cannot be claimed by editing prose.

The files are read as text and never executed.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["LEDGER_SCHEMA", "Link", "LedgerError", "read_ledger", "status", "problems", "unverified", "counts", "main"]

LEDGER_SCHEMA = "cns-links/1"
_MAX_BYTES = 2_000_000
#: A dependency line: the name `cns` (or `cns_composition`) at the start of an entry, then a version, an extra,
#: a direct URL, a quote or the end of the line. `cnsx` and `my-cns` do not match.
_DEPENDENCY = re.compile(r"""(?mi)(?:^|[\s"',\[])cns(?:_composition)?(?:\[[^\]]*\])?\s*(?:@|[<>=~!]=?|["',\]]|$)""")
_DEPENDENCY_FILES = ("pyproject.toml", "setup.cfg", "setup.py")


class LedgerError(Exception):
    """The ledger itself could not be read or is not the documented shape."""


@dataclass(frozen=True)
class Link:
    repo: str
    to_cns: Optional[str] = None
    from_cns: Optional[str] = None
    exempt: Optional[str] = None
    hub: bool = False
    aka: Tuple[str, ...] = ()
    via: Optional[Tuple[str, str]] = None   # (bridge repository, module of this repository the bridge imports)
    private: bool = False                   # its source cannot be cloned with the default token


def status(link: Link) -> str:
    if link.hub:
        return "hub"
    if link.exempt:
        return "exempt"
    if link.to_cns and link.from_cns:
        return "two_way"
    if link.via and link.from_cns and not link.to_cns:
        return "bridged"
    if link.to_cns:
        return "to_cns"
    if link.from_cns:
        return "from_cns"
    return "none"


def read_ledger(path: Path) -> List[Link]:
    """The ledger as `Link`s, in file order. Raises LedgerError for anything that is not the documented shape."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise LedgerError(f"the ledger {str(path)!r} cannot be read as JSON: {type(err).__name__}") from err
    if not isinstance(data, dict) or data.get("schema") != LEDGER_SCHEMA or not isinstance(data.get("repos"), dict):
        raise LedgerError(f'the ledger must be an object with "schema": "{LEDGER_SCHEMA}" and a "repos" object')
    known = {"to_cns", "from_cns", "exempt", "hub", "aka", "via", "private"}
    links: List[Link] = []
    for name, entry in data["repos"].items():
        if not isinstance(entry, dict):
            raise LedgerError(f"{name!r} must be an object")
        extra = sorted(set(entry) - known)
        if extra:
            raise LedgerError(f"{name!r} has unknown field(s): {', '.join(extra)}")
        for key in ("to_cns", "from_cns", "exempt"):
            if entry.get(key) is not None and not (isinstance(entry[key], str) and entry[key].strip()):
                raise LedgerError(f"{name!r}: {key} must be a non-empty string or absent")
        if entry.get("hub") not in (None, True):
            raise LedgerError(f"{name!r}: hub may only be true")
        if entry.get("private") not in (None, True):
            raise LedgerError(f"{name!r}: private may only be true")
        if entry.get("private") and not entry.get("to_cns"):
            raise LedgerError(f"{name!r}: private needs a to_cns proof; it only excuses a missing checkout")
        aka = entry.get("aka", [])
        if not isinstance(aka, list) or not all(isinstance(a, str) and len(a.strip()) >= 3 for a in aka):
            raise LedgerError(f"{name!r}: aka must be a list of names of at least three characters")
        via = entry.get("via")
        if via is not None:
            if not (isinstance(via, dict) and set(via) == {"repo", "module"}
                    and all(isinstance(v, str) and v.strip() for v in via.values())):
                raise LedgerError(f'{name!r}: via must be {{"repo": ..., "module": ...}}')
            via = (via["repo"], via["module"])
        links.append(Link(name, entry.get("to_cns"), entry.get("from_cns"), entry.get("exempt"),
                          bool(entry.get("hub")), tuple(aka), via, bool(entry.get("private"))))
    return links


def counts(links: Sequence[Link]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for link in links:
        out[status(link)] = out.get(status(link), 0) + 1
    return out


def _inside(root: Path, rel: str) -> Optional[Path]:
    """`rel` under `root` as a regular, non-symlink file, or None."""
    if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        return None
    path = root
    for part in Path(rel).parts:
        path = path / part
        if path.is_symlink():
            return None
    return path if path.is_file() and path.stat().st_size <= _MAX_BYTES else None


def _tree(path: Path) -> Optional[ast.AST]:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None


def _docstrings(tree: ast.AST) -> set:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _names_in_code(tree: ast.AST, needles: Sequence[str]) -> bool:
    """Whether any of `needles` appears (any case) in an identifier or a string that is not a docstring."""
    needles = [n.casefold() for n in needles]
    skip = _docstrings(tree)
    for node in ast.walk(tree):
        words: List[str] = []
        if isinstance(node, ast.Name):
            words.append(node.id)
        elif isinstance(node, ast.Attribute):
            words.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            words.append(node.name)
        elif isinstance(node, ast.arg):
            words.append(node.arg)
        elif isinstance(node, ast.alias):
            words.append(node.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            words.append(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            words.append(node.value)
        if any(n in w.casefold() for w in words for n in needles):
            return True
    return False


def _imports_cns(tree: ast.AST) -> bool:
    def is_cns(name: str) -> bool:
        return name.split(".")[0] in ("cns", "cns_composition")
    skip = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(is_cns(a.name) for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and is_cns(node.module):
            return True
        if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            target = node.args[0].value
            callee = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if callee in ("import_module", "__import__") and isinstance(target, str) and is_cns(target) \
                    and id(node.args[0]) not in skip:
                return True
    return False


def imports_module(folder: Path, root: str) -> bool:
    """Whether non-test Python under `folder` imports the top-level module `root`."""
    for path in sorted(Path(folder).rglob("*.py")):
        rel = path.relative_to(folder).parts
        if (any(p.startswith(".") or p in ("tests", "test", "node_modules", "site-packages") for p in rel)
                or rel[-1].startswith("test_") or rel[-1].endswith("_test.py") or rel[-1] == "conftest.py"
                or path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES):
            continue
        tree = _tree(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == root for a in node.names):
                return True
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module \
                    and node.module.split(".")[0] == root:
                return True
    return False


def bridge_problem(links: Sequence[Link], link: Link, stack: Optional[Path]) -> Optional[str]:
    """Why `link`'s bridge does not carry it to CNS, or None when it does."""
    if link.via is None:
        return None
    bridge_name, module = link.via
    bridge = next((x for x in links if x.repo.casefold() == bridge_name.casefold()), None)
    if bridge is None:
        return f"via names {bridge_name}, which is not in the ledger"
    if status(bridge) != "two_way":
        return f"via names {bridge_name}, which is {status(bridge)}, not two_way; a bridge must itself be connected both ways"
    if link.to_cns:
        return "has its own to_cns proof and a via; it is two_way by itself, so remove the via"
    if stack is not None and Path(stack).is_dir():
        folder = _folder(Path(stack), bridge_name)
        if folder is None:
            return f"bridge {bridge_name} has no checkout in the stack folder, so the bridge cannot be checked"
        if not imports_module(folder, module):
            return f"bridge {bridge_name}'s source does not import {module}"
    return None


def cns_side_problem(cns_root: Path, repo: str, evidence: str, aka: Sequence[str] = ()) -> Optional[str]:
    """Why `evidence` does not show CNS carrying `repo`, or None when it does."""
    top = Path(evidence).parts[0] if Path(evidence).parts else ""
    path = _inside(cns_root, evidence)
    if path is None:
        return f"from_cns proof {evidence!r} is not a file inside CNS"
    if top == "contracts" and path.suffix == ".json":
        try:
            pins = json.loads(path.read_text(encoding="utf-8")).get("repos", {})
        except (OSError, ValueError, AttributeError):
            return f"from_cns proof {evidence!r} is not readable JSON"
        if isinstance(pins, dict) and repo.casefold() in {str(k).casefold() for k in pins}:
            return None
        return f"from_cns proof {evidence!r} does not pin {repo}"
    if top == "cns_composition" and path.suffix == ".py" and "tests" not in Path(evidence).parts:
        tree = _tree(path)
        if tree is not None and _names_in_code(tree, [repo, *aka]):
            return None
        return f"from_cns proof {evidence!r} does not name {repo} in code (a docstring does not count)"
    return (f"from_cns proof {evidence!r} must be a JSON file under contracts/ or a module under cns_composition/; "
            "the cns/ package is shapes and carries no behaviour toward a repository")


def _folder(stack: Path, name: str) -> Optional[Path]:
    for p in sorted(stack.iterdir()):
        if p.is_dir() and not p.is_symlink() and p.name.casefold() == name.casefold():
            return p
    return None


def repo_side_problem(stack: Path, repo: str, evidence: str, cns_root: Optional[Path] = None) -> Optional[str]:
    """Why `evidence` does not show `repo` using CNS, or None when it does."""
    folder = _folder(stack, repo)
    if folder is None:
        return f"{repo} has no checkout in the stack folder, so to_cns cannot be checked"
    path = _inside(folder, evidence)
    if path is None:
        return f"to_cns proof {evidence!r} is not a file inside {repo}"
    if path.suffix == ".py":
        tree = _tree(path)
        if tree is not None and _imports_cns(tree):
            return None
        return f"to_cns proof {evidence!r} does not import cns or cns_composition"
    if path.suffix == ".json":
        if cns_root is None:
            return f"to_cns proof {evidence!r} is a vendored copy of CNS's digest vectors, which needs the CNS checkout to compare"
        want = _inside(Path(cns_root), "contracts/digest-vectors.json")
        try:
            same = want is not None and json.loads(path.read_text(encoding="utf-8")) == json.loads(want.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return f"to_cns proof {evidence!r} is not readable JSON"
        return None if same else f"to_cns proof {evidence!r} is not an exact copy of CNS's contracts/digest-vectors.json"
    if path.name in _DEPENDENCY_FILES or path.name.startswith("requirements"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return f"to_cns proof {evidence!r} cannot be read"
        if _DEPENDENCY.search(text):
            return None
        return f"to_cns proof {evidence!r} does not declare cns as a dependency"
    return f"to_cns proof {evidence!r} must be a Python file, a dependency file or the vendored digest vectors"


def unverified(links: Sequence[Link], stack: Optional[Path]) -> List[Link]:
    """The private repositories whose to_cns proof could not be checked because the stack has no checkout."""
    if stack is None or not Path(stack).is_dir():
        return []
    return [k for k in links if k.private and k.to_cns and _folder(Path(stack), k.repo) is None]


def problems(links: Sequence[Link], cns_root: Path, stack: Optional[Path] = None) -> List[str]:
    """Every claim in the ledger the files do not support, and every mismatch with the stack folder."""
    out: List[str] = []
    seen = set()
    for link in links:
        key = link.repo.casefold()
        if key in seen:
            out.append(f"{link.repo} is listed twice")
        seen.add(key)
        if link.hub:
            continue
        if link.exempt and (link.to_cns or link.from_cns):
            out.append(f"{link.repo} is exempt and also claims a connection; it is one or the other")
        if link.from_cns:
            why = cns_side_problem(Path(cns_root), link.repo, link.from_cns, link.aka)
            if why:
                out.append(f"{link.repo}: {why}")
        if link.via:
            why = bridge_problem(links, link, stack)
            if why:
                out.append(f"{link.repo}: {why}")
            if not link.from_cns:
                out.append(f"{link.repo}: via needs a from_cns proof; the bridge carries the repository to CNS, "
                           "CNS must still carry something back")
        if link.to_cns and stack is not None and link not in unverified(links, stack):
            why = repo_side_problem(Path(stack), link.repo, link.to_cns, Path(cns_root))
            if why:
                out.append(f"{link.repo}: {why}")
    if stack is not None:
        if not Path(stack).is_dir():
            out.append(f"the stack folder {str(stack)!r} does not exist")
        else:
            present = {p.name.casefold() for p in Path(stack).iterdir() if p.is_dir() and not p.name.startswith(".")}
            for p in sorted(present - seen):
                out.append(f"{p} is in the stack folder but not in the ledger")
    return out


def _default_ledger() -> Path:
    return Path(__file__).resolve().parents[1] / "contracts" / "cns-links.json"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.link_ledger",
        description="Check the CNS connection ledger against the files it points at.")
    parser.add_argument("--ledger", type=Path, default=None, help="default: contracts/cns-links.json beside this package")
    parser.add_argument("--cns", type=Path, default=None, help="the CNS checkout the from_cns proofs live in (default: this one)")
    parser.add_argument("--stack", type=Path, default=None,
                        help="a folder with one checkout per repository; without it only the CNS side is checked")
    parser.add_argument("--require-two-way", action="store_true",
                        help="also fail unless every repository that is not exempt is connected both ways")
    args = parser.parse_args(argv)
    ledger = args.ledger or _default_ledger()
    try:
        links = read_ledger(ledger)
    except LedgerError as err:
        print(f"link_ledger: {err}", file=sys.stderr)
        return 2
    found = problems(links, args.cns or Path(__file__).resolve().parents[1], args.stack)
    tally = counts(links)
    if args.require_two_way:
        for link in links:
            if status(link) not in ("two_way", "bridged", "exempt", "hub"):
                found.append(f"{link.repo} is {status(link)}, not two_way")
    print("link_ledger: " + ", ".join(f"{n} {k}" for k, n in sorted(tally.items())))
    skipped = unverified(links, args.stack)
    if skipped:
        print("link_ledger: not verified here (private, no checkout): " + ", ".join(k.repo for k in skipped))
    if found:
        for line in found:
            print(f"link_ledger: {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

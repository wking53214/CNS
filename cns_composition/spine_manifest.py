"""spine_manifest: which four commits, with which CNS, make one decision spine?

WHY THIS EXISTS

interconnected_alpha, interconnected_zeta, interconnected_beta and interconnected_delta pin one another by commit,
and each tests green on its own. Measured on 2026-11-04: alpha, beta and delta pinned zeta at `4ba70f6`, a commit
older than zeta's stale-observation guard, while the `chains` workflow tested the floating head of each repository,
which had that guard. So the set each repository's CI installed was not the set the end-to-end run tested, and
no job ran the set the repositories declare. Individual green CI is not integration.

`contracts/spine-manifest.json` names the one set: a commit for each of the four, and the CNS tag (with the commit
it points at) that all four use. The `spine-pinned` job in `chains.yml` checks the four out AT those commits and
runs `chains/spine_run.py`, lenient and strict, on exactly them.

WHAT IT CHECKS (`check`)

  - the manifest is well formed: the schema, exactly the four repositories of `spine_trace.SPINE`, every commit a
    full 40 character SHA, the CNS tag a version tag and its commit a full SHA;
  - the CNS commit is the one `contracts/cns-releases.json` records for that tag, so the tag cannot be moved;
  - each repository declares the dependencies the architecture allows, at the manifest's commits: alpha pins zeta,
    zeta pins nothing, beta pins zeta, delta pins zeta and beta, and no other dependency appears, in the runtime list
    or in any extra (a plain `name>=1` requirement and a URL from another host are named like any other);
    every pin is owned by `OWNER`, the repository owner, and every `cns` extra pins the manifest's tag;
  - each checkout is at the commit the manifest names (`git rev-parse HEAD`) AND is clean: `git status --porcelain` lists
    nothing, untracked files included, because HEAD naming the pinned commit says nothing about the files that are
    imported (an edited tracked file, or a planted untracked one, is named);
  - the pyproject is read as TOML. With Python 3.11 and later that is `tomllib`; on 3.10, the floor of this repository,
    a strict fallback reads only the two tables the check needs and REFUSES (a named problem) a pyproject it cannot read
    completely: a multi-line string, a repeated section or key, a bracket in a comment inside a list. A file the check
    cannot see is never a file it passes. Messages name whole 40 character commits.

pip refuses two different commit URLs for the same package, so "alpha, beta and delta pin one zeta" is not a style
rule: it is what makes the four installable together.

WHAT IT DOES NOT CHECK

That the four are the newest commits (they are meant to lag until someone moves them on purpose), or that the
repositories behave (that is `spine_run.py`). The files are read as text and never executed. A manifest with a repeated JSON key is
refused, because a reader that keeps the last one and a reader that keeps the first would see different commits.
`--installed` reads what pip recorded, so it cannot tell a distribution installed from the right commit and then edited in
place from an unedited one (no hash of the installed files is recorded for a VCS install); the checkout check above is the
one that sees edits.

THE COMMANDS

    python -m cns_composition.spine_manifest --github-output "$GITHUB_OUTPUT"   validate, write alpha= zeta= beta= delta=
    python -m cns_composition.spine_manifest --stack stack                      check pins, checked-out commits, clean trees
    python -m cns_composition.spine_manifest --installed                        check each installed distribution's direct_url.json
                                                                                commit against the manifest (importlib.metadata,
                                                                                no network), and that the package imported is that one

Exit 0 holds, 1 does not, 2 a repository the manifest names was not read.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from cns_composition import delivery
from cns_composition.spine_trace import SPINE

try:  # Python 3.11 and later; the floor of this repository is 3.10, which reads with the strict fallback below
    import tomllib as _tomllib
except ImportError:  # pragma: no cover - exercised by monkeypatching _tomllib to None in the tests
    _tomllib = None  # type: ignore[assignment]

__all__ = ["ALLOWED_EXTRAS", "DEFAULT_MANIFEST", "EXPECTED_RUNTIME", "OWNER", "SCHEMA", "check", "declared", "main", "manifest_problems", "load"]

SCHEMA = "spine-manifest/1"
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "contracts" / "spine-manifest.json"
DEFAULT_RELEASES = Path(__file__).resolve().parents[1] / "contracts" / "cns-releases.json"

#: The runtime dependencies each repository may declare, as the package name they import. Nothing else is allowed.
EXPECTED_RUNTIME: Mapping[str, Tuple[str, ...]] = {
    "interconnected_alpha": ("zeta",),
    "interconnected_zeta": (),
    "interconnected_beta": ("zeta",),
    "interconnected_delta": ("beta", "zeta"),
}
#: What each optional extra may hold, by normalised distribution name. `dev` is tooling; `cns` is the CNS pin.
ALLOWED_EXTRAS: Mapping[str, Tuple[str, ...]] = {"cns": ("cns",), "dev": ("pytest",)}
#: The GitHub owner of the four repositories and of CNS. Every direct-URL pin must name it.
OWNER = "wking53214"
#: The package a runtime dependency name refers to.
_PACKAGE_REPO = {"zeta": "interconnected_zeta", "beta": "interconnected_beta"}

# Matched with fullmatch: `$` also matches before a trailing newline, and `\d` matches non-ASCII digits.
_SHA = re.compile(r"[0-9a-f]{40}")
_TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
_DEP = re.compile(
    r"""\s*(?P<name>[A-Za-z0-9_.-]+)\s*(?:\[[^\]]*\])?\s*@\s*git\+https://github\.com/"""
    r"""(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?@(?P<ref>[0-9A-Za-z._/-]+)\s*"""
)


def _no_duplicate_keys(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def load(path: Path = DEFAULT_MANIFEST) -> Dict[str, object]:
    """The manifest as read. A file that is not JSON, or not an object, raises ValueError."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path} cannot be read as JSON: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{path} is refused: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def manifest_problems(manifest: Mapping[str, object], releases: Optional[Mapping[str, object]] = None) -> List[str]:
    """What is wrong with the manifest itself. Empty when it is well formed."""
    out: List[str] = []
    if manifest.get("schema") != SCHEMA:
        out.append(f"schema is {manifest.get('schema')!r}; this check speaks {SCHEMA!r}")
    repos = manifest.get("repos")
    if not isinstance(repos, Mapping):
        out.append("repos must be an object")
        repos = {}
    if set(repos) != set(SPINE):
        out.append(f"repos must be exactly {sorted(SPINE)}; got {sorted(map(str, repos))}")
    for name, commit in repos.items():
        if not isinstance(commit, str) or not _SHA.fullmatch(commit):
            out.append(f"repos.{name} must be a full 40 character lowercase commit SHA")
    cns = manifest.get("cns")
    if not isinstance(cns, Mapping):
        out.append("cns must be an object with a tag and a commit")
    else:
        tag, commit = cns.get("tag"), cns.get("commit")
        if not isinstance(tag, str) or not _TAG.fullmatch(tag):
            out.append("cns.tag must be a release tag such as v2.3.0")
        if not isinstance(commit, str) or not _SHA.fullmatch(commit):
            out.append("cns.commit must be a full 40 character lowercase commit SHA")
        if releases is not None and isinstance(tag, str) and isinstance(commit, str):
            rows = releases.get("releases")
            known = {r.get("ref"): r.get("commit") for r in rows if isinstance(r, Mapping)} if isinstance(rows, list) else {}
            if tag not in known:
                out.append(f"cns.tag {tag} is not in contracts/cns-releases.json")
            elif known[tag] != commit:
                out.append(f"cns.commit {commit} is not the commit {tag} points at in contracts/cns-releases.json "
                           f"({known[tag]}); a tag that moved would change what the four install")
    return out


_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


def _skip_inline_table(lines: List[str], i: int, col: int) -> int:
    """The line index after a one-line inline table that starts at lines[i][col]. Its content is not read."""
    line = lines[i]
    braces = 0
    while col < len(line):
        ch = line[col]
        if line.startswith('"""', col) or line.startswith("'''", col):
            raise ValueError(f"line {i + 1}: a multi-line string")
        if ch in "\"'":
            end = line.find(ch, col + 1)
            if end < 0:
                raise ValueError(f"line {i + 1}: an unterminated string")
            col = end + 1
            continue
        if ch == "{":
            braces += 1
        elif ch == "}":
            braces -= 1
            if braces == 0:
                rest = line[col + 1:].strip()
                if rest and not rest.startswith("#"):
                    raise ValueError(f"line {i + 1}: text after an inline table")
                return i + 1
        col += 1
    raise ValueError(f"line {i + 1}: an inline table that does not end on its line")


def _scan_value(lines: List[str], index: int, start: int, bracket_comments_refused: bool) -> Tuple[Optional[List[str]], int]:
    """Scan one TOML value that begins at lines[index][start:].

    Returns (strings, next line index). `strings` is the list of quoted strings when the value is an array of basic or
    literal single-line strings, and None for any other single-line scalar. A multi-line string, an unterminated string
    or array, an escape in a string, an element that is not a string, or (when asked) a bracket in a comment inside an
    array raises ValueError: the fallback reads only what it can read completely.
    """
    depth = 0
    items: List[str] = []
    is_array = False
    i, col = index, start
    while i < len(lines):
        line = lines[i]
        while col < len(line):
            ch = line[col]
            if line.startswith('"""', col) or line.startswith("'''", col):
                raise ValueError(f"line {i + 1}: a multi-line string")
            if ch in "\"'":
                end = line.find(ch, col + 1)
                if end < 0:
                    raise ValueError(f"line {i + 1}: an unterminated string")
                body = line[col + 1:end]
                if ch == '"' and "\\" in body:
                    raise ValueError(f"line {i + 1}: an escape inside a string")
                if depth == 1:
                    items.append(body)
                elif depth == 0 and not is_array:
                    return None, i + 1
                else:
                    raise ValueError(f"line {i + 1}: a nested value")
                col = end + 1
                continue
            if ch == "#":
                if bracket_comments_refused and depth > 0 and ("[" in line[col:] or "]" in line[col:]):
                    raise ValueError(f"line {i + 1}: a bracket in a comment inside a list")
                break
            if ch == "[":
                if depth > 0:
                    raise ValueError(f"line {i + 1}: a nested list")
                depth, is_array = 1, True
            elif ch == "]":
                if depth == 0:
                    raise ValueError(f"line {i + 1}: an unexpected ]")
                depth = 0
                rest = line[col + 1:].strip()
                if rest and not rest.startswith("#"):
                    raise ValueError(f"line {i + 1}: text after the end of a list")
                return items, i + 1
            elif ch == "{":
                if depth > 0 or is_array:
                    raise ValueError(f"line {i + 1}: an inline table inside a list")
                return None, _skip_inline_table(lines, i, col)
            elif depth > 0 and ch not in " \t,":
                raise ValueError(f"line {i + 1}: a list element that is not a string")
            elif depth == 0 and not is_array and ch not in " \t":
                return None, i + 1  # a scalar (number, boolean, date): not a requirement, not read
            col += 1
        if depth == 0 and not is_array:
            raise ValueError(f"line {index + 1}: a key with no value")
        i += 1
        col = 0
    raise ValueError(f"line {index + 1}: a list that is never closed")


def _fallback_view(text: str) -> Dict[str, Any]:
    """The part of a pyproject.toml the checks use, read without tomllib. Anything it cannot read completely raises."""
    lines = text.splitlines()
    section = ""
    seen: List[str] = []
    project: Dict[str, Any] = {}
    optional: Dict[str, List[str]] = {}
    keys: Dict[str, set] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if stripped.startswith("["):
            m = re.fullmatch(r"\[\s*([A-Za-z0-9_.-]+)\s*\]\s*(?:#.*)?", stripped)
            if not m:
                if stripped.startswith("[["):
                    section = "[[" + stripped + "]]"
                    i += 1
                    continue
                raise ValueError(f"line {i + 1}: a table header this reader does not understand")
            section = re.sub(r"\s+", "", m.group(1))
            if section in seen:
                raise ValueError(f"line {i + 1}: the section [{section}] appears twice")
            seen.append(section)
            keys[section] = set()
            i += 1
            continue
        eq = line.find("=")
        if eq < 0:
            raise ValueError(f"line {i + 1}: a line that is neither a header nor a key")
        key = line[:eq].strip()
        watched = section in ("project", "project.optional-dependencies")
        if section == "":
            raise ValueError(f"line {i + 1}: a key before any section header")
        if watched and not _BARE_KEY.fullmatch(key):
            raise ValueError(f"line {i + 1}: a key this reader does not understand: {key!r}")
        values, i = _scan_value(lines, i, eq + 1, watched)
        if not watched:
            continue
        if key in keys[section]:
            raise ValueError(f"the key {key!r} appears twice in [{section}]")
        keys[section].add(key)
        if section == "project" and key in ("dependencies", "dynamic", "optional-dependencies"):
            if values is None:
                raise ValueError(f"[project] {key} is not a list of strings")
            project[key] = values
        elif section == "project.optional-dependencies":
            if values is None:
                raise ValueError(f"[project.optional-dependencies] {key} is not a list of strings")
            optional[key] = values
    if "optional-dependencies" in project:
        raise ValueError("[project] optional-dependencies is written as an inline value this reader does not read")
    return {"dependencies": project.get("dependencies"), "dynamic": project.get("dynamic", []), "optional": optional}


def _view(text: str) -> Dict[str, Any]:
    """{"dependencies": list or None, "dynamic": list, "optional": {extra: list}} from tomllib, else the strict fallback.

    ValueError when the text cannot be read completely: a pyproject the checks cannot see is not a pyproject they pass.
    """
    if _tomllib is None:
        return _fallback_view(text)
    try:
        data = _tomllib.loads(text)
    except _tomllib.TOMLDecodeError as exc:
        raise ValueError(f"not valid TOML: {exc}") from exc
    project = data.get("project", {})
    if not isinstance(project, dict):
        raise ValueError("[project] is not a table")
    deps = project.get("dependencies")
    optional = project.get("optional-dependencies", {})
    dynamic = project.get("dynamic", [])

    def strings(value: Any, what: str) -> List[str]:
        if not isinstance(value, list) or not all(type(x) is str for x in value):
            raise ValueError(f"{what} is not a list of strings")
        return list(value)

    if not isinstance(optional, dict):
        raise ValueError("[project.optional-dependencies] is not a table")
    return {"dependencies": None if deps is None else strings(deps, "dependencies"),
            "dynamic": strings(dynamic, "dynamic"),
            "optional": {str(k): strings(v, f"optional-dependencies.{k}") for k, v in optional.items()}}


def _pins(items: Sequence[str]) -> Dict[str, Tuple[str, str]]:
    found: Dict[str, Tuple[str, str]] = {}
    for item in items:
        m = _DEP.fullmatch(item)
        if m:
            found[m.group("name").lower()] = (m.group("repo"), m.group("ref"))
    return found


def _owners(items: Sequence[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in items:
        m = _DEP.fullmatch(item)
        if m:
            out[m.group("name").lower()] = m.group("owner")
    return out


def _requirements(items: Sequence[str]) -> List[Tuple[str, str]]:
    """Every requirement in a list, as (normalised name, text). Direct URL or not, any host."""
    found: List[Tuple[str, str]] = []
    for item in items:
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", item)
        found.append((re.sub(r"[-_.]+", "-", m.group(1)).lower() if m else item.strip(), item))
    return found


def _flat_optional(view: Mapping[str, Any]) -> List[str]:
    return [item for items in view["optional"].values() for item in items]


def declared(pyproject_text: str) -> Dict[str, Dict[str, Tuple[str, str]]]:
    """The direct URL pins in a pyproject.toml: {"runtime": {name: (repo, ref)}, "optional": {...}}.

    Read with tomllib when it exists (Python 3.11 and later). On 3.10, where it does not, a strict fallback reads
    only the two tables the checks need and raises ValueError on anything it cannot read completely (a multi-line
    string, a repeated section or key, a bracket in a comment inside a list), so a construct that could hide a
    requirement is refused, never skipped.
    """
    view = _view(pyproject_text)
    return {"runtime": _pins(view["dependencies"] or []), "optional": _pins(_flat_optional(view))}


def _head(path: Path) -> Optional[str]:
    try:
        done = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _status(path: Path) -> Optional[List[str]]:
    """The lines of `git status --porcelain` (untracked files listed one by one), or None when git cannot say."""
    try:
        done = subprocess.run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.splitlines() if done.returncode == 0 else None


def check(
    manifest: Mapping[str, object],
    pyprojects: Mapping[str, str],
    heads: Optional[Mapping[str, Optional[str]]] = None,
    releases: Optional[Mapping[str, object]] = None,
    dirty: Optional[Mapping[str, Optional[Sequence[str]]]] = None,
) -> List[str]:
    """Every way the four repositories' declarations, or checkouts, disagree with the manifest.

    `dirty`, when given, maps each repository to the lines of `git status --porcelain` for its checkout (None when
    they could not be read): any line, an untracked file included, is a problem, because HEAD naming the pinned
    commit says nothing about the files that are actually imported.
    """
    out = manifest_problems(manifest, releases)
    if out:
        return out
    repos = manifest["repos"]
    cns = manifest["cns"]
    assert isinstance(repos, Mapping) and isinstance(cns, Mapping)
    for repo in SPINE:
        text = pyprojects.get(repo)
        if text is None:
            out.append(f"{repo}: pyproject.toml was not read")
            continue
        try:
            view = _view(text)
        except ValueError as exc:
            out.append(f"{repo}: pyproject.toml cannot be read completely ({exc}); a file the check cannot read is not a file it passes")
            continue
        found = {"runtime": _pins(view["dependencies"] or []), "optional": _pins(_flat_optional(view))}
        allowed = set(EXPECTED_RUNTIME[repo])
        for field in view["dynamic"]:
            if field in ("dependencies", "optional-dependencies"):
                out.append(f"{repo} declares {field} as dynamic, which the check cannot read from pyproject.toml")
        runtime = _requirements(view["dependencies"] or [])
        extra = sorted({name for name, _ in runtime} - allowed)
        if extra:
            out.append(f"{repo} declares runtime dependenc(ies) the spine does not allow: {', '.join(extra)}")
        for name, requirement in runtime:
            if name in allowed and name not in found["runtime"]:
                out.append(f"{repo} pins {name} other than by a git+https://github.com/ direct URL: {requirement!r}")
        for extra_name, items in sorted(view["optional"].items()):
            for name, requirement in _requirements(items):
                if name not in ALLOWED_EXTRAS.get(extra_name, ()):
                    out.append(f"{repo} extra [{extra_name}] declares {name}, which the spine does not allow: {requirement!r}")
                elif "@" in requirement and name not in found["optional"]:
                    out.append(f"{repo} extra [{extra_name}] pins {name} other than by a git+https://github.com/ direct URL: {requirement!r}")
        owners = _owners(view["dependencies"] or [])
        owners.update({f"{n} (extra)": o for n, o in _owners(_flat_optional(view)).items()})
        for name, owner in sorted(owners.items()):
            if owner.lower() != OWNER.lower():
                out.append(f"{repo} pins {name} from owner {owner!r}, not {OWNER!r}")
        for name in sorted(allowed):
            if name not in found["runtime"]:
                if not any(n == name for n, _ in runtime):
                    out.append(f"{repo} does not pin {name}")
                continue
            target, ref = found["runtime"][name]
            want_repo = _PACKAGE_REPO[name]
            if target.lower() != want_repo.lower():
                out.append(f"{repo} pins {name} from {target}, not {want_repo}")
            if ref != repos[want_repo]:
                out.append(f"{repo} pins {name} at {ref} but the manifest names {repos[want_repo]}")
        cns_pin = found["optional"].get("cns")
        if cns_pin is None:
            out.append(f"{repo} has no cns extra pinned by tag")
        elif cns_pin[1] != cns["tag"]:
            out.append(f"{repo}'s cns extra pins {cns_pin[1]} but the manifest names {cns['tag']}")
        if heads is not None:
            head = heads.get(repo)
            if head is None:
                out.append(f"{repo}: the checked-out commit could not be read")
            elif head != repos[repo]:
                out.append(f"{repo} is checked out at {head} but the manifest names {repos[repo]}")
        if dirty is not None:
            changes = dirty.get(repo)
            if changes is None:
                out.append(f"{repo}: the checkout status could not be read")
            elif changes:
                out.append(f"{repo} has {len(changes)} uncommitted or untracked change(s) in its checkout "
                           f"(first: {changes[0].strip()!r}); HEAD is the manifest's commit but the files are not")
    return out


#: The search path `--installed` reads; None means `sys.path`. A test points it at a folder of dist-info directories.
_SEARCH_PATH: Optional[List[str]] = None


def _normal(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_installed(path: Optional[Sequence[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """What is installed for each spine package (and for `cns`), read from the distributions' metadata and nothing else.

    {package: [record, ...]} with one record per distribution of that name on the path. A record holds `direct_url` (the
    parsed direct_url.json pip writes for a VCS, archive or directory install, None when the file is absent),
    `direct_url_error` when it is present but cannot be read, `location` (the folder holding the dist-info) and
    `imported_from` (where `import <package>` would find the package, found without importing it). No network, no code run.
    """
    wanted = {_normal(pkg): pkg for pkg in (*SPINE.values(), "cns")}
    found: Dict[str, List[Dict[str, Any]]] = {pkg: [] for pkg in wanted.values()}
    search = list(path) if path is not None else (list(_SEARCH_PATH) if _SEARCH_PATH is not None else list(sys.path))
    for dist in importlib.metadata.distributions(path=search):
        name = dist.metadata["Name"]
        if not isinstance(name, str) or _normal(name) not in wanted:
            continue
        package = wanted[_normal(name)]
        record: Dict[str, Any] = {"direct_url": None, "location": str(Path(str(dist.locate_file(""))).resolve())}
        raw = dist.read_text("direct_url.json")
        if raw is not None:
            try:
                record["direct_url"] = json.loads(raw)
            except ValueError as exc:
                record["direct_url_error"] = str(exc)
        spec = importlib.machinery.PathFinder.find_spec(package, search)
        origin = None
        if spec is not None:
            origin = spec.origin if spec.origin not in (None, "namespace") else next(iter(spec.submodule_search_locations or []), None)
        record["imported_from"] = str(Path(origin).resolve()) if origin else None
        found[package].append(record)
    return found


def installed_problems(manifest: Mapping[str, object], installed: Mapping[str, Sequence[Mapping[str, Any]]]) -> List[str]:
    """Every way what is installed differs from what the manifest names: a missing, duplicated or shadowed distribution, an
    install that records no commit (an index release, a wheel, an editable directory), a source other than the owner's
    repository, or a commit that is not the manifest's. `cns`, when installed from a VCS URL, is held to the manifest's CNS commit."""
    out = manifest_problems(manifest)
    if out:
        return out
    repos = manifest["repos"]
    cns = manifest["cns"]
    assert isinstance(repos, Mapping) and isinstance(cns, Mapping)
    for repo, package in SPINE.items():
        records = installed.get(package, [])
        if not records:
            out.append(f"{package} is not installed (no distribution of that name on the search path)")
            continue
        if len(records) > 1:
            out.append(f"{package} is installed twice ({len(records)} distributions on the search path); which one is imported depends on path order")
        record = records[0]
        direct = record.get("direct_url")
        want_url = f"https://github.com/{OWNER}/{repo}"
        if "direct_url_error" in record:
            out.append(f"{package}: direct_url.json cannot be read ({record['direct_url_error']})")
        elif not isinstance(direct, Mapping):
            out.append(f"{package} was not installed from a direct URL, so no commit was recorded "
                       "(an index release, a wheel file, or an installer that does not write direct_url.json)")
        elif "dir_info" in direct:
            out.append(f"{package} was installed from a directory (editable or local), which records no commit")
        elif not isinstance(direct.get("vcs_info"), Mapping) or direct["vcs_info"].get("vcs") != "git":
            out.append(f"{package} was installed from an archive or another kind of source, which records no commit")
        else:
            url = direct.get("url")
            if not isinstance(url, str) or re.sub(r"(\.git)?/*$", "", url).lower() != want_url.lower():
                out.append(f"{package} was installed from {url}, not {want_url}")
            commit = direct["vcs_info"].get("commit_id")
            if not isinstance(commit, str) or not _SHA.fullmatch(commit):
                out.append(f"{package} records no full commit in direct_url.json (commit_id is {commit!r})")
            elif commit != repos[repo]:
                out.append(f"{package} is installed from commit {commit} but the manifest names {repos[repo]}")
        origin, location = record.get("imported_from"), record.get("location")
        if origin is None:
            out.append(f"{package} is installed but cannot be found for import on the search path")
        elif isinstance(location, str) and Path(origin) != Path(location) and Path(location) not in Path(origin).parents:
            out.append(f"{package} would be imported from {origin}, not from the installed distribution at {location}; "
                       "a path entry shadows what was installed")
    for record in installed.get("cns", [])[:1]:
        direct = record.get("direct_url")
        info = direct.get("vcs_info") if isinstance(direct, Mapping) else None
        if isinstance(info, Mapping) and info.get("commit_id") != cns["commit"]:
            out.append(f"cns is installed from commit {info.get('commit_id')} but the manifest names {cns['commit']}")
    return out


def _main(argv: Optional[Sequence[str]]) -> int:
    parser = argparse.ArgumentParser(description="Hold the four decision-spine repositories to contracts/spine-manifest.json.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--releases", type=Path, default=DEFAULT_RELEASES)
    parser.add_argument("--stack", type=Path, help="a folder holding one checkout per repository")
    parser.add_argument("--installed", action="store_true",
                        help="hold the installed distributions (importlib.metadata, direct_url.json; no network) to the manifest's commits")
    parser.add_argument("--github-output", type=Path, help="validate the manifest and write one `package=commit` line each")
    args = parser.parse_args(argv)
    try:
        manifest = load(args.manifest)
        releases: Optional[Mapping[str, object]] = load(args.releases)
    except ValueError as exc:
        print(f"spine_manifest: {exc}", file=sys.stderr)
        return 1
    if args.github_output is not None:
        found = manifest_problems(manifest, releases)
        for problem in found:
            print(f"spine_manifest: {problem}", file=sys.stderr)
        if found:
            return 1
        repos = manifest["repos"]
        assert isinstance(repos, Mapping)
        with args.github_output.open("a", encoding="utf-8") as handle:
            for repo, package in SPINE.items():
                handle.write(f"{package}={repos[repo]}\n")
        return 0
    if args.installed:
        found = installed_problems(manifest, read_installed())
        for problem in found:
            print(f"spine_manifest: {problem}", file=sys.stderr)
        if found:
            return 1
        print("spine_manifest: every spine distribution is installed from the manifest's commit, and is the one that imports")
        return 0
    if args.stack is None:
        print("spine_manifest: give --stack, --installed or --github-output", file=sys.stderr)
        return 1
    texts: Dict[str, str] = {}
    heads: Dict[str, Optional[str]] = {}
    dirty: Dict[str, Optional[List[str]]] = {}
    for repo in SPINE:
        folder = args.stack / repo
        try:
            texts[repo] = (folder / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            continue
        heads[repo] = _head(folder)
        dirty[repo] = _status(folder)
    if len(texts) != len(SPINE):
        missing = sorted(set(SPINE) - set(texts))
        print(f"spine_manifest: read {len(texts)} of {len(SPINE)} repositories; missing: {', '.join(missing)}", file=sys.stderr)
        return 2
    found = check(manifest, texts, heads, releases, dirty=dirty)
    for problem in found:
        print(f"spine_manifest: {problem}", file=sys.stderr)
    if found:
        return 1
    print(f"spine_manifest: read {len(texts)} repositories; every pin is the manifest's and every checkout is at the manifest's commit with no uncommitted or untracked file")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "spine_manifest")


if __name__ == "__main__":
    raise SystemExit(main())

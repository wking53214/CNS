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
  - each checkout is at the commit the manifest names (`git rev-parse HEAD`).

pip refuses two different commit URLs for the same package, so "alpha, beta and delta pin one zeta" is not a style
rule: it is what makes the four installable together.

WHAT IT DOES NOT CHECK

That the four are the newest commits (they are meant to lag until someone moves them on purpose), or that the
repositories behave (that is `spine_run.py`). The files are read as text and never executed. A manifest with a repeated JSON key is
refused, because a reader that keeps the last one and a reader that keeps the first would see different commits.

THE COMMANDS

    python -m cns_composition.spine_manifest --github-output "$GITHUB_OUTPUT"   validate, write alpha= zeta= beta= delta=
    python -m cns_composition.spine_manifest --stack stack                      check pins and checked-out commits

Exit 0 holds, 1 does not, 2 a repository the manifest names was not read.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from cns_composition import delivery
from cns_composition.spine_trace import SPINE

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
    r"""["']\s*(?P<name>[A-Za-z0-9_.-]+)\s*(?:\[[^\]]*\])?\s*@\s*git\+https://github\.com/"""
    r"""(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?@(?P<ref>[0-9A-Za-z._/-]+)["']"""
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
                out.append(f"cns.commit {commit[:12]} is not the commit {tag} points at in contracts/cns-releases.json "
                           f"({str(known[tag])[:12]}); a tag that moved would change what the four install")
    return out


def _section_bodies(text: str) -> Dict[str, str]:
    bodies: Dict[str, List[str]] = {}
    current = ""
    for line in text.splitlines():
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            current = header.group(1).strip()
            bodies.setdefault(current, [])
        else:
            bodies.setdefault(current, []).append(line)
    return {name: "\n".join(lines) for name, lines in bodies.items()}


def _uncommented(text: str) -> str:
    return re.sub(r"(?m)^\s*#.*$|\s#[^\"']*$", "", text)


def _pins(text: str) -> Dict[str, Tuple[str, str]]:
    found: Dict[str, Tuple[str, str]] = {}
    for m in _DEP.finditer(_uncommented(text)):
        found[m.group("name").lower()] = (m.group("repo"), m.group("ref"))
    return found


def _owners(text: str) -> Dict[str, str]:
    return {m.group("name").lower(): m.group("owner") for m in _DEP.finditer(_uncommented(text))}


def _requirements(list_body: str) -> List[Tuple[str, str]]:
    """Every quoted requirement in a list body, as (normalised name, text). Direct URL or not, any host."""
    found: List[Tuple[str, str]] = []
    for item in re.findall(r"[\"']([^\"']+)[\"']", _uncommented(list_body)):
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", item)
        found.append((re.sub(r"[-_.]+", "-", m.group(1)).lower() if m else item.strip(), item))
    return found


def _extras(section_body: str) -> Dict[str, List[Tuple[str, str]]]:
    return {m.group(1): _requirements(m.group(2))
            for m in re.finditer(r"(?ms)^([A-Za-z0-9_.-]+)\s*=\s*\[(.*?)\]\s*$", _uncommented(section_body))}


def declared(pyproject_text: str) -> Dict[str, Dict[str, Tuple[str, str]]]:
    """The direct URL pins in a pyproject.toml, read as text: {"runtime": {name: (repo, ref)}, "optional": {...}}.

    Only `dependencies = [...]` under [project] is runtime; everything under [project.optional-dependencies] is
    optional. tomllib needs Python 3.11 and the floor of the four repositories is 3.9, so this reads text.
    """
    bodies = _section_bodies(pyproject_text)
    listed = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]\s*$", bodies.get("project", ""))
    return {
        "runtime": _pins(listed.group(1)) if listed else {},
        "optional": _pins(bodies.get("project.optional-dependencies", "")),
    }


def _head(path: Path) -> Optional[str]:
    try:
        done = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def check(
    manifest: Mapping[str, object],
    pyprojects: Mapping[str, str],
    heads: Optional[Mapping[str, Optional[str]]] = None,
    releases: Optional[Mapping[str, object]] = None,
) -> List[str]:
    """Every way the four repositories' declarations, or checkouts, disagree with the manifest."""
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
        found = declared(text)
        allowed = set(EXPECTED_RUNTIME[repo])
        bodies = _section_bodies(text)
        listed = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]\s*$", bodies.get("project", ""))
        runtime = _requirements(listed.group(1)) if listed else []
        extra = sorted({name for name, _ in runtime} - allowed)
        if extra:
            out.append(f"{repo} declares runtime dependenc(ies) the spine does not allow: {', '.join(extra)}")
        for name, requirement in runtime:
            if name in allowed and name not in found["runtime"]:
                out.append(f"{repo} pins {name} other than by a git+https://github.com/ direct URL: {requirement!r}")
        for extra_name, requirements in sorted(_extras(bodies.get("project.optional-dependencies", "")).items()):
            for name, requirement in requirements:
                if name not in ALLOWED_EXTRAS.get(extra_name, ()):
                    out.append(f"{repo} extra [{extra_name}] declares {name}, which the spine does not allow: {requirement!r}")
                elif "@" in requirement and name not in found["optional"]:
                    out.append(f"{repo} extra [{extra_name}] pins {name} other than by a git+https://github.com/ direct URL: {requirement!r}")
        owners = _owners(listed.group(1) if listed else "")
        owners.update({f"{n} (extra)": o for n, o in _owners(bodies.get("project.optional-dependencies", "")).items()})
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
                out.append(f"{repo} pins {name} at {ref[:12]} but the manifest names {str(repos[want_repo])[:12]}")
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
                out.append(f"{repo} is checked out at {head[:12]} but the manifest names {str(repos[repo])[:12]}")
    return out


def _main(argv: Optional[Sequence[str]]) -> int:
    parser = argparse.ArgumentParser(description="Hold the four decision-spine repositories to contracts/spine-manifest.json.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--releases", type=Path, default=DEFAULT_RELEASES)
    parser.add_argument("--stack", type=Path, help="a folder holding one checkout per repository")
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
    if args.stack is None:
        print("spine_manifest: give --stack or --github-output", file=sys.stderr)
        return 1
    texts: Dict[str, str] = {}
    heads: Dict[str, Optional[str]] = {}
    for repo in SPINE:
        folder = args.stack / repo
        try:
            texts[repo] = (folder / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            continue
        heads[repo] = _head(folder)
    if len(texts) != len(SPINE):
        missing = sorted(set(SPINE) - set(texts))
        print(f"spine_manifest: read {len(texts)} of {len(SPINE)} repositories; missing: {', '.join(missing)}", file=sys.stderr)
        return 2
    found = check(manifest, texts, heads, releases)
    for problem in found:
        print(f"spine_manifest: {problem}", file=sys.stderr)
    if found:
        return 1
    print(f"spine_manifest: read {len(texts)} repositories; every pin and every checkout is the manifest's")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "spine_manifest")


if __name__ == "__main__":
    raise SystemExit(main())

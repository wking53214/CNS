"""evidence_bundle: one reproducible JSON record of what was checked, on which commits, with what result.

WHY THIS EXISTS

A claim that the decision spine passes is only checkable by someone else if they can see exactly which four commits and which CNS commit
were run, whether each checkout was clean, what the manifest said, and what every run printed. This module writes that record. Two people who
check out the same commits and run the same command get the same record (the record carries no clock, no host name and no path), and
`verify` recomputes the record's digest so an edited record is refused.

WHAT IT RECORDS

  - the manifest as read, and the CNS checkout's commit and cleanliness;
  - for each of the four repositories: the commit the manifest names, the commit actually checked out, whether the checkout is clean (the same
    reads `spine_manifest` uses), and every tag that points at that commit;
  - every problem `spine_manifest.check` finds (an empty list is the pass);
  - when Python interpreters are named (`--python`, repeatable): for each, the exit status and the ok and other counts of
    `chains/spine_run.py`, and the exit status and last summary line of each repository's own test suite, run with the four checkouts and CNS on
    the path;
  - `not_established`: what a record like this cannot show (see below);
  - `bundle_digest`: SHA-256 of the canonical JSON of everything above.

WHAT IT DOES NOT ESTABLISH

The digest is a label for comparison, not a MAC: anyone can write a record and its digest. It shows what was run and what it printed on one
machine; it does not show that the machine told the truth, that the commits are the ones a third party reviewed, or that the repositories
behave beyond what their tests assert. A reader who needs more reruns the commands.

THE COMMAND

    python -m cns_composition.evidence_bundle --stack stack [--python /path/to/python ...] [--out FILE]

Exit 0 when the manifest check is empty and every named run exited 0; 1 when it is not; 2 when a repository could not be read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from . import spine_manifest as sm
from .spine_trace import SPINE

SCHEMA = "spine-evidence/1"

NOT_ESTABLISHED = (
    "the digest is a label for comparison, not a MAC: anyone can write a record and its digest",
    "that the machine that produced this record reported its own runs truthfully",
    "that the commits named are the ones any third party reviewed",
    "that a pack, producer or origin identity is authentic (all are the producer's own claim)",
    "behaviour the repositories' tests do not assert",
)

#: How a run is made: (python, argv, environment, working directory) -> (exit status, standard output and error as text).
Runner = Callable[[str, Sequence[str], Mapping[str, str], Path], "tuple[int, str]"]


def _subprocess_runner(python: str, argv: Sequence[str], env: Mapping[str, str], cwd: Path) -> "tuple[int, str]":
    done = subprocess.run([python, *argv], cwd=str(cwd), env=dict(env), capture_output=True, text=True, timeout=3600)
    return done.returncode, done.stdout + done.stderr


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_of(body: Mapping[str, Any]) -> str:
    """SHA-256 of the record without its own digest field."""
    return hashlib.sha256(_canonical({k: v for k, v in body.items() if k != "bundle_digest"})).hexdigest()


def verify(bundle: Mapping[str, Any]) -> List[str]:
    """Why a record is not what it says it is: an unknown schema, or a digest that does not match its contents."""
    out: List[str] = []
    if bundle.get("schema") != SCHEMA:
        out.append(f"schema is {bundle.get('schema')!r}, not {SCHEMA!r}")
    if bundle.get("bundle_digest") != digest_of(bundle):
        out.append("bundle_digest does not match the record's contents")
    return out


def _tags_at(folder: Path) -> Optional[List[str]]:
    lines = sm._git_lines(folder, "tag", "--points-at", "HEAD")
    return None if lines is None else sorted(t.strip() for line in lines for t in line.split("\n") if t.strip())


def _suite_summary(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _counts(text: str) -> Dict[str, int]:
    ok = sum(1 for ln in text.splitlines() if ln.startswith("ok "))
    other = sum(1 for ln in text.splitlines() if ln.strip() and not ln.startswith("ok "))
    return {"ok": ok, "other": other}


def _python_version(python: str, runner: Runner, cwd: Path) -> str:
    code, text = runner(python, ["-c", "import platform; print(platform.python_version())"], os.environ, cwd)
    return text.strip().splitlines()[-1] if code == 0 and text.strip() else "unknown"


def run_checks(stack: Path, cns_root: Path, pythons: Sequence[str], runner: Runner = _subprocess_runner) -> List[Dict[str, Any]]:
    """For each interpreter: the runner's counts and each repository's own suite, with the four checkouts and CNS on the path."""
    path = os.pathsep.join([str(stack / repo) for repo in SPINE] + [str(cns_root)])
    env = {**os.environ, "PYTHONPATH": path, "PYTHONDONTWRITEBYTECODE": "1"}
    runs: List[Dict[str, Any]] = []
    for python in pythons:
        code, text = runner(python, ["chains/spine_run.py"], env, cns_root)
        suites = {}
        for repo in SPINE:
            suite_code, suite_text = runner(python, ["-m", "pytest", "-q", "-p", "no:cacheprovider"], env, stack / repo)
            suites[repo] = {"exit": suite_code, "summary": re.sub(r" in [0-9.]+s.*$", "", _suite_summary(suite_text))}
        runs.append({"python": _python_version(python, runner, cns_root), "runner": {"exit": code, **_counts(text)}, "suites": suites})
    return runs


def collect(
    stack: Path,
    cns_root: Path,
    manifest: Mapping[str, Any],
    releases: Optional[Mapping[str, Any]] = None,
    runs: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """The record, with its digest. Reads the checkouts; runs nothing."""
    texts: Dict[str, str] = {}
    heads: Dict[str, Optional[str]] = {}
    dirty: Dict[str, Optional[List[str]]] = {}
    repos: Dict[str, Any] = {}
    declared = manifest.get("repos")
    expected: Mapping[str, Any] = declared if isinstance(declared, Mapping) else {}
    for repo in SPINE:
        folder = stack / repo
        try:
            texts[repo] = (folder / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            pass
        heads[repo] = sm._head(folder)
        dirty[repo] = sm._status(folder)
        repos[repo] = {"expected": expected.get(repo), "head": heads[repo], "dirty": dirty[repo], "tags": _tags_at(folder)}
    problems = sm.check(manifest, texts, heads, releases, dirty=dirty)
    cns_status = sm._status(cns_root)
    body: Dict[str, Any] = {
        "schema": SCHEMA,
        "manifest": manifest,
        "cns": {"head": sm._head(cns_root), "dirty": cns_status},
        "repos": repos,
        "problems": problems,
        "runs": list(runs or []),
        "not_established": list(NOT_ESTABLISHED),
    }
    body["bundle_digest"] = digest_of(body)
    return body


def passed(bundle: Mapping[str, Any]) -> bool:
    """True when the manifest check is empty, the CNS checkout is clean, and every recorded run exited 0."""
    if bundle.get("problems") or bundle.get("cns", {}).get("dirty") not in ([],):
        return False
    for run in bundle.get("runs", []):
        if run["runner"]["exit"] != 0 or run["runner"]["other"] != 0:
            return False
        if any(suite["exit"] != 0 for suite in run["suites"].values()):
            return False
    return not verify(bundle)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Write the reproducible evidence record for the four decision-spine repositories.")
    parser.add_argument("--stack", type=Path, required=True, help="a folder holding one checkout per repository")
    parser.add_argument("--cns-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=sm.DEFAULT_MANIFEST)
    parser.add_argument("--releases", type=Path, default=sm.DEFAULT_RELEASES)
    parser.add_argument("--python", action="append", default=[], help="an interpreter to run the runner and the four suites with (repeatable)")
    parser.add_argument("--out", type=Path, help="write the record here instead of standard output")
    args = parser.parse_args(argv)
    try:
        manifest = sm.load(args.manifest)
        releases: Optional[Mapping[str, Any]] = sm.load(args.releases)
    except ValueError as exc:
        print(f"evidence_bundle: {exc}", file=sys.stderr)
        return 2
    missing = [repo for repo in SPINE if not (args.stack / repo / "pyproject.toml").is_file()]
    if missing:
        print(f"evidence_bundle: not a stack folder, missing: {', '.join(missing)}", file=sys.stderr)
        return 2
    runs = run_checks(args.stack, args.cns_root, args.python) if args.python else []
    bundle = collect(args.stack, args.cns_root, manifest, releases, runs)
    text = json.dumps(bundle, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    for problem in bundle["problems"]:
        print(f"evidence_bundle: {problem}", file=sys.stderr)
    return 0 if passed(bundle) else 1


if __name__ == "__main__":
    raise SystemExit(main())

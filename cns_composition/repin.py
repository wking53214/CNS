"""repin: rewrite the circuit manifest from the checkouts that are actually there.

WHY THIS EXISTS

`contracts/warden-stack.json` says which commits of the seven circuit repositories belong together, and
Warden refuses a stack whose checkout is at any other commit. That is the point of it, and it is also the
chore: every merge to any of the seven makes the manifest wrong, and until somebody edits it by hand the
whole circuit refuses to run. It went stale twice on the day the manifest was first merged.

This module is the editing, done by a program, from facts. It reads each pinned repository's HEAD in a
stack folder and rewrites the pins to match. It does not decide whether the new combination works. That is
the canary's job (`circuit_canary`), and a re-pin is only worth proposing after the canary says ACCEPT.

WHAT IT WILL NOT DO

  It never adds or removes a repository. The manifest says which repositories make up the stack; this
    only moves their commits. A name in the manifest with no checkout is an error, not a skipped pin.
  It never pins a dirty checkout unless told to. A commit that is not what is on disk is not a fact.
  It never touches `schema` or `contract`. Those are claims about the seat contract, not about commits.
  It never guesses. Any checkout it cannot read is an error that names the checkout.

The manifest is validated with `cns.stack.StackManifest` before and after, so a re-pin cannot produce a
file the rest of CNS would refuse to read. Output formatting is fixed (two-space indent, one trailing
newline) and a test holds the committed file to it, so an unchanged stack gives an unchanged file.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - git is run with a fixed argument list, never through a shell
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from cns.stack import StackManifest, StackPin

__all__ = ["RepinError", "read_heads", "repin_text", "changes", "main"]

#: Environment for git: no prompts, no system config, and the same scrub the scanners use.
_GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0"}
#: Config that names a program is overridden on the command line, because a checkout's own config is data
#: written by somebody else and git will run what it names.
_GIT_SAFE = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat")
_GIT_TIMEOUT_SECONDS = 30


class RepinError(Exception):
    """A pin could not be updated, and why. Never raised for a manifest that is simply up to date."""


def _git(folder: Path, *args: str) -> str:
    exe = shutil.which("git")
    if exe is None:
        raise RepinError("git is not on PATH")
    env = {**os.environ, **_GIT_ENV}
    try:
        done = subprocess.run(  # nosec B603 - fixed argument list, no shell
            [exe, *_GIT_SAFE, "-C", str(folder), *args],
            capture_output=True, text=True, env=env, timeout=_GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise RepinError(f"git could not be run in {str(folder)!r}: {type(err).__name__}") from err
    if done.returncode != 0:
        raise RepinError(f"{str(folder)!r} is not a readable git checkout")
    return done.stdout.strip()


def _folder_for(stack: Path, name: str) -> Path:
    """The stack folder for a pin name, matched without regard to case, as Warden matches it."""
    matches = [p for p in sorted(stack.iterdir()) if p.is_dir() and p.name.casefold() == name.casefold()]
    if not matches:
        raise RepinError(f"the manifest names {name!r}, which is not in the stack folder {str(stack)!r}")
    if len(matches) > 1:
        raise RepinError(f"{name!r} matches more than one folder in {str(stack)!r}: "
                         f"{', '.join(p.name for p in matches)}")
    return matches[0]


def read_heads(stack: Path, names: Sequence[str], *, allow_dirty: bool = False) -> Dict[str, str]:
    """The full HEAD commit of each named checkout in `stack`, keyed by the manifest's spelling of the name."""
    stack = Path(stack)
    if not stack.is_dir():
        raise RepinError(f"the stack folder {str(stack)!r} does not exist")
    heads: Dict[str, str] = {}
    for name in names:
        folder = _folder_for(stack, name)
        head = _git(folder, "rev-parse", "HEAD")
        if not allow_dirty and _git(folder, "status", "--porcelain", "--untracked-files=no"):
            raise RepinError(f"{name!r} has uncommitted changes, so its HEAD is not what is on disk; "
                             "commit or stash them, or pass allow_dirty")
        heads[name] = head
    return heads


def _load(text: str) -> Tuple[Dict[str, object], StackManifest]:
    try:
        data = json.loads(text)
    except ValueError as err:
        raise RepinError(f"the manifest is not JSON: {err}") from err
    if not isinstance(data, dict) or not isinstance(data.get("repos"), dict):
        raise RepinError('the manifest must be an object with a "repos" object')
    manifest = StackManifest(
        schema=str(data.get("schema", "")), contract=str(data.get("contract", "")),
        repos=tuple(StackPin(name=str(n), commit=str(c)) for n, c in data["repos"].items()))
    problems = manifest.problems()
    if problems:
        raise RepinError("the manifest is not valid: " + "; ".join(problems))
    return data, manifest


def changes(text: str, heads: Mapping[str, str]) -> List[Tuple[str, str, str]]:
    """(name, old commit, new commit) for every pin that would move."""
    _, manifest = _load(text)
    return [(p.name, p.commit, heads[p.name]) for p in manifest.repos
            if p.name in heads and heads[p.name] != p.commit]


def repin_text(text: str, heads: Mapping[str, str]) -> str:
    """The manifest with each pin moved to `heads[name]`. Only `repos` values change."""
    data, manifest = _load(text)
    missing = [p.name for p in manifest.repos if p.name not in heads]
    if missing:
        raise RepinError("no commit was given for: " + ", ".join(missing))
    repos = {p.name: heads[p.name] for p in manifest.repos}
    out = {**data, "repos": repos}
    new = json.dumps(out, indent=2) + "\n"
    _, checked = _load(new)
    if tuple(p.name for p in checked.repos) != tuple(p.name for p in manifest.repos):
        raise RepinError("the set of repositories changed; a re-pin moves commits only")
    return new


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.repin",
        description="Rewrite the pins in the circuit manifest to the HEAD of each checkout in a stack folder.")
    parser.add_argument("--stack", required=True, type=Path, help="a folder holding one checkout per pinned repository")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="the manifest to rewrite (default: contracts/warden-stack.json beside this package)")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if any pin is stale, 0 if all are current")
    parser.add_argument("--allow-dirty", action="store_true", help="pin a checkout that has uncommitted changes")
    args = parser.parse_args(argv)

    path = args.manifest or Path(__file__).resolve().parents[1] / "contracts" / "warden-stack.json"
    try:
        text = path.read_text(encoding="utf-8")
        _, manifest = _load(text)
        heads = read_heads(args.stack, [p.name for p in manifest.repos], allow_dirty=args.allow_dirty)
        moved = changes(text, heads)
        new = repin_text(text, heads)
    except (RepinError, OSError) as err:
        print(f"repin: {err}", file=sys.stderr)
        return 2
    for name, old, now in moved:
        print(f"{name}: {old[:12]} -> {now[:12]}")
    if not moved:
        print("repin: every pin is current")
        return 0
    if args.check:
        print(f"repin: {len(moved)} pin(s) are stale", file=sys.stderr)
        return 1
    path.write_text(new, encoding="utf-8")
    print(f"repin: wrote {len(moved)} pin(s) to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

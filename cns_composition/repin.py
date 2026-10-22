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
  It never pins a dirty checkout unless told to. A commit that is not what is on disk is not a fact. "Dirty"
    is asked the way Warden 0.13.8 asks it, because git's own answer depends on who asks: git runs with no user
    or system configuration, every untracked file is listed (only the repository's own .gitignore can hide
    one), submodules are not ignored, the executable bit is compared, and a tracked file whose index entry
    carries `assume-unchanged` or `skip-worktree` counts as uncommitted work, since git would not report its
    next edit. Before 2.0.0 a seat file edited and then marked `assume-unchanged` was pinned as clean.
  It never touches `schema` or `contract`. Those are claims about the seat contract, not about commits.
  It never guesses. Any checkout it cannot read is an error that names the checkout.

The manifest is validated with `cns.stack.StackManifest` before and after, so a re-pin cannot produce a
file the rest of CNS would refuse to read. Output formatting is fixed (two-space indent, one trailing
newline) and a test holds the committed file to it, so an unchanged stack gives an unchanged file.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import subprocess  # nosec B404 - git is run with a fixed argument list, never through a shell
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from cns.stack import StackManifest, StackPin
from cns_composition import delivery

__all__ = ["RepinError", "DEFAULT_MANIFEST", "stack_folders", "load_manifest", "manifest_names", "unread",
           "uncovered_notes", "read_heads", "uncommitted", "repin_text", "changes", "render_install", "main"]

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "contracts" / "warden-stack.json"

#: Config that names a program is overridden on the command line, because a checkout's own config is data
#: written by somebody else and git will run what it names. The rest is what a status of uncommitted work must
#: not be talked out of by configuration: no global ignore file, file stat not trusted blindly, the mode bit
#: compared, no untracked-file cache.
_GIT_SAFE = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat",
             "-c", "core.excludesFile=", "-c", "core.ignoreStat=false", "-c", "core.fileMode=true",
             "-c", "core.untrackedCache=false")
_GIT_TIMEOUT_SECONDS = 30

_empty_config_dir: Optional[Path] = None


def _empty_config() -> Path:
    """A folder holding an empty git config file, made once per process and removed when it ends."""
    global _empty_config_dir
    if _empty_config_dir is None or not (_empty_config_dir / "gitconfig").is_file():
        folder = Path(tempfile.mkdtemp(prefix="cns-git-"))
        (folder / "gitconfig").write_text("", encoding="utf-8")
        atexit.register(shutil.rmtree, str(folder), True)
        _empty_config_dir = folder
    return _empty_config_dir


def _git_env() -> Dict[str, str]:
    """The environment git runs in: no GIT_* variable from the caller (a stray GIT_DIR would point it
    elsewhere), no prompt, no optional locks, and no user or system configuration at all. HOME and
    XDG_CONFIG_HOME point at the empty folder for a git that predates GIT_CONFIG_GLOBAL."""
    folder = _empty_config()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1",
                "HOME": str(folder), "XDG_CONFIG_HOME": str(folder),
                "GIT_CONFIG_GLOBAL": str(folder / "gitconfig"), "GIT_CONFIG_SYSTEM": str(folder / "gitconfig")})
    return env


class RepinError(Exception):
    """A pin could not be updated, and why. Never raised for a manifest that is simply up to date."""


def _git(folder: Path, *args: str) -> str:
    exe = shutil.which("git")
    if exe is None:
        raise RepinError("git is not on PATH")
    env = _git_env()
    try:
        done = subprocess.run(  # nosec B603 - fixed argument list, no shell
            [exe, *_GIT_SAFE, "-C", str(folder), *args],
            capture_output=True, text=True, env=env, timeout=_GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise RepinError(f"git could not be run in {str(folder)!r}: {type(err).__name__}") from err
    if done.returncode != 0:
        raise RepinError(f"{str(folder)!r} is not a readable git checkout")
    return done.stdout.strip()


def stack_folders(stack: Path) -> List[Path]:
    """The immediate subfolders of a stack folder. A symlink to a folder counts, as it does for `read_heads`, so
    `repin`, `seat_pins` and `cns_versions` all see the same set of repositories."""
    return sorted(p for p in Path(stack).iterdir() if p.is_dir())


def load_manifest(path: Optional[Path] = None) -> Dict[str, str]:
    """The pins a manifest holds, name to commit, in its order. Raises RepinError if it cannot be read as a manifest."""
    path = Path(path) if path else DEFAULT_MANIFEST
    try:
        text = delivery.read_text(path)
    except delivery.DeliveryError as err:
        raise RepinError(str(err)) from err
    except (OSError, UnicodeDecodeError) as err:
        raise RepinError(f"{str(path)!r} cannot be read: {type(err).__name__}") from err
    _, manifest = _load(text)
    return {p.name: p.commit for p in manifest.repos}


def manifest_names(path: Optional[Path] = None) -> List[str]:
    """The repository names a manifest pins, in its order. Raises RepinError if it cannot be read as a manifest."""
    return list(load_manifest(path))


def unread(names: Sequence[str], read: Sequence[str]) -> List[str]:
    """The manifest names that no folder name in `read` matches (without regard to case, as Warden matches them)."""
    seen = {r.casefold() for r in read}
    return [n for n in names if n.casefold() not in seen]


def uncovered_notes(stack: Path, names: Sequence[str]) -> List[str]:
    """One note when the stack folder holds checkouts the manifest does not name. A note, not a failure: Warden
    refuses only a folder it uses (WATCHER_MCU sits beside the seven and reads the record afterwards), but a
    person reading "every pin agrees" should know which folders that claim does not cover."""
    covered = {n.casefold() for n in names}
    extra = [p.name for p in stack_folders(stack) if p.name.casefold() not in covered and not p.name.startswith(".")]
    if not extra:
        return []
    return [f"the stack folder also holds {', '.join(extra)}, which the manifest does not name, so nothing pins "
            + ("it" if len(extra) == 1 else "them") + " to a commit"]


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
        if not allow_dirty:
            changed, hidden = uncommitted(folder)
            if changed:
                flagged = (f"; {hidden} of them hidden from git status by an index flag, which `git update-index "
                           "--no-assume-unchanged` or `--no-skip-worktree` clears") if hidden else ""
                raise RepinError(f"{name!r} has uncommitted changes ({changed} path(s) are dirty{flagged}), so "
                                 "its HEAD is not what is on disk; commit, stash or remove them, or pass allow_dirty")
        heads[name] = head
    return heads


def uncommitted(folder: Path) -> Tuple[int, int]:
    """(paths with uncommitted work, of which hidden by an index flag) for a checkout, asked the strict way.

    Every untracked file is listed and only the repository's own .gitignore can hide one; submodules are not
    ignored; a tracked file flagged `assume-unchanged` (a lowercase letter in `git ls-files -v`) or
    `skip-worktree` (`S`) counts, because git would report nothing for it whatever it holds."""
    status = _git(folder, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none")
    changed = {line[3:] for line in status.splitlines() if line.strip()}
    listing = _git(folder, "ls-files", "-v", "-z", "--full-name", "--", ":/")
    hidden = {entry.partition(" ")[2] for entry in listing.split("\0")
              if entry and (entry[0].islower() or entry[0] == "S")}
    return len(changed | hidden), len(hidden - changed)


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


def _main(argv: Optional[List[str]] = None) -> int:
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
        text = delivery.read_text(path)
        _, manifest = _load(text)
        heads = read_heads(args.stack, [p.name for p in manifest.repos], allow_dirty=args.allow_dirty)
        moved = changes(text, heads)
        new = repin_text(text, heads)
    except (RepinError, OSError) as err:
        print(f"repin: {err}", file=sys.stderr)
        return 2
    for note in uncovered_notes(args.stack, [p.name for p in manifest.repos]):
        print(f"note: {note}")
    for name, old, now in moved:
        print(f"{name}: {old[:12]} -> {now[:12]}")
    if not moved:
        print("repin: every pin is current")
        return 0
    if args.check:
        print(f"repin: {len(moved)} pin(s) are stale", file=sys.stderr)
        return 1
    try:
        delivery.write_file(path, new)
    except delivery.DeliveryError as err:
        print(f"repin: {err}", file=sys.stderr)
        return 2
    print(f"repin: wrote {len(moved)} pin(s) to {path}")
    return render_install(path, args.stack)


def render_install(manifest_path: Path, stack: Path) -> int:
    """After the manifest moved: rewrite the install file beside it so the two cannot drift apart, with each
    version comment refreshed from its checkout. No install file beside the manifest is said, not skipped silently.
    Returns the exit code for the command."""
    from cns_composition import cns_versions, install_stack  # here, not at the top: cns_versions imports repin
    install = manifest_path.with_name("install-stack.txt")
    if not install.exists():
        print(f"repin: no install-stack.txt beside {manifest_path}, so nothing was rendered from the new pins")
        return 0
    try:
        text = delivery.read_text(install)
        manifest = load_manifest(manifest_path)
        table = cns_versions.load_table()
        rendered = install_stack.render(text, manifest, table, install_stack.stack_versions(stack, list(manifest)))
        if rendered != text:
            delivery.write_file(install, rendered)
    except (RepinError, install_stack.RenderError, OSError) as err:
        print(f"repin: the manifest moved but {install} could not be rendered from it: {err}", file=sys.stderr)
        return 2
    print(f"repin: {'wrote' if rendered != text else 'left'} {install}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "repin")


if __name__ == "__main__":
    raise SystemExit(main())

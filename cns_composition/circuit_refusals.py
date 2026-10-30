"""circuit_refusals: the circuit must refuse what it must refuse, proven on throwaway copies of the stack.

WHY THIS EXISTS

`circuit_canary` proves the circuit says ACCEPT on a clean stack and a clean target. A check that can only pass is
half a check: the manifest exists so that Warden refuses a stack that is not what the manifest says, and until
2.0.0 nothing ran the circuit on such a stack to see that it does. Measured on 2026-10-22 on throwaway clones of
the pinned stack: Warden 0.13.7 (then the pinned governor) refuses a dirty member, a short pin and a wrong commit, and
runs on with a seat the manifest does not name and with a modified seat file hidden from `git status` by
`assume-unchanged`, `skip-worktree` or the caller's global git configuration. Warden 0.13.8 refuses all of them.
This module is each of those cases as a check, so the pinned circuit's answer is read on every run and not
remembered from a changelog.

WHAT IT DOES

For each case it clones every folder of the stack into a temporary folder (local clones, read-only for the
source; a case may leave one out), writes a manifest for those clones into a throwaway hub (the real manifest's names
and order, the clones' commits), applies one change, runs `warden tagteam` the way the canary does (the claim seat
proposes one ordinary change, because a stack without the released Drafter needs a proposer and a refusal for want of
one would prove nothing), and passes only when the
decision and the exit code are the refusal the case expects. The documented refusals are, for Warden 0.13.7 and
later: USAGE_ERROR, exit 2, "Nothing was run", for every stack problem; and for a target whose suite is red from
the start, one of INCONCLUSIVE exit 6 (the Drafter proposed), FINISH_REJECTED exit 1 (the Finisher did) or
JUDGE_REJECTED exit 1 (nobody did), as Warden 0.13.8's `docs/EXIT_CODES.md` states them. Every other answer,
ACCEPT above all, is a failure that names the case, the answer and Warden's own reason.

A roster case (a seat the manifest and the folder disagree about) may not pass on exit 2 alone: its reason must name
the seat as a seat. Warden quotes paths in its reasons, so every path-like word is taken out first and a name that
survives only inside a path does not count. The throwaway folders are numbered, never named after the case, so a case
name cannot reach a reason through a path (found by the round-8 audit: a case named `unnamed_drafter_explicit`, whose only
change was a dirty JUDGE file, passed because its folder was called that).

The real stack is read, never written; the code that runs is the code in the stack, as for the canary.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import shutil
import subprocess  # nosec B404 - fixed argument lists, never through a shell
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from cns_composition import circuit_canary as canary, delivery, repin

__all__ = ["CASES", "Case", "Outcome", "run_case", "run_all", "main"]

#: The seat every stack case changes. A seat Warden imports, so a change to it is code the run would execute.
_SEAT = "JUDGE"
_SEAT_FILE = Path("judge") / "seat.py"
_REFUSED = frozenset({("USAGE_ERROR", 2)})
_RED_SUITE = frozenset({("INCONCLUSIVE", 6), ("FINISH_REJECTED", 1), ("JUDGE_REJECTED", 1)})
_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True)
class Case:
    name: str
    what: str
    #: (decision, exit code) pairs that pass. Anything else fails.
    expected: frozenset
    #: Changes the throwaway stack or hub. Receives (stack, hub, manifest dict, env dict) and may edit any of them.
    apply: Callable[[Path, Path, Dict[str, str], Dict[str, str]], None]
    #: Whether the throwaway target's suite is red from the start.
    red_target: bool = False
    #: Stack folders left out of the throwaway copy (a seat the manifest names but the folder lacks).
    leave_out: Tuple[str, ...] = ()
    #: How the run supplies the Drafter seat (and, for "finisher", the finisher): "claim-commit" (the default, as the
    #: canary does), "claim-diff" (the same change as a diff file), "drafter" (an explicit `--drafter`, no claim) or
    #: "finisher" (the claimed commit plus an explicit `--finisher`). A roster rule that holds for one of these and not
    #: for another is a defect, so each path has a case.
    supply: str = "claim-commit"
    #: A seat or repository the refusal reason must name (compared without regard to case); empty for no requirement.
    #: A refusal on exit 2 and USAGE_ERROR alone could be a refusal for another reason, so the roster cases also ask
    #: that Warden say which seat it refused.
    reason_names: str = ""
    #: A roster case (a seat the manifest and the folder disagree about). It may not pass on a refusal alone: exit 2
    #: and USAGE_ERROR could be a refusal for any other reason, so it needs `reason_names`, and the seat must be named
    #: in the reason as a seat, not only inside a path.
    roster: bool = False

    def __post_init__(self) -> None:
        if self.roster and not self.reason_names:
            raise ValueError(f"the roster case {self.name!r} has no seat its reason must name, so it would pass on exit 2 alone")


@dataclass(frozen=True)
class Outcome:
    case: str
    ok: bool
    decision: str
    exit_code: int
    reason: str


def _git(folder: Path, *args: str) -> str:
    exe = shutil.which("git")
    if exe is None:
        raise OSError("git is not on PATH")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    done = subprocess.run([exe, *canary._GIT_IDENT, "-C", str(folder), *args],  # nosec B603 - fixed list
                          capture_output=True, text=True, check=True, timeout=120, env=env)
    return done.stdout.strip()


def _seat(stack: Path) -> Path:
    found = canary._folder(stack, _SEAT)
    if found is None:
        raise OSError(f"the stack has no {_SEAT} checkout")
    return found


def _edit_seat_file(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
    path = _seat(stack) / _SEAT_FILE
    path.write_text(path.read_text(encoding="utf-8") + "\n# changed after the pin\n", encoding="utf-8")


def _add_untracked(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
    (_seat(stack) / _SEAT_FILE.parent / "unpinned.py").write_text("UNPINNED = True\n", encoding="utf-8")


def _omit_seat(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
    for name in list(manifest):
        if name.casefold() == _SEAT.casefold():
            del manifest[name]


def _pin_as(transform: Callable[[str], str]) -> Callable[[Path, Path, Dict[str, str], Dict[str, str]], None]:
    def apply(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
        for name in manifest:
            if name.casefold() == _SEAT.casefold():
                manifest[name] = transform(manifest[name])
    return apply


def _index_flag(flag: str) -> Callable[[Path, Path, Dict[str, str], Dict[str, str]], None]:
    def apply(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
        _edit_seat_file(stack, hub, manifest, env)
        _git(_seat(stack), "update-index", flag, _SEAT_FILE.as_posix())
    return apply


def _global_excludes(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
    _add_untracked(stack, hub, manifest, env)
    home = hub / "home"
    home.mkdir(parents=True)
    (home / "excludes").write_text("unpinned.py\n", encoding="utf-8")
    (home / ".gitconfig").write_text(f"[core]\n\texcludesFile = {home / 'excludes'}\n[status]\n\tshowUntrackedFiles = no\n",
                                     encoding="utf-8")
    env["HOME"] = env["XDG_CONFIG_HOME"] = str(home)
    env.pop("GIT_CONFIG_GLOBAL", None)


def _nothing(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
    pass


def _add_unnamed_seat(name: str) -> Callable[[Path, Path, Dict[str, str], Dict[str, str]], None]:
    """A checkout of a releasable seat, which the manifest does not name, is put into the stack folder. It is a
    throwaway repository holding one stub file: Warden refuses the folder before it runs anything in it. Every case
    here hands Warden a claimed commit, so the claim seat already holds the option a DRAFTER folder would fill. Warden
    0.16.1 did not refuse that folder, although its README said it did (found by the 2026-10-30 work here, fixed in
    Warden 0.16.2, which compares the folder with the manifest before any option is substituted); it did refuse a
    BURNISH folder, which fills the finisher. Both are cases now."""
    def apply(stack: Path, hub: Path, manifest: Dict[str, str], env: Dict[str, str]) -> None:
        folder = stack / name.upper()
        (folder / name).mkdir(parents=True)
        (folder / name / "__init__.py").write_text("", encoding="utf-8")
        _git(folder, "init", "-q")
        _git(folder, "add", "-A")
        _git(folder, "commit", "-q", "-m", "a seat the manifest does not name")
    return apply


CASES: Tuple[Case, ...] = (
    Case("dirty_tracked", f"a tracked file of {_SEAT} is modified after the pin", _REFUSED, _edit_seat_file),
    Case("dirty_untracked", f"an untracked file is added to {_SEAT}", _REFUSED, _add_untracked),
    Case("omitted_seat", f"{_SEAT} is in the stack but not in the manifest", _REFUSED, _omit_seat,
         reason_names=_SEAT, roster=True),
    Case("short_pin", f"the manifest pins {_SEAT} by a 7-character prefix", _REFUSED, _pin_as(lambda c: c[:7])),
    Case("uppercase_pin", f"the manifest pins {_SEAT} in uppercase hex", _REFUSED, _pin_as(str.upper)),
    Case("wrong_commit", f"the manifest pins {_SEAT} to a commit the checkout is not at", _REFUSED, _pin_as(lambda c: "0" * 40)),
    Case("assume_unchanged", f"a modified {_SEAT} file is flagged assume-unchanged, so git status hides it",
         _REFUSED, _index_flag("--assume-unchanged")),
    Case("skip_worktree", f"a modified {_SEAT} file is flagged skip-worktree, so git status hides it",
         _REFUSED, _index_flag("--skip-worktree")),
    Case("global_excludes", f"an untracked {_SEAT} file is hidden by the caller's global excludes file and "
         "status.showUntrackedFiles=no", _REFUSED, _global_excludes),
    Case("red_suite", "the target's own suite is red before anything is written", _RED_SUITE, _nothing, red_target=True),
    # Warden's roster rule, and nothing else: a seat the manifest names must be in the folder, and a seat the folder
    # holds must be named by the manifest, including the releasable one. Configuration integrity, not a detector.
    Case("missing_seat", "SWIZZLE is in the manifest but not in the stack folder", _REFUSED, _nothing,
         leave_out=("SWIZZLE",), reason_names="swizzle", roster=True),
    Case("unnamed_burnish", "a BURNISH checkout is in the stack folder but not in the manifest", _REFUSED,
         _add_unnamed_seat("burnish"), reason_names="burnish", roster=True),
    Case("unnamed_drafter", "a DRAFTER checkout is in the stack folder but not in the manifest, and the claim seat "
         "proposes", _REFUSED, _add_unnamed_seat("drafter"), reason_names="drafter", roster=True),
    # The same roster rule through each other path that supplies a seat (Warden 0.16.1 compared the folder with the
    # manifest only for a seat whose option was still unset, so the path mattered). Configuration integrity again.
    Case("unnamed_drafter_claim_diff", "a DRAFTER checkout is in the stack folder but not in the manifest, and the "
         "change is claimed as a diff file", _REFUSED, _add_unnamed_seat("drafter"), supply="claim-diff",
         reason_names="drafter", roster=True),
    Case("unnamed_drafter_explicit", "a DRAFTER checkout is in the stack folder but not in the manifest, and "
         "--drafter names the seat", _REFUSED, _add_unnamed_seat("drafter"), supply="drafter",
         reason_names="drafter", roster=True),
    Case("unnamed_burnish_explicit", "a BURNISH checkout is in the stack folder but not in the manifest, and "
         "--finisher names the seat", _REFUSED, _add_unnamed_seat("burnish"), supply="finisher",
         reason_names="burnish", roster=True),
)


#: A counter for the throwaway folders, so that a case name never appears in a path: Warden quotes paths in its reasons,
#: and a roster case once passed because its folder was called "unnamed_drafter" while the refusal was for something else.
_FOLDERS = itertools.count(1)
_PATH_LIKE = re.compile(r"\S*[/\\]\S*")


def names_the_seat(reason: str, name: str) -> bool:
    """Whether `reason` names the seat `name` as a seat: with every path-like word (anything with a slash) taken out
    first, the name still appears as a whole word, in any case."""
    words = _PATH_LIKE.sub(" ", reason)
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", words, re.IGNORECASE) is not None


def _clone_stack(src: Path, dst: Path, leave_out: Sequence[str] = ()) -> None:
    dst.mkdir(parents=True)
    skipped = {name.casefold() for name in leave_out}
    for folder in repin.stack_folders(src):
        if folder.name.casefold() in skipped:
            continue
        _git(dst, "clone", "--quiet", str(folder.resolve()), str(dst / folder.name))


def _hub_manifest(real_manifest: Path, stack: Path) -> Dict[str, str]:
    """The real manifest's names, in its order, pinned to the clones' commits (the same commits when the stack is at
    the manifest, which is what the workflow checks out)."""
    names = repin.manifest_names(real_manifest)
    heads = repin.read_heads(stack, names, allow_dirty=True)
    return {name: heads[name] for name in names}


def _write_hub(hub: Path, real_manifest: Path, manifest: Dict[str, str]) -> None:
    data = json.loads(delivery.read_text(real_manifest))
    data["repos"] = manifest
    (hub / "contracts").mkdir(parents=True, exist_ok=True)
    (hub / "contracts" / "warden-stack.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _make_target(root: Path, red: bool) -> Tuple[Path, str]:
    """The throwaway target, at its base, and the commit the claim seat is asked to apply to it."""
    target = canary._make_target(root)
    if red:
        (target / "tests" / "test_area.py").write_text(
            "from shapes.area import circle\n\n\ndef test_circle():\n    assert circle(1) == 0  # red on purpose\n",
            encoding="utf-8")
        canary._git(target, "add", "-A")
        canary._git(target, "commit", "-q", "-m", "a red suite")
    return target, canary._claim_commit(target)


_SUPPLIES = ("claim-commit", "claim-diff", "drafter", "finisher")


def _supply_args(supply: str, target: Path, claimed: str, root: Path) -> List[str]:
    """The Warden options that put a proposer (and for "finisher" a finisher) into the run, one path per supply."""
    if supply == "claim-commit":
        return ["--claim-commit", claimed]
    if supply == "claim-diff":
        diff = root / "claimed.diff"
        diff.write_text(_git(target, "diff", "--no-color", f"{claimed}^", claimed) + "\n", encoding="utf-8")
        return ["--claim-diff", str(diff), "--claim-subject", "write the circle area with a power",
                "--claim-author", "circuit-refusals <circuit-refusals@example.org>"]
    if supply == "drafter":
        return ["--drafter", "drafter.seat:Drafter"]
    if supply == "finisher":
        return ["--claim-commit", claimed, "--finisher", "burnish.finisher:Burnish"]
    raise OSError(f"unknown supply {supply!r}")


def run_case(case: Case, stack: Path, cns: Path, *, python: Optional[str] = None,
             timeout: int = _TIMEOUT_SECONDS) -> Outcome:
    """Build the case on throwaway clones of `stack` and say what Warden answered."""
    stack, cns = Path(stack), Path(cns)
    real_manifest = cns / "contracts" / "warden-stack.json"
    with tempfile.TemporaryDirectory(prefix=f"circuit-refusal-{next(_FOLDERS):03d}-") as tmp:
        root = Path(tmp)
        copy, hub = root / "stack", root / "hub"
        env: Dict[str, str] = dict(os.environ)
        try:
            _clone_stack(stack, copy, case.leave_out)
            manifest = _hub_manifest(real_manifest, stack)
            case.apply(copy, hub, manifest, env)
            _write_hub(hub, real_manifest, manifest)
            target, claimed = _make_target(root, case.red_target)
        except (OSError, subprocess.SubprocessError, repin.RepinError) as err:
            return Outcome(case.name, False, "REFUSAL_ERROR", -1, f"the case could not be built: {type(err).__name__}: {err}")
        paths = [str(canary._folder(copy, name)) for name in canary._IMPORTED] + [str(hub)]
        env["PYTHONPATH"] = os.pathsep.join(paths)
        try:
            supply = _supply_args(case.supply, target, claimed, root)
        except (OSError, subprocess.SubprocessError) as err:
            return Outcome(case.name, False, "REFUSAL_ERROR", -1, f"the case could not be built: {type(err).__name__}: {err}")
        cmd = [python or sys.executable, "-m", "warden.cli", "tagteam", str(target),
               "--stack", str(copy), "--cns", str(hub), *supply,
               "--authorize", "circuit-refusals", "--reason", "must the circuit refuse this stack",
               "--scope", "code"]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, env=env,  # nosec B603 - fixed list, no shell
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return Outcome(case.name, False, "REFUSAL_TIMEOUT", -1, f"the circuit did not finish in {timeout} seconds")
        except OSError as err:
            return Outcome(case.name, False, "REFUSAL_ERROR", -1, f"Warden could not be started: {type(err).__name__}")
    try:
        record = json.loads(done.stdout)
    except ValueError:
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or ["no output"]
        return Outcome(case.name, False, "REFUSAL_ERROR", done.returncode,
                       f"Warden printed no run record (exit {done.returncode}): {tail[0][:300]}")
    if not isinstance(record, dict):
        return Outcome(case.name, False, "REFUSAL_ERROR", done.returncode, "Warden's run record is not an object")
    decision, reason = str(record.get("decision", "")), str(record.get("reason", ""))
    ok = (decision, done.returncode) in case.expected
    if ok and case.reason_names and not names_the_seat(reason, case.reason_names):
        return Outcome(case.name, False, decision, done.returncode,
                       f"refused, but the reason does not name {case.reason_names} as a seat (a name inside a path "
                       f"does not count): {reason[:300]}")
    return Outcome(case.name, ok, decision, done.returncode, reason)


def run_all(stack: Path, cns: Path, names: Sequence[str] = (), *, python: Optional[str] = None,
            timeout: int = _TIMEOUT_SECONDS) -> List[Outcome]:
    chosen = [c for c in CASES if not names or c.name in names]
    return [run_case(case, stack, cns, python=python, timeout=timeout) for case in chosen]


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.circuit_refusals",
        description="Run the circuit on throwaway stacks that must be refused, and exit 0 only if every one is.")
    parser.add_argument("--stack", required=True, type=Path, help="a folder holding one checkout per circuit repository")
    parser.add_argument("--cns", required=True, type=Path, help="a CNS checkout (the hub that holds the manifest)")
    parser.add_argument("--case", action="append", default=[], choices=[c.name for c in CASES],
                        help="run only this case (may be repeated; default: every case)")
    parser.add_argument("--timeout", type=int, default=_TIMEOUT_SECONDS, help="seconds to wait for each run")
    args = parser.parse_args(argv)
    if not args.stack.is_dir():
        print(f"circuit refusals: the stack folder {str(args.stack)!r} does not exist", file=sys.stderr)
        return 2
    if not (args.cns / "contracts" / "warden-stack.json").is_file():
        print(f"circuit refusals: {str(args.cns)!r} has no contracts/warden-stack.json; is it a CNS checkout?",
              file=sys.stderr)
        return 2
    for name in canary._IMPORTED:
        if canary._folder(args.stack, name) is None:
            print(f"circuit refusals: the stack folder has no {name} checkout", file=sys.stderr)
            return 2
    try:
        missing = canary._missing_modules(sys.executable)
    except (OSError, subprocess.SubprocessError) as err:
        print(f"circuit refusals: the interpreter could not be started: {type(err).__name__}", file=sys.stderr)
        return 2
    if missing:
        print(f"circuit refusals: this interpreter cannot import {', '.join(missing)} without PYTHONPATH; install them "
              "(pip install pytest numpy matplotlib . from a CNS checkout)", file=sys.stderr)
        return 2
    failed = 0
    for outcome in run_all(args.stack, args.cns, args.case, timeout=args.timeout):
        expected = ", ".join(f"{d} exit {e}" for d, e in sorted(outcome_expected(outcome.case)))
        if outcome.ok:
            print(f"circuit refusals: {outcome.case}: {outcome.decision} exit {outcome.exit_code}: refused as it must be")
        else:
            failed += 1
            print(f"circuit refusals: {outcome.case}: FAILED: got {outcome.decision} exit {outcome.exit_code}, "
                  f"expected {expected}: {outcome.reason[:300]}", file=sys.stderr)
    total = len(args.case) or len(CASES)
    if failed:
        print(f"circuit refusals: {failed} of {total} cases were not refused", file=sys.stderr)
        return 1
    print(f"circuit refusals: every case was refused ({total} of {total})")
    return 0


def outcome_expected(name: str) -> frozenset:
    return next(c.expected for c in CASES if c.name == name)


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "circuit_refusals")


if __name__ == "__main__":
    raise SystemExit(main())

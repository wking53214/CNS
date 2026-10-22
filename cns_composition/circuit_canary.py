"""circuit_canary: does the whole circuit still work together, on the checkouts in this folder?

WHY THIS EXISTS

`repin` can say what the heads of the seven repositories are. It cannot say whether those seven still work
together, and a manifest that names a combination nobody ran is a guess with a commit hash on it. This is the
run: it builds a small throwaway repository, hands it to Warden with `--stack` and `--cns`, and reports whether
the whole circuit (Ghost Tools, SWIZZLE, ASSAY, the Drafter, the Judge, Burnish) ended ACCEPT.

It is also a daily health check for the combination, because the same run answers "did a merge to any one of
the seven break the others". That check is what an exact-commit pin was standing in for.

WHAT COUNTS AS A PASS

All of: Warden exits 0, its run record says ACCEPT, converged, and nothing was put back. Anything else is a
failure and the record's own reason is carried out. A refusal (a stale manifest, a dirty checkout, a missing
part) is a failure, not an error in the canary: it is the answer.

WHAT IT TOUCHES

A temporary folder it creates and removes. The stack is read, never written. The code it runs is the code in
the stack, so run it where that is acceptable (CI, with a read-only token).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - fixed argument lists, never through a shell
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from cns_composition import delivery

__all__ = ["CanaryResult", "run_canary", "main"]

#: What the interpreter must be able to import on its own. The throwaway repository's tests need pytest, and the
#: instruments Warden starts (SWIZZLE's attacks among them) do not inherit PYTHONPATH, so `cns` has to be installed
#: as a package, not merely reachable. Found by the first run on GitHub: without pytest the circuit ends
#: SUITE_RED, and without an installed cns the Judge says INSUFFICIENT, neither of which names the cause. numpy and
#: matplotlib are for ASSAY: a claim it cannot run is a failure, so without them Warden ends INCONCLUSIVE.
_NEEDED = ("pytest", "cns", "numpy", "matplotlib")
#: The checkouts whose packages Warden imports as seats. Matched without regard to case, as Warden matches a stack.
_IMPORTED = ("WARDEN", "JUDGE", "DRAFTER", "BURNISH")
_TIMEOUT_SECONDS = 1800
_GIT_IDENT = ("-c", "user.name=circuit-canary", "-c", "user.email=canary@invalid", "-c", "commit.gpgsign=false")

#: The throwaway repository: a tiny package whose README says nothing about its tests, which is what the
#: circuit has already been shown to accept under a documentation grant.
_TARGET = {
    "README.md": "# shapes\n\nArea helpers for circles and rectangles.\n",
    "shapes/__init__.py": '"""Small geometry helpers."""\n',
    "shapes/area.py": (
        '"""Areas of simple shapes."""\nimport math\n\n\n'
        'def circle(radius: float) -> float:\n    """Area of a circle."""\n    return math.pi * radius * radius\n\n\n'
        'def rectangle(width: float, height: float) -> float:\n    """Area of a rectangle."""\n    return width * height\n'),
    "tests/test_area.py": (
        "import math\n\nfrom shapes.area import circle, rectangle\n\n\n"
        "def test_circle():\n    assert math.isclose(circle(1), math.pi)\n\n\n"
        "def test_rectangle():\n    assert rectangle(2, 3) == 6\n"),
}


@dataclass(frozen=True)
class CanaryResult:
    ok: bool
    decision: str
    reason: str


def _fail(decision: str, reason: str) -> CanaryResult:
    return CanaryResult(ok=False, decision=decision, reason=reason)


def _folder(stack: Path, name: str) -> Optional[Path]:
    for p in sorted(stack.iterdir()):
        if p.is_dir() and p.name.casefold() == name.casefold():
            return p
    return None


def _git(folder: Path, *args: str) -> None:
    exe = shutil.which("git")
    if exe is None:
        raise OSError("git is not on PATH")
    subprocess.run([exe, *_GIT_IDENT, "-C", str(folder), *args],  # nosec B603 - fixed argument list
                   capture_output=True, text=True, check=True, timeout=60)


def _missing_modules(python: str, modules: Sequence[str] = _NEEDED) -> List[str]:
    """Which of `modules` this interpreter cannot import with no PYTHONPATH, as an instrument would see it."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    missing: List[str] = []
    for name in modules:
        done = subprocess.run([python, "-c", f"import {name}"],  # nosec B603 - fixed list, name from a constant
                              capture_output=True, text=True, env=env, timeout=60, check=False)
        if done.returncode != 0:
            missing.append(name)
    return missing


def _make_target(root: Path) -> Path:
    target = root / "target"
    for rel, text in _TARGET.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(target, "init", "-q")
    _git(target, "add", "-A")
    _git(target, "commit", "-q", "-m", "canary target")
    return target


def run_canary(stack: Path, cns: Path, *, python: Optional[str] = None,
               timeout: int = _TIMEOUT_SECONDS) -> CanaryResult:
    """Run the whole circuit over `stack` with the manifest from `cns`; say whether it ended ACCEPT."""
    stack, cns = Path(stack), Path(cns)
    if not stack.is_dir():
        return _fail("CANARY_ERROR", f"the stack folder {str(stack)!r} does not exist")
    paths: List[str] = []
    for name in _IMPORTED:
        found = _folder(stack, name)
        if found is None:
            return _fail("CANARY_ERROR", f"the stack folder has no {name} checkout")
        paths.append(str(found))
    paths.append(str(cns))
    try:
        missing = _missing_modules(python or sys.executable)
    except (OSError, subprocess.SubprocessError) as err:
        return _fail("CANARY_ERROR", f"the interpreter could not be started: {type(err).__name__}")
    if missing:
        return _fail("CANARY_ERROR",
                     f"this interpreter cannot import {', '.join(missing)} without PYTHONPATH, and the circuit's "
                     "instruments do not inherit PYTHONPATH; install them (pip install pytest numpy matplotlib . from a CNS checkout)")
    env: Dict[str, str] = {**os.environ, "PYTHONPATH": os.pathsep.join(paths)}
    with tempfile.TemporaryDirectory(prefix="circuit-canary-") as tmp:
        try:
            target = _make_target(Path(tmp))
        except (OSError, subprocess.SubprocessError) as err:
            return _fail("CANARY_ERROR", f"could not build the throwaway repository: {type(err).__name__}")
        cmd = [python or sys.executable, "-m", "warden.cli", "tagteam", str(target),
               "--stack", str(stack), "--cns", str(cns),
               "--authorize", "circuit-canary", "--reason", "does the whole circuit still work together",
               "--scope", "documentation"]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, env=env,  # nosec B603 - fixed list, no shell
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return _fail("CANARY_TIMEOUT", f"the circuit did not finish in {timeout} seconds")
        except OSError as err:
            return _fail("CANARY_ERROR", f"Warden could not be started: {type(err).__name__}")
    try:
        record = json.loads(done.stdout)
    except ValueError:
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or ["no output"]
        return _fail("CANARY_ERROR", f"Warden printed no run record (exit {done.returncode}): {tail[0][:300]}")
    if not isinstance(record, dict):
        return _fail("CANARY_ERROR", "Warden's run record is not an object")
    decision = str(record.get("decision", ""))
    reason = str(record.get("reason", ""))
    ok = (done.returncode == 0 and decision == "ACCEPT"
          and record.get("converged") is True and record.get("put_back") is False)
    if ok:
        return CanaryResult(True, decision, reason)
    return _fail(decision or "CANARY_ERROR",
                 reason or f"exit {done.returncode}, converged={record.get('converged')!r}, "
                           f"put_back={record.get('put_back')!r}")


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.circuit_canary",
        description="Run the whole circuit over a stack folder and exit 0 only if it ends ACCEPT.")
    parser.add_argument("--stack", required=True, type=Path, help="a folder holding one checkout per circuit repository")
    parser.add_argument("--cns", required=True, type=Path, help="a CNS checkout (the hub that holds the manifest)")
    parser.add_argument("--timeout", type=int, default=_TIMEOUT_SECONDS, help="seconds to wait for the circuit")
    args = parser.parse_args(argv)
    result = run_canary(args.stack, args.cns, timeout=args.timeout)
    if result.ok:
        print("circuit canary: ACCEPT")
        return 0
    print(f"circuit canary: {result.decision}: {result.reason}", file=sys.stderr)
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    """The command. A report that could not be delivered is exit 2, never 0 (see `delivery`)."""
    return delivery.run(_main, argv, "circuit_canary")


if __name__ == "__main__":
    raise SystemExit(main())

"""seat_pins: do the repositories pin a shared package the same way?

WHY THIS EXISTS

JUDGE, DRAFTER and BURNISH each pin Warden by commit in their own pyproject.toml, and pip refuses to install
two packages together when they pin the same package at different direct URLs. Measured on 2026-10-17 with
Warden's real commits: JUDGE at `df16da8` with DRAFTER at `2cf0eec` gives "judge depends on warden 0.11.5 ...
drafter depends on warden 0.12.0 ... conflicting dependencies". So a pin may not move in one repository
alone: moving one without the others breaks installing them together, and nothing said so until a person hit
the error. The manifest re-pin (`repin`) cannot see this, because these pins are not in the manifest.

WHAT IT CHECKS

For every package that two or more repositories in a stack folder pin by direct URL (`name @ git+https://...@ref`),
the URL and the ref must be identical text. Extras count, because the circuit is installed with them. A package
pinned once is never a disagreement. Anything not pinned by direct URL is ignored.

WHAT IT REPORTS BUT DOES NOT FAIL ON

A pin that lags the stack: a full-commit pin that is not the HEAD of the checkout it names (JUDGE pins Warden at
`df16da8` and WARDEN is at `2cf0eec`). Pins are meant to lag until someone moves them on purpose, and all three
agreeing is what matters. A tag pin cannot be compared with a commit, so it is not reported.

The files are read as text and never executed.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from cns_composition import repin

__all__ = ["Pin", "agreement_problems", "lag_notes", "read_pins", "main"]

#: `"name @ git+URL@ref"`, in a dependencies list or an extra. The ref is whatever follows the last `@`.
_DIRECT = re.compile(r"""["'](?P<pkg>[A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]*\])?\s*@\s*(?P<target>git\+[^"'\s]+)["']""")
_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Pin:
    repo: str          # the stack folder it was read from
    package: str       # normalised distribution name
    url: str           # everything before the last `@`
    ref: str           # a tag, a branch or a commit

    @property
    def text(self) -> str:
        return f"{self.url}@{self.ref}"


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(stack: Path) -> List[Pin]:
    """Every direct-URL pin in the pyproject.toml of each immediate subfolder of `stack`."""
    stack = Path(stack)
    if not stack.is_dir():
        raise repin.RepinError(f"the stack folder {str(stack)!r} does not exist")
    pins: List[Pin] = []
    for folder in sorted(p for p in stack.iterdir() if p.is_dir() and not p.is_symlink()):
        path = folder / "pyproject.toml"
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            raise repin.RepinError(f"{str(path)!r} cannot be read: {type(err).__name__}") from err
        for match in _DIRECT.finditer(text):
            url, _, ref = match.group("target").rpartition("@")
            if not url or not ref:
                continue
            pins.append(Pin(folder.name, _normalise(match.group("pkg")), url, ref))
    return pins


def agreement_problems(pins: Sequence[Pin]) -> List[str]:
    """One sentence per package that is pinned at more than one direct URL or ref."""
    by_package: Dict[str, List[Pin]] = {}
    for pin in pins:
        by_package.setdefault(pin.package, []).append(pin)
    out: List[str] = []
    for package, group in sorted(by_package.items()):
        if len({p.text for p in group}) < 2:
            continue
        urls_differ = len({p.url for p in group}) > 1
        spelled = "; ".join(f"{p.repo} pins {p.text if urls_differ else p.ref}" for p in group)
        out.append(f"{package} is pinned differently: {spelled}. pip cannot install these together; "
                   "move the pin in every repository at once")
    return out


def lag_notes(stack: Path, pins: Sequence[Pin]) -> List[str]:
    """Full-commit pins that name a checkout in the stack but are not that checkout's HEAD."""
    notes: List[str] = []
    seen: set = set()
    for pin in pins:
        if not _FULL_COMMIT.match(pin.ref):
            continue
        name = pin.url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        key = (pin.package, pin.ref, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        try:
            head = repin.read_heads(stack, [name], allow_dirty=True)[name]
        except repin.RepinError:
            continue
        if head != pin.ref:
            holders = ", ".join(sorted({p.repo for p in pins if (p.package, p.ref) == (pin.package, pin.ref)}))
            notes.append(f"{holders} pin {pin.package} at {pin.ref[:12]}, but {name} is at {head[:12]}")
    return notes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cns_composition.seat_pins",
        description="Fail if two repositories in a stack folder pin the same package differently.")
    parser.add_argument("--stack", required=True, type=Path, help="a folder holding one checkout per repository")
    args = parser.parse_args(argv)
    try:
        pins = read_pins(args.stack)
        problems = agreement_problems(pins)
        notes = lag_notes(args.stack, pins)
    except repin.RepinError as err:
        print(f"seat_pins: {err}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"note: {note}")
    if problems:
        for problem in problems:
            print(f"seat_pins: {problem}", file=sys.stderr)
        return 1
    shared = sorted({p.package for p in pins})
    print(f"seat_pins: every shared pin agrees ({len(pins)} pin(s) across {len({p.repo for p in pins})} "
          f"repositories: {', '.join(shared)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

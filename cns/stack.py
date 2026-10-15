"""cns.stack: the stack manifest, the contract that says which checkouts belong together.

WHY THIS EXISTS

On 2026-10-14 the governance circuit (Ghost Tools, SWIZZLE, Warden, the Drafter,
the Judge, Burnish, ASSAY) was run on its own seven repositories. Four of the
seven could not be fully measured: each imports a sibling, Ghost Tools scanned
one repository at a time, and Warden held the result rather than accept what
it had not seen. The missing piece was not a scanner feature. It was a fact
nobody held with authority: which checkouts, at which commits, make up the
whole. Warden had been told a folder; nothing had told it a stack.

Warden 0.11.2 fixed the mechanism (`--join`, `--stack-manifest`) and read the
list from a file a person wrote. A list a person wrote in one repository is a
convention, and this package exists because convention cannot carry an
invariant across repositories. The manifest is a join key like every other
shape here: the circuit joins on "these commits belong together", and the
hub holds the shape of that claim so every consumer reads it the same way.

WHAT THIS MODULE IS

Two rows and pure functions of them. `StackPin` names one checkout and the
commit it must be at. `StackManifest` is the whole: a schema name, the seat
contract the stack speaks, and its pins. `problems` is the validation every
consumer would otherwise write for itself; `pin_for` is the case-blind lookup
Warden's `--stack` folder matching already does; `to_dict` is the wire shape.

Reading the manifest off disk is I/O and stays in the consumer. The data
itself, the circuit's current pins, lives beside this package in
`contracts/warden-stack.json`, outside the wheel, because a pin is state and
this package holds none. `tests/test_stack.py` checks that file against this
shape on every run, so the file can drift from the contract no further than
one failing test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = ["StackPin", "StackManifest"]


@dataclass(frozen=True)
class StackPin:
    """One checkout in the stack: its folder name and the commit it must be at."""

    name: str
    commit: str

    def pins(self, actual: str) -> bool:
        """Whether a checkout at `actual` satisfies this pin. A full commit must match
        exactly; an abbreviated pin of seven or more characters matches as a prefix."""
        if not actual:
            return False
        if actual == self.commit:
            return True
        return len(self.commit) >= 7 and actual.startswith(self.commit)

    def problems(self) -> Tuple[str, ...]:
        out = []
        if not self.name or not self.name.strip():
            out.append("a pin has no name")
        elif "/" in self.name or "\\" in self.name or self.name in (".", ".."):
            out.append(f"the pin {self.name!r} is a path, not a folder name")
        if not _is_hex(self.commit) or not 7 <= len(self.commit) <= 40:
            out.append(f"the pin {self.name!r} has commit {self.commit!r}, not 7 to 40 hex characters")
        return tuple(out)


@dataclass(frozen=True)
class StackManifest:
    """Which checkouts belong together: a schema name, the seat contract they speak, and the pins."""

    schema: str
    contract: str
    repos: Tuple[StackPin, ...]

    def pin_for(self, name: str) -> Optional[StackPin]:
        """The pin for a folder name, matched without regard to case, as a stack folder is."""
        wanted = name.casefold()
        for pin in self.repos:
            if pin.name.casefold() == wanted:
                return pin
        return None

    def problems(self) -> Tuple[str, ...]:
        """Everything wrong with this manifest, in plain words; empty when it can be used."""
        out = []
        if self.schema != "warden-stack/1":
            out.append(f"schema is {self.schema!r}, not 'warden-stack/1'")
        if not self.contract or not self.contract.strip():
            out.append("contract is empty")
        if not self.repos:
            out.append("no repositories are pinned")
        seen: Dict[str, str] = {}
        for pin in self.repos:
            out.extend(pin.problems())
            key = pin.name.casefold()
            if key in seen:
                out.append(f"{pin.name!r} is pinned twice (names are matched without regard to case)")
            seen.setdefault(key, pin.name)
        return tuple(out)

    def to_dict(self) -> Dict[str, object]:
        """The wire shape: {"schema", "contract", "repos": {name: commit}}."""
        return {
            "schema": self.schema,
            "contract": self.contract,
            "repos": {pin.name: pin.commit for pin in self.repos},
        }


def _is_hex(text: str) -> bool:
    return bool(text) and all(c in "0123456789abcdef" for c in text)

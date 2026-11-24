"""figure_check: does one document state two dollar figures that look like one figure mis-typed?

WHY THIS EXISTS

The evidence spine proves that every stage looked at the same text. It does not read the text. An invoice that says
$412.00 in one place and $421.00 in another (two digits swapped), or $412.00 and $4,120.00 (a decimal slip), passes
every gate, because each stage faithfully carried what it was given. A person catches this at a glance; nothing in
the spine did.

WHAT THIS DOES, AND DOES NOT

It finds pairs of different dollar figures in one text where one looks like a typing slip of the other:
two neighbouring digits swapped, or the same digits at a different size (a shifted decimal point or an extra zero).
It is a heuristic that raises a flag for a person. It does not know which figure is right, it does not catch a
document whose figures are all consistently wrong (the true text was inflated before HERALD read it), and two
different figures that merely resemble each other (a deposit and a balance) will be flagged too. A flag means "a
person looks", never "the document is false".
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import List, Tuple

__all__ = ["figures", "disagreements"]

_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")


def figures(text: str) -> List[str]:
    """Each dollar figure in `text`, as a string of cents with no separators, in order of appearance."""
    out = []
    for raw in _MONEY.findall(text):
        cents = int((Decimal(raw.replace(",", "")) * 100).to_integral_value())
        out.append(str(cents))
    return out


def _kind(a: str, b: str) -> str:
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]:
            return "swapped digits"
    if a.rstrip("0") == b.rstrip("0") and a != b:
        return "shifted size"
    return ""


def disagreements(text: str) -> List[Tuple[str, str, str]]:
    """(figure, figure, what looks wrong) for each pair of different figures in `text` that look like one mis-typed.
    Figures are shown as dollars, e.g. ("412.00", "421.00", "swapped digits"). Empty when there is nothing to flag."""
    seen: List[str] = []
    for c in figures(text):
        if c not in seen:
            seen.append(c)
    shown = lambda c: f"{int(c) // 100}.{int(c) % 100:02d}"  # noqa: E731
    return [(shown(a), shown(b), k) for i, a in enumerate(seen) for b in seen[i + 1:] if (k := _kind(a, b))]

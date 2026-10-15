"""cns.attack: one attack SWIZZLE reported against the governor.

WHY THIS EXISTS

SWIZZLE attacks the governor with scenarios and reports, for each, whether the governor
held. Warden reads that report and hands it to the Judge, which decides on it. The report
crosses repositories, so its row is shared here, the same way the suite result is.

WHAT IT CARRIES

`AttackResult` is the three fields the Judge reads: the scenario's name, the severity
SWIZZLE assigned it, and the status SWIZZLE gave it. The vocabulary of severity and
status belongs to SWIZZLE, so both are carried as text; this row checks that they are
text, not what they say. Running an attack is I/O and stays in SWIZZLE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

__all__ = ["AttackResult"]


def _required() -> tuple[str, ...]:
    """The fields every attack result names. A function, not a constant: this package holds no module-level state."""
    return ("scenario", "severity", "status")


@dataclass(frozen=True)
class AttackResult:
    """One scenario SWIZZLE attacked the governor with, and what came of it."""

    scenario: str
    severity: str
    status: str

    def problems(self) -> Tuple[str, ...]:
        """Everything wrong with this row, in plain words. Empty when it can be read."""
        out = []
        for name in _required():
            if not getattr(self, name).strip():
                out.append(f"{name} is empty")
        return tuple(out)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttackResult":
        """Read one attack result. Raises ValueError, naming the field, when it cannot be read.
        Extra keys are allowed and ignored."""
        if not isinstance(data, Mapping):
            raise ValueError("an attack result is an object, not " + type(data).__name__)
        values = {}
        for name in _required():
            if name not in data or data[name] is None:
                raise ValueError(f"{name} is missing or null, not text")
            if not isinstance(data[name], str):
                raise ValueError(f"{name} is {type(data[name]).__name__}, not text")
            values[name] = str(data[name])
        row = cls(**values)
        problems = row.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return row

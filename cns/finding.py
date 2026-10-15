"""cns.finding: one defect Ghost Tools reported, as the readers across the circuit see it.

WHY THIS EXISTS

Ghost Tools finds defects and writes them as findings. Warden turns them into the
defects it governs, the Drafter reads them to choose a fix, and the Finisher reads them
to know what remains open. Each of those reads a finding without a shared definition of
what a finding is, so a field renamed on one side breaks the others on the day nobody
expects it. This is the row they share.

WHAT IT CARRIES

`Finding` names the fields those readers rely on and their types. `id` is Ghost's own
identity for the finding and is never recomputed by a reader. Severity, status and the
detector name are carried as text: their vocabulary belongs to Ghost, and each reader
maps it for itself. `evidence` and `attributes` are carried as objects so a reader can
take the parts it needs without this row listing every key Ghost may add.

Extra keys are allowed and ignored. Running a scan is I/O and stays in Ghost Tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

__all__ = ["Finding"]


def _required() -> Tuple[str, ...]:
    """The text fields every finding names. A function, not a constant: this package holds no module-level state."""
    return ("id", "detector", "severity", "status", "summary")


@dataclass(frozen=True)
class Finding:
    """One defect Ghost Tools reported. Field names are the finding's JSON keys."""

    id: str
    detector: str
    severity: str
    status: str
    summary: str
    detail: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def problems(self) -> Tuple[str, ...]:
        """Everything wrong with this finding, in plain words. Empty when it can be read."""
        out = []
        for name in _required():
            if not getattr(self, name).strip():
                out.append(f"{name} is empty")
        return tuple(out)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Finding":
        """Read one finding. Raises ValueError, naming the field, when it cannot be read."""
        if not isinstance(data, Mapping):
            raise ValueError("a finding is an object, not " + type(data).__name__)
        values: Dict[str, str] = {}
        for name in _required():
            if name not in data or data[name] is None:
                raise ValueError(f"{name} is missing or null, not text")
            if not isinstance(data[name], str):
                raise ValueError(f"{name} is {type(data[name]).__name__}, not text")
            values[name] = str(data[name])
        detail = data.get("detail") or ""
        if not isinstance(detail, str):
            raise ValueError(f"detail is {type(detail).__name__}, not text")
        for name in ("evidence", "attributes"):
            if data.get(name) is not None and not isinstance(data[name], Mapping):
                raise ValueError(f"{name} is {type(data[name]).__name__}, not an object")
        row = cls(
            detail=str(detail),
            evidence=dict(data.get("evidence") or {}),
            attributes=dict(data.get("attributes") or {}),
            **values,
        )
        problems = row.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return row

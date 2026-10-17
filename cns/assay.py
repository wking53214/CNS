"""cns.assay: the summary ASSAY reports on an answer key, as one record.

WHY THIS EXISTS

ASSAY checks an answer key: a set of claims about a repository, each either holding or
failing, and a set of entries it found and how well each one is backed. It prints that
result as one machine-readable line, so a tool can read whether the key is proven without
parsing prose. This is the row that line is written against.

WHAT IT CARRIES

`AssaySummary` names the fields a reader may rely on: the schema name, whether every claim
holds, the status ASSAY gave, the claim and entry counts, and each failure. `counts` and
`status` are carried as objects and text: their vocabulary belongs to ASSAY. Reading the
line is I/O and stays in the consumer.

Extra keys are allowed and ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

__all__ = ["AssaySummary"]


def _schema() -> str:
    """The schema name this row is written against. A function, not a constant: this package holds no module-level state."""
    return "assay-summary/1"


@dataclass(frozen=True)
class AssaySummary:
    """One ASSAY answer-key result, as the summary line reports it. Field names are the JSON keys."""

    schema: str
    all_claims_hold: bool
    status: str
    claims: Mapping[str, Any] = field(default_factory=dict)
    entries: Mapping[str, Any] = field(default_factory=dict)
    failures: Tuple[Mapping[str, Any], ...] = ()

    def problems(self) -> Tuple[str, ...]:
        """Everything wrong with this summary, in plain words. Empty when it can be read."""
        out = []
        if self.schema != _schema():
            out.append(f"schema is {self.schema!r}, not {_schema()!r}")
        if not self.status.strip():
            out.append("status is empty")
        return tuple(out)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssaySummary":
        """Read one summary. Raises ValueError, naming every problem, when it cannot be read."""
        if not isinstance(data, Mapping):
            raise ValueError("an ASSAY summary is an object, not " + type(data).__name__)
        for key in ("schema", "all_claims_hold", "status"):
            if key not in data or data[key] is None:
                raise ValueError(f"{key} is missing or null")
        if not isinstance(data["schema"], str):
            raise ValueError(f"schema is {type(data['schema']).__name__}, not text")
        if not isinstance(data["all_claims_hold"], bool):
            raise ValueError(f"all_claims_hold is {type(data['all_claims_hold']).__name__}, not a true or false value")
        if not isinstance(data["status"], str):
            raise ValueError(f"status is {type(data['status']).__name__}, not text")
        for key in ("claims", "entries"):
            if data.get(key) is not None and not isinstance(data[key], Mapping):
                raise ValueError(f"{key} is {type(data[key]).__name__}, not an object")
        failures = data.get("failures")
        if failures is None:
            failures = []
        if not isinstance(failures, (list, tuple)):
            raise ValueError(f"failures is {type(failures).__name__}, not a list")
        if not all(isinstance(f, Mapping) for f in failures):
            raise ValueError("failures holds something that is not an object")
        row = cls(
            schema=data["schema"],
            all_claims_hold=data["all_claims_hold"],
            status=data["status"],
            claims=dict(data.get("claims") or {}),
            entries=dict(data.get("entries") or {}),
            failures=tuple(dict(f) for f in failures),
        )
        problems = row.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return row

"""cns.run: the record one circuit run leaves behind, the contract its readers join on.

WHY THIS EXISTS

Warden ends every `warden tagteam` run by printing one JSON object: the decision, the
Judge's verdict, what was measured, what was not. Until now that object had no contract.
The Watcher reads it, Warden writes it, and neither could say what the other promised.
A record format that changes silently breaks the reader on the day nobody expects it.

WHAT THIS MODULE DOES

`RunRecord` names the fields a reader may rely on and their types. Its key names are
Warden's own, so a record needs no mapping to become one. `problems` says what is wrong
with a record in plain words, and `from_dict` refuses a record that has problems rather
than reading half of it. Both are pure functions of the record's own fields.

Extra keys are allowed and ignored. A record that grows a field is still a valid record;
a record that loses or retypes a field named here is not.

Reading a file is I/O and stays in the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Tuple

__all__ = ["RunRecord"]


def _decisions() -> frozenset[str]:
    """The decisions Warden can end a run with. A record naming any other decision is refused.
    A function rather than a module-level constant: this package holds no module-level state."""
    return frozenset({
        "ACCEPT", "ACCEPT_UNVERIFIED", "REJECT", "REFUSED", "USAGE_ERROR", "SEAT_NOT_LOADED",
        "NOT_CONVERGED", "FINISH_REJECTED", "JUDGE_REJECTED", "INCONCLUSIVE", "ERROR", "INTERRUPTED",
        "TERMINATED",
    })



@dataclass(frozen=True)
class RunRecord:
    """One run, as the governor reports it. Field names are the record's JSON keys."""

    schema: str
    contract: str
    decision: str
    reason: str
    converged: bool
    finished: bool
    put_back: bool
    held_digest: str = ""
    unmeasured: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()
    observed: Tuple[str, ...] = ()
    verdict: Mapping[str, Any] = field(default_factory=dict)
    ghost_scan: Mapping[str, Any] = field(default_factory=dict)
    versions: Mapping[str, Any] = field(default_factory=dict)

    def problems(self) -> Tuple[str, ...]:
        """Everything wrong with this record, in plain words. Empty when it can be read."""
        out: List[str] = []
        if self.schema != "cns.run/1":
            out.append(f"schema is {self.schema!r}, not 'cns.run/1' (the record predates the contract)")
        if not self.contract.strip():
            out.append("contract is empty")
        if self.decision not in _decisions():
            out.append(f"decision {self.decision!r} is not one Warden ends a run with")
        return tuple(out)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RunRecord":
        """Read a record. Raises ValueError, naming every problem, when it cannot be read."""
        if not isinstance(data, Mapping):
            raise ValueError("a run record is an object, not " + type(data).__name__)
        missing = [k for k in ("schema", "contract", "decision", "reason", "converged", "finished", "put_back")
                   if k not in data]
        if missing:
            raise ValueError("a run record is missing " + ", ".join(missing))
        record = cls(
            schema=_text(data, "schema"),
            contract=_text(data, "contract"),
            decision=_text(data, "decision"),
            reason=_text(data, "reason"),
            converged=_flag(data, "converged"),
            finished=_flag(data, "finished"),
            put_back=_flag(data, "put_back"),
            held_digest=_text(data, "held_digest", required=False),
            unmeasured=_texts(data, "unmeasured"),
            notes=_texts(data, "notes"),
            observed=_texts(data, "observed"),
            verdict=_object(data, "verdict"),
            ghost_scan=_object(data, "ghost_scan"),
            versions=_object(data, "versions"),
        )
        problems = record.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return record


def _text(data: Mapping[str, Any], key: str, required: bool = True) -> str:
    if key not in data or data[key] is None:
        if required:
            raise ValueError(f"{key} is missing or null, not text")
        return ""
    if not isinstance(data[key], str):
        raise ValueError(f"{key} is {type(data[key]).__name__}, not text")
    return str(data[key])


def _flag(data: Mapping[str, Any], key: str) -> bool:
    value = data[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} is {type(value).__name__}, not a true or false value")
    return value


def _object(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} is {type(value).__name__}, not an object")
    return dict(value)


def _texts(data: Mapping[str, Any], key: str) -> Tuple[str, ...]:
    value = data.get(key)
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{key} is {type(value).__name__}, not a list")
    if not all(isinstance(v, str) for v in value):
        raise ValueError(f"{key} holds something that is not text")
    return tuple(value)

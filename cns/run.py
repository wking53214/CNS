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

WHAT 2.0.0 ADDED, AND WHY

A real record (Warden 0.13.6, kept as `tests/fixtures/warden_0_13_6_declined_record.json`) said
`unmeasured: []` and `converged: true` while `ghost_scan.declined` listed seven checks the scanner
was told to leave out, and a reader that looked only at the named fields reported "gaps: none".
Nothing in the record was false; the contract simply gave a reader no field for the rest of it.
So the row now names `reobserved` (the findings still there at the end), `declined` (read from
`ghost_scan.declined`) and `swizzle_sound`, and carries pure functions of itself: `gaps` is every
reason the run was less than fully measured, `participants` is the commit set that took part with
each part's `dirty` flag, `dirty_parts` the subset flagged dirty, `findings_remaining` the count
behind "converged", and `clean` the one claim that is stronger than ACCEPT. All of it is read from
fields Warden already writes; the schema stays `cns.run/1`.

2.1.0 adds two optional mappings, `claim` (the row that names the change a run governed: which commit, which
diff, which actor) and `evidence` (the Judge's input as written). Both are read when present and None when
absent; the schema stays `cns.run/1`, and a reader older than this field ignores the keys as it always did.

Reading a file is I/O and stays in the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Tuple

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
    #: Finding identities still reported at the end of the run. Empty when the scanner never ran, too.
    reobserved: Tuple[str, ...] = ()
    #: Checks the scanner was told to leave out (`ghost_scan.declined`). A declined check did not run.
    declined: Tuple[str, ...] = ()
    #: True: SWIZZLE's own proofs held. False: they did not. None: the record does not say.
    swizzle_sound: Optional[bool] = None
    #: The row that names the change a run governed: which commit, which diff, which actor. Warden writes its
    #: keys; this contract types it no further than a mapping. None: the record does not carry one (2.1.0).
    claim: Optional[Mapping[str, object]] = None
    #: The Judge's input as written, the `cns.seat.Evidence` the governor assembled, as a mapping. None: the
    #: record does not carry it (2.1.0).
    evidence: Optional[Mapping[str, object]] = None

    def gaps(self) -> Tuple[str, ...]:
        """Every reason this run was less than fully measured, in words: each check that did not run, each
        check that was declined, each gap the scanner reported, each part that took part with uncommitted
        changes. Empty only when nothing in the record says a measurement is missing."""
        out = [f"unmeasured: {name}" for name in self.unmeasured]
        out += [f"declined: {name}" for name in self.declined]
        reported = self.ghost_scan.get("gaps")
        if isinstance(reported, (list, tuple)):
            out += [f"ghost: {gap}" for gap in reported if isinstance(gap, str)]
        out += [f"dirty: {name}" for name in self.dirty_parts()]
        return tuple(out)

    def participants(self) -> Tuple[Tuple[str, str, Optional[bool]], ...]:
        """(name, commit, dirty) for every part the record says took part: Warden, each instrument, each
        seat, each joined checkout. The commit is empty and dirty is None where the record does not say."""
        out: List[Tuple[str, str, Optional[bool]]] = []
        for name in ("warden", "ghost_tools", "swizzle", "assay"):
            entry = self.versions.get(name)
            if isinstance(entry, Mapping):
                out.append((name, _commit_of(entry), _dirty_of(entry)))
        seats = self.versions.get("seats")
        if isinstance(seats, Mapping):
            for role, seat in seats.items():
                if isinstance(seat, Mapping):
                    out.append((f"{role} seat", _commit_of(seat), _dirty_of(seat)))
        joins = self.versions.get("joins")
        if isinstance(joins, (list, tuple)):
            for join in joins:
                if isinstance(join, Mapping):
                    out.append((f"join {join.get('path')}", _commit_of(join), _dirty_of(join)))
        return tuple(out)

    def dirty_parts(self) -> Tuple[str, ...]:
        """The participants whose `dirty` flag is true. A null flag is not dirty; it is unknown."""
        return tuple(name for name, _, dirty in self.participants() if dirty is True)

    @property
    def findings_remaining(self) -> int:
        """How many findings the scanner still reported at the end. Converged means no proposals were left,
        which is not this being zero."""
        return len(self.reobserved)

    @property
    def clean(self) -> bool:
        """ACCEPT, converged, nothing put back, no gap of any kind and no finding remaining. The claim a
        reader usually means by "it passed", which ACCEPT alone does not make."""
        return (self.decision == "ACCEPT" and self.converged and not self.put_back
                and not self.gaps() and self.findings_remaining == 0)

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
        ghost_scan = _object(data, "ghost_scan")
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
            ghost_scan=ghost_scan,
            versions=_object(data, "versions"),
            reobserved=_texts(data, "reobserved"),
            declined=_texts(ghost_scan, "declined", label="ghost_scan.declined"),
            swizzle_sound=_optional_flag(data, "swizzle_sound"),
            claim=_optional_object(data, "claim"),
            evidence=_optional_object(data, "evidence"),
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


def _optional_flag(data: Mapping[str, Any], key: str) -> Optional[bool]:
    value = data.get(key)
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{key} is {type(value).__name__}, not a true or false value or null")
    return value


def _commit_of(entry: Mapping[str, Any]) -> str:
    value = entry.get("commit")
    return value if isinstance(value, str) else ""


def _dirty_of(entry: Mapping[str, Any]) -> Optional[bool]:
    value = entry.get("dirty")
    return value if isinstance(value, bool) else None


def _object(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} is {type(value).__name__}, not an object")
    return dict(value)


def _optional_object(data: Mapping[str, Any], key: str) -> Optional[Mapping[str, Any]]:
    """An object the record may leave out: None when absent or null, the mapping when present."""
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} is {type(value).__name__}, not an object or null")
    return dict(value)


def _texts(data: Mapping[str, Any], key: str, label: Optional[str] = None) -> Tuple[str, ...]:
    value = data.get(key)
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label or key} is {type(value).__name__}, not a list")
    if not all(isinstance(v, str) for v in value):
        raise ValueError(f"{label or key} holds something that is not text")
    return tuple(value)

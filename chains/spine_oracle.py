"""The oracle behind `spine_run.py`: what a scenario must produce, and how a result is judged against it.

This module imports no component repository, so its own tests can run in the CNS suite. `spine_run.py` imports it
(`Expect`, `refused`, `judge`, `check_table`); a scenario's third element is an `Expect` and nothing else. The older
plain-string form ("" meant no problems, otherwise some problem contained the text) is gone: it passed a scenario for any
unrelated problem that happened to contain the text, so a `str` is a TypeError when the table is loaded.

An `Expect` says which of four things the scenario must do:
  clean     it returns no problems (a check that holds).
  gap       it returns no problems; a KNOWN GAP recorded as a fact, which goes red the day the gap closes.
  problems  it returns problems. Every text in `required` appears in some problem. Every problem contains a
            `required` or an `allowed_extra` text, so an unrelated extra problem fails the scenario.
  refused   as `problems`, for a boundary that raised. `raises` names the exception classes accepted; at least one
            problem must start with one of them.
`forbidden` texts must appear in no problem, whatever the outcome. A scenario that raises fails, unless its outcome is
`refused` and the exception class name is one of `raises`. Anything raised that is not an `Exception` (SystemExit,
KeyboardInterrupt, GeneratorExit) is a crash of that scenario: it always fails the scenario and never ends the run.

A `refused` scenario must also show that the attack call was made and refused. Text a scenario returns is not that
evidence (a scenario that let the attack through can return the refusal text), so `refused()` records every call it
makes and every refusal it catches, and `judge` requires a refusal recorded while the scenario ran (or the scenario
itself raising an exception class it declares). The record is a counter, not an element of the returned list, because
rows branch on whether `refused()` returned anything.
"""

from __future__ import annotations

import dataclasses
import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

OUTCOMES = ("clean", "problems", "refused", "gap")
STATE_CHANGED = "state changed after refusal"


@dataclass(frozen=True)
class Expect:
    outcome: str
    required: Tuple[str, ...] = ()
    allowed_extra: Tuple[str, ...] = ()
    forbidden: Tuple[str, ...] = ()
    raises: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"Expect.outcome must be one of {OUTCOMES}, not {self.outcome!r}")
        for name in ("required", "allowed_extra", "forbidden", "raises"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(type(t) is str and t.strip() for t in value):
                raise TypeError(f"Expect.{name} must be a tuple of exact, non-blank str (a str subclass or a text of "
                                "only whitespace matches anything it should not)")
        if self.outcome in ("problems", "refused") and not self.required:
            raise ValueError(f"an Expect with outcome {self.outcome!r} must name the problem it requires")
        if self.outcome in ("clean", "gap") and (self.required or self.allowed_extra or self.raises):
            raise ValueError(f"an Expect with outcome {self.outcome!r} expects no problems; it takes only forbidden")
        if self.raises and self.outcome != "refused":
            raise ValueError("only a refused Expect may name the exceptions it accepts")


Expectation = Expect
CAUGHT = (ValueError, TypeError, OverflowError)

_EVIDENCE_LOCK = threading.Lock()
_CALLS = 0
_REFUSALS = 0


def _evidence() -> Tuple[int, int]:
    with _EVIDENCE_LOCK:
        return _CALLS, _REFUSALS


def entries_digest(entries: Iterable[Any]) -> str:
    """A digest of the whole content of every entry, in order, so a refusal that edited an entry and kept its hash shows.

    A dataclass entry is read field by field (nested dataclasses included); anything else by its repr. The hashes an entry
    carries are part of its content, so a swapped or reordered entry shows too."""
    h = hashlib.sha256()
    for entry in entries:
        body = repr(dataclasses.asdict(entry)) if dataclasses.is_dataclass(entry) and not isinstance(entry, type) else repr(entry)
        h.update(hashlib.sha256(body.encode("utf-8", "surrogatepass")).digest())
    return h.hexdigest()


def refused(thunk: Callable[[], Any], *, catch: Tuple[type, ...] = (), state: Optional[Callable[[], Any]] = None) -> List[str]:
    """What a boundary refused, as a problem string, or nothing if it let the call through.

    `state`, when given, is read before and after; a refusal that left the state different is reported as a second
    problem, because a refused call must change nothing."""
    global _CALLS, _REFUSALS
    before = state() if state is not None else None
    with _EVIDENCE_LOCK:
        _CALLS += 1
    try:
        thunk()
    except CAUGHT + tuple(catch) as exc:
        with _EVIDENCE_LOCK:
            _REFUSALS += 1
        out = [f"{type(exc).__name__}: {exc}"]
        if state is not None:
            after = state()
            if after != before:
                out.append(f"{STATE_CHANGED}: before {before!r}, after {after!r}")
        return out
    return []


def check_table(table: Sequence[Tuple[Any, ...]]) -> None:
    """Refuse a scenario table that is not (name, callable, Expect) rows, with unique names. Called when the table loads."""
    seen = set()
    for row in table:
        if not isinstance(row, tuple) or len(row) != 3:
            raise TypeError(f"a scenario is (name, scenario, Expect); got {row!r}")
        name, scenario, expect = row
        if not isinstance(name, str) or not name:
            raise TypeError(f"a scenario name must be a non-empty str; got {name!r}")
        if not callable(scenario):
            raise TypeError(f"scenario {name!r} must be callable")
        if not isinstance(expect, Expect):
            raise TypeError(f"scenario {name!r} must declare an Expect, not {type(expect).__name__}: a plain string "
                            "expectation is no longer accepted")
        if name in seen:
            raise ValueError(f"scenario name {name!r} appears twice")
        seen.add(name)


def judge(expect: Expect, scenario: Callable[[], List[str]]) -> Tuple[List[str], List[str]]:
    """Run a scenario and return (problems it produced, reasons it failed). No reasons means it passed."""
    if not isinstance(expect, Expect):
        raise TypeError(f"a scenario must declare an Expect, not {type(expect).__name__}")
    raised: Optional[BaseException] = None
    refusals_before = _evidence()[1]
    try:
        found = list(scenario())
    except BaseException as exc:  # noqa: BLE001 - a scenario that crashes (SystemExit and KeyboardInterrupt too) is judged, not propagated
        raised, found = exc, [f"{type(exc).__name__}: {exc}"]
    why: List[str] = []
    if raised is not None:
        if not isinstance(raised, Exception):
            return found, [f"the scenario ended with {found[0]}, which is not an exception a scenario may raise; it is a crash of the scenario"]
        if expect.outcome != "refused" or type(raised).__name__ not in expect.raises:
            return found, [f"the scenario raised {found[0]}, which this scenario does not declare"]
    if expect.outcome in ("clean", "gap"):
        if found:
            why.append("expected no problems" + (" (the gap has closed)" if expect.outcome == "gap" else ""))
    else:
        if not found:
            why.append("expected problems and got none (the attack went through)")
        for text in expect.required:
            if not any(text in p for p in found):
                why.append(f"missing required problem {text!r}")
        listed = expect.required + expect.allowed_extra
        for p in found:
            if not any(t in p for t in listed):
                why.append(f"unlisted extra problem {p!r}")
        if expect.outcome == "refused" and raised is None and _evidence()[1] == refusals_before:
            why.append("no refusal was recorded while the scenario ran: it returned refusal text without making an attack call "
                       "that a boundary refused (use refused() around the attack call)")
        if expect.outcome == "refused" and expect.raises and found and not any(
                p.startswith(c + ":") for p in found for c in expect.raises):
            why.append(f"no problem starts with an accepted exception class {expect.raises}")
    for text in expect.forbidden + ((STATE_CHANGED,) if expect.outcome == "refused" else ()):
        if any(text in p for p in found):
            why.append(f"forbidden text {text!r} appeared")
    return found, why

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
`refused` and the exception class name is one of `raises`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

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
            if not isinstance(value, tuple) or not all(isinstance(t, str) and t for t in value):
                raise TypeError(f"Expect.{name} must be a tuple of non-empty strings")
        if self.outcome in ("problems", "refused") and not self.required:
            raise ValueError(f"an Expect with outcome {self.outcome!r} must name the problem it requires")
        if self.outcome in ("clean", "gap") and (self.required or self.allowed_extra or self.raises):
            raise ValueError(f"an Expect with outcome {self.outcome!r} expects no problems; it takes only forbidden")
        if self.raises and self.outcome != "refused":
            raise ValueError("only a refused Expect may name the exceptions it accepts")


Expectation = Expect
CAUGHT = (ValueError, TypeError, OverflowError)


def refused(thunk: Callable[[], Any], *, catch: Tuple[type, ...] = (), state: Optional[Callable[[], Any]] = None) -> List[str]:
    """What a boundary refused, as a problem string, or nothing if it let the call through.

    `state`, when given, is read before and after; a refusal that left the state different is reported as a second
    problem, because a refused call must change nothing."""
    before = state() if state is not None else None
    try:
        thunk()
    except CAUGHT + tuple(catch) as exc:
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
    try:
        found = list(scenario())
    except Exception as exc:  # noqa: BLE001 - a scenario that crashes is judged, not propagated
        raised, found = exc, [f"{type(exc).__name__}: {exc}"]
    why: List[str] = []
    if raised is not None:
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
        if expect.outcome == "refused" and expect.raises and found and not any(
                p.startswith(c + ":") for p in found for c in expect.raises):
            why.append(f"no problem starts with an accepted exception class {expect.raises}")
    for text in expect.forbidden + ((STATE_CHANGED,) if expect.outcome == "refused" else ()):
        if any(text in p for p in found):
            why.append(f"forbidden text {text!r} appeared")
    return found, why

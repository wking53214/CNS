"""decision_guard: a one-use permission, issued by an approved decision, for one thing to happen to one document.

WHY THIS EXISTS

A SuperGate says whether a decision is a go. Nothing stops a caller from then doing the action anyway after a
"no", or doing it twice, or doing it to a different document than the one the gates judged. The action (here:
registering a root in the Conservation_Kernel) lives in another repository, and the kernel imports no CNS. What it
does offer is a hook: a callable it asks, last, before it registers a root, where only `True` permits.

`DecisionGuard` is that callable. It starts closed. It opens only when it is handed a Decision that `SuperGate.decide` issued (`decision.issued`),
that is `allowed`, that carries a `subject` (the roster had `same_subject` and every seat agreed), and whose root is
recomputed from its own verdicts. A decision written by hand, or copied field by field, is refused however
complete it looks: the proof of issue is a process-local key, so it settles where a decision came from only inside
this process. When the kernel then asks about an artifact, the guard answers True only if:

  - it was authorized, and has not already said yes (one use: the permission is spent by the first yes),
  - the decision has not expired, and
  - the artifact reads, through `subject_of`, as exactly the identity and content digest the decision approved.

One decision opens one action: every decision carries a nonce, and the first guard authorized with it spends the nonce
for the whole process. A second guard handed the same decision, however fresh, is refused. That is in-process only:
the spent set lives in this module, so two processes can each spend the same decision.

Anything else is False: nothing authorized, a refused or unbound decision, a second use, another document, a reader
that raises. A refusal does not spend the permission; only a yes does.

BOUND TO A SEAT'S VERDICT, NOT ONLY TO A DOCUMENT

The document check says which text the decision was about. It does not say which thing is about to happen to it: two
different artifacts, or two different calls, can carry the same source and the same text. A guard built with `seat`
and `binding_of` also opens only for the exact object one seat judged. `authorize` finds that seat's PASS verdict in
the decision and keeps what it is bound to, `(subject, subject_digest)`; the guard then answers True only if
`binding_of(artifact)` is that pair. `binding_of` should use the digest function the seat's own repository exports
(the one that repository's gate binds its verdict with), so the permission is for the same object the gate judged,
every field of it. Without `seat`, the guard checks the document only, as before.

BOUND TO A ROSTER

`Decision.issued` proves that some SuperGate in this process issued the decision, not that the roster the caller
meant to consult did. A guard built with `required_seats` refuses a decision whose roster does not seat every one of
them, so a short roster of gates that pass anything cannot open it. This checks seat names, which the decision's root
covers, not what stands behind a name: a roster that reuses the names with other gates is not caught here, because
nothing in a decision says which gate objects ran. Treat it as closing the careless and the lazy substitution, and
keep the guard and the roster's construction in the same reviewed file.

WHAT IT DOES NOT DO

It protects a kernel that was built with it. A caller who builds a kernel without a guard, or who writes to a ledger
they built themselves, is not stopped, and nothing here can see that. `subject_of` is policy, like the readers in
`SuperGate(same_subject=...)`: it is only as honest as the file it lives in, so keep it next to the required roster.
It imports no repository.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Iterable, Optional, Set, Tuple

from cns.gate import GateOutcome

from .super_gate import Decision, Judged

__all__ = ["DecisionGuard"]

#: Nonces of decisions some guard in this process was authorized with, taken under the lock so two guards racing for
#: one decision cannot both win. Kept for the life of the process.
_SPENT: Set[str] = set()
_SPENT_LOCK = threading.Lock()


class DecisionGuard:
    """Closed until authorized by an approved decision; then opens once, for the one document that decision judged."""

    def __init__(self, subject_of: Callable[[object], Judged], *, clock: Callable[[], float] = time.time,
                 seat: Optional[str] = None,
                 binding_of: Optional[Callable[[object], Tuple[str, str]]] = None,
                 required_seats: Iterable[str] = ()) -> None:
        if not callable(subject_of):
            raise ValueError("subject_of must be a function that reads which document an artifact is")
        if not callable(clock):
            raise ValueError("clock must be a function that returns the time in seconds")
        if (seat is None) != (binding_of is None):
            raise ValueError("seat and binding_of go together: a seat to bind to needs a reader of what it judged")
        if seat is not None and not (isinstance(seat, str) and ":" in seat and all(seat.split(":", 1))):
            raise ValueError("seat must name a seat of the roster as 'repository:gate'")
        if binding_of is not None and not callable(binding_of):
            raise ValueError("binding_of must be a function that reads what an artifact's verdict is bound to")
        required = tuple(required_seats)
        if any(not isinstance(name, str) or not name for name in required) or len(set(required)) != len(required):
            raise ValueError("required_seats must be distinct, non-empty seat names")
        self._subject_of = subject_of
        self._clock = clock
        self._required_seats = required
        self._seat = seat
        self._binding_of = binding_of
        self._bound_to: Optional[Tuple[str, str]] = None
        #: Held across the whole of `__call__`, so two callers cannot both read "not spent" and both be told yes.
        self._lock = threading.Lock()
        self._expires_at: Optional[float] = None
        self._approved: Optional[Judged] = None
        self._spent = False

    @property
    def authorized(self) -> bool:
        return self._approved is not None

    @property
    def spent(self) -> bool:
        return self._spent

    def authorize(self, decision: Decision) -> None:
        """Open the guard for the document `decision` approved. Raises ValueError, leaving the guard closed, unless
        the decision was issued by a SuperGate, is allowed, carries a subject, binds its own root, has not expired,
        has not already authorized a guard, and this guard has not been authorized."""
        if self._approved is not None:
            raise ValueError("this guard was already authorized; one guard serves one decision")
        if not decision.allowed:
            raise ValueError("a decision that is not a go cannot authorize anything: " + "; ".join(decision.reasons()))
        if decision.subject is None:
            raise ValueError("the decision records no subject, so there is no document to authorize")
        if not decision.binds(decision.root):
            raise ValueError("the decision's root does not match its own verdicts")
        if not decision.issued:
            raise ValueError("this decision was not issued by a SuperGate in this process, so it cannot authorize "
                             "anything")
        if decision.expires_at is not None and self._clock() >= decision.expires_at:
            raise ValueError("the decision has expired, so it cannot authorize anything")
        absent = [name for name in self._required_seats if name not in decision.seats]
        if absent:
            raise ValueError("the decision's roster lacks required seat(s), so it cannot authorize this guard: "
                             + ", ".join(absent))
        bound_to = self._seat_binding(decision)
        with _SPENT_LOCK:
            if decision.nonce in _SPENT:
                raise ValueError("this decision has already authorized a guard; one decision opens one action")
            _SPENT.add(decision.nonce)
        self._approved = decision.subject
        self._bound_to = bound_to
        self._expires_at = decision.expires_at

    def _seat_binding(self, decision: Decision) -> Optional[Tuple[str, str]]:
        """What the bound seat's verdict is bound to, or None when this guard binds no seat. Raises ValueError
        unless that seat is on the roster and its one verdict is a PASS that records what it judged."""
        if self._seat is None:
            return None
        if self._seat not in decision.seats:
            raise ValueError(f"the decision's roster has no seat {self._seat}, so it cannot authorize this guard")
        gate = self._seat.split(":", 1)[1]
        verdicts = [r for r in decision.run.results if r.gate == gate]
        if len(verdicts) != 1:
            raise ValueError(f"the decision holds {len(verdicts)} verdicts named {gate}, so there is no one verdict "
                             f"to bind to for {self._seat}")
        verdict = verdicts[0]
        if verdict.outcome is not GateOutcome.PASS or not verdict.bound():
            raise ValueError(f"{self._seat} did not pass with a verdict that records what it judged, so there is "
                             "nothing to bind the permission to")
        return verdict.subject, verdict.subject_digest

    def __call__(self, artifact: object) -> bool:
        with self._lock:
            return self._answer(artifact)

    def _answer(self, artifact: object) -> bool:
        if self._approved is None or self._spent:
            return False
        if self._expires_at is not None and self._clock() >= self._expires_at:
            return False
        try:
            judged = self._subject_of(artifact)
        except Exception:  # a reader that cannot answer never permits
            return False
        if not (isinstance(judged, Judged) and judged == self._approved):
            return False
        if self._binding_of is not None:
            try:
                bound = self._binding_of(artifact)
            except Exception:  # a reader that cannot say what this is never permits
                return False
            if not (isinstance(bound, tuple) and len(bound) == 2 and bound == self._bound_to):
                return False
        self._spent = True
        return True

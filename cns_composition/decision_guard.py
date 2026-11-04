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

WHO SETS THE ROSTER

A SuperGate refuses a roster built without the seats its builder named, and cannot refuse a builder who names fewer.
The party that ACTS is the one that knows which seats it needs, so it says so here, in its own file:

  `expected_seats`   the seats (`repository:gate`) this action needs. A decision whose roster lacks any of them is
                     refused, and the refusal names the missing ones. Seats beyond these are fine: more gates never
                     weaken a decision. Written by hand, never built from the roster being checked, or a missing seat
                     is missing from both.
  `expected_context` what this action is (the action, the tenant, the policy version). A decision made for another
                     context, or for none, is refused.

Left out, either check is simply not made: a guard with no `expected_seats` accepts whatever roster the issuer chose,
and `expected_seats` is None so a test can assert it was set.
  `require_strict_binding`  the decision came from a roster built with `strict_binding=True`, so each PASS was checked
                     against the candidate its own seat was handed and not taken on the gate's word.

A name is still not the code behind it: nothing here
can tell that a seat's gate is the one the repository ships.

WHAT IT DOES NOT DO

It protects a kernel that was built with it. A caller who builds a kernel without a guard, or who writes to a ledger
they built themselves, is not stopped, and nothing here can see that. `subject_of` is policy, like the readers in
`SuperGate(same_subject=...)`: it is only as honest as the file it lives in, so keep it next to the required roster.
It imports no repository.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Iterable, Mapping, Optional, Set, Tuple

from .super_gate import Decision, Judged, digest_context

__all__ = ["DecisionGuard"]

#: Nonces of decisions some guard in this process was authorized with, taken under the lock so two guards racing for
#: one decision cannot both win. Kept for the life of the process.
_SPENT: Set[str] = set()
_SPENT_LOCK = threading.Lock()


class DecisionGuard:
    """Closed until authorized by an approved decision; then opens once, for the one document that decision judged."""

    def __init__(self, subject_of: Callable[[object], Judged], *, clock: Callable[[], float] = time.time,
                 expected_seats: Optional[Iterable[str]] = None,
                 expected_context: Optional[Mapping[str, str]] = None, require_strict_binding: bool = False) -> None:
        if not callable(subject_of):
            raise ValueError("subject_of must be a function that reads which document an artifact is")
        if not callable(clock):
            raise ValueError("clock must be a function that returns the time in seconds")
        self._subject_of = subject_of
        self._clock = clock
        self._expected_seats: Optional[Tuple[str, ...]] = None
        if expected_seats is not None:
            if isinstance(expected_seats, (str, bytes)):
                raise ValueError("expected_seats must be a collection of seat names, not one string")
            seats = tuple(expected_seats)
            if not seats:
                raise ValueError("expected_seats is empty, so it would expect nothing; leave it out to pin no roster")
            if any(not isinstance(s, str) or not s for s in seats):
                raise ValueError("expected_seats names must be non-empty text")
            if len(set(seats)) != len(seats):
                raise ValueError("expected_seats names a seat twice")
            self._expected_seats = seats
        self._require_strict_binding = bool(require_strict_binding)
        self._expected_context = digest_context(expected_context) if expected_context is not None else ""
        if expected_context is not None and not self._expected_context:
            raise ValueError("expected_context binds nothing")
        self._expires_at: Optional[float] = None
        self._approved: Optional[Judged] = None
        self._spent = False

    @property
    def authorized(self) -> bool:
        return self._approved is not None

    @property
    def spent(self) -> bool:
        return self._spent

    @property
    def expected_seats(self) -> Optional[Tuple[str, ...]]:
        """The seats this guard holds a decision to, or None when it pins no roster."""
        return self._expected_seats

    def authorize(self, decision: Decision) -> None:
        """Open the guard for the document `decision` approved. Raises ValueError, leaving the guard closed and the
        decision unspent, unless the decision was issued by a SuperGate, is allowed, carries a subject, binds its own
        root, has not expired, covers every seat in `expected_seats` and was made for `expected_context` when this
        guard has them, has not already authorized a guard, and this guard has not been authorized."""
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
        if self._expected_seats is not None:
            absent = [seat for seat in self._expected_seats if seat not in decision.seats]
            if absent:
                raise ValueError("the decision was not made on the roster this action needs; its roster lacks: "
                                 + ", ".join(absent))
        if self._require_strict_binding and not decision.strict_binding:
            raise ValueError("this guard requires strict binding, and the roster that decided did not check each "
                             "seat's verdict against its own candidate")
        if self._expected_context and decision.context_digest != self._expected_context:
            raise ValueError("the decision was made for a different context than this action, or for none")
        with _SPENT_LOCK:
            if decision.nonce in _SPENT:
                raise ValueError("this decision has already authorized a guard; one decision opens one action")
            _SPENT.add(decision.nonce)
        self._approved = decision.subject
        self._expires_at = decision.expires_at

    def __call__(self, artifact: object) -> bool:
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
        self._spent = True
        return True

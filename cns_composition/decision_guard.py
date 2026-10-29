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

  - it was authorized, and has not already said yes (one use: the permission is spent by the first yes), and
  - the artifact reads, through `subject_of`, as exactly the identity and content digest the decision approved.

Anything else is False: nothing authorized, a refused or unbound decision, a second use, another document, a reader
that raises. A refusal does not spend the permission; only a yes does.

WHAT IT DOES NOT DO

It protects a kernel that was built with it. A caller who builds a kernel without a guard, or who writes to a ledger
they built themselves, is not stopped, and nothing here can see that. `subject_of` is policy, like the readers in
`SuperGate(same_subject=...)`: it is only as honest as the file it lives in, so keep it next to the required roster.
It imports no repository.
"""

from __future__ import annotations

from typing import Callable, Optional

from .super_gate import Decision, Judged

__all__ = ["DecisionGuard"]


class DecisionGuard:
    """Closed until authorized by an approved decision; then opens once, for the one document that decision judged."""

    def __init__(self, subject_of: Callable[[object], Judged]) -> None:
        if not callable(subject_of):
            raise ValueError("subject_of must be a function that reads which document an artifact is")
        self._subject_of = subject_of
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
        the decision was issued by a SuperGate, is allowed, carries a subject, binds its own root, and this guard
        has not been authorized."""
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
        self._approved = decision.subject

    def __call__(self, artifact: object) -> bool:
        if self._approved is None or self._spent:
            return False
        try:
            judged = self._subject_of(artifact)
        except Exception:  # a reader that cannot answer never permits
            return False
        if not (isinstance(judged, Judged) and judged == self._approved):
            return False
        self._spent = True
        return True

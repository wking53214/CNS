"""grants: what THIS receiver permits, for which purpose, to whom, until when, and with whose approval.

WHY THIS EXISTS

A signature is not permission, and a manifest is an advertisement. A verified decision says a decider judged a document;
it does not say this receiver will act on it. Without a receiver-side step, any code that holds a `Verified` decision
decides for itself what that permits. A `GrantTable` is that step. It is the receiver's own policy, default deny, and
nothing a sender signs can add to it.

THE QUESTIONS IT ANSWERS (each a stable refusal code)

  Is there a grant at all for this capability and version?     no_grant
  Is it still in force, and not withdrawn?                      grant_expired, withdrawn
  Is the decider one this grant names?                          decider
  Is the action one this grant names?                           action
  Will this receiver disclose what the terms ask to see?        disclosure   (a ceiling on `terms["disclose"]`)
  Does this action need a human, and did one say yes?           approval_required, approval
  Could the evidence be retained?                               unavailable  (the audit write failed, so nothing is permitted)

PURPOSE needs no new field on the wire. UAI-1 terms are signed over the capability NAME and VERSION, so a purpose is
a capability name that carries it (`income-screen.loan-underwriting`). A decision negotiated under one purpose names
that capability and a grant for another purpose does not match it. The receiver chooses its purposes by choosing the
names it grants.

HUMAN APPROVAL is local to the receiver. An `Approval` is signed by an approver identity the grant lists, bound to
one decision, one action and one document, and expires. The approver can never be the decider, the requester, or any
identity the receiver treats as an agent, so an agent or a model cannot approve its own recommendation. This module
never gives any signing key to an adapter (adapter.py); approval keys belong to people.

EVIDENCE: every permit and every refusal is appended to a hash-chained audit record. Each entry carries the digest of
the one before, so removing or editing an entry is detectable (`verify_audit`); it does not stop someone with write
access from truncating the tail, which is what an external anchor of the last digest is for.

NOT HERE: delegation (a grant is for the requester it names, and cannot be passed on), and a shared grant store across
hosts (the table is one receiver's own memory, loaded from its own configuration).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional

from cns.gate import subject_digest

from . import crypto_backend
from .decision import Verified
from .envelope import MAX_INT, Refused, now_ms
from .identity import Signer, is_agent_id, public_of

__all__ = ["Grant", "GrantTable", "Approval", "approve", "Permit", "verify_audit"]

_APPROVAL_TAG = b"uai/1 approval\n"


@dataclass(frozen=True)
class Grant:
    """One purpose-bound permission. `capability` is the (purpose-carrying) name the terms must name."""

    id: str
    capability: str
    version: int
    requester: str                               # the identity this receiver acts as; the grant is for no one else
    deciders: FrozenSet[str]
    actions: FrozenSet[str]
    disclose_max: FrozenSet[str] = frozenset()   # the most this receiver will let the decider see; empty means nothing
    expires_at: Optional[int] = None             # None: no expiry (a receiver may choose that; it is its own)
    approvers: FrozenSet[str] = frozenset()      # humans whose approval an action needs; empty means none is needed
    retain_ms: int = 0                           # how long the audit entry for this grant must be kept (recorded)

    def __post_init__(self) -> None:
        if not self.id or not self.capability or not self.actions or not self.deciders:
            raise ValueError("a grant names an id, a capability, at least one decider and at least one action")
        if not is_agent_id(self.requester) or not all(is_agent_id(d) for d in self.deciders | self.approvers):
            raise ValueError("requester, deciders and approvers are agent identities")
        if self.approvers & (self.deciders | {self.requester}):
            raise ValueError("an approver is never the decider or the requester: a party cannot approve itself")
        for name in ("deciders", "actions", "disclose_max", "approvers"):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version is a positive integer")


@dataclass(frozen=True)
class Approval:
    """A human's signed yes to ONE action on ONE document under ONE decision."""

    approver: str
    decision_id: str
    action: str
    subject_digest: str
    expires_at: int
    sig: str

    def body(self) -> Dict[str, Any]:
        return {"approver": self.approver, "decision_id": self.decision_id, "action": self.action,
                "subject_digest": self.subject_digest, "expires_at": self.expires_at}


def approve(approver: Signer, verified: Verified, action: str, *, ttl_ms: int = 300_000,
            now: Optional[int] = None) -> Approval:
    """What a person's tool calls after reading what the decision and the action are."""
    t = now_ms() if now is None else now
    draft = Approval(approver=approver.agent, decision_id=verified.envelope.id, action=action,
                     subject_digest=verified.subject["digest"], expires_at=t + ttl_ms, sig="")
    sig = approver.sign(_APPROVAL_TAG + subject_digest(draft.body()).encode("ascii"))
    return Approval(approver=draft.approver, decision_id=draft.decision_id, action=action,
                    subject_digest=draft.subject_digest, expires_at=draft.expires_at, sig=sig.hex())


@dataclass(frozen=True)
class Permit:
    """The receiver's yes. Holding one is what an action may rely on, not holding a Verified decision."""

    grant: str
    action: str
    capability: str
    version: int
    decision_id: str
    subject_digest: str
    approver: str
    audit_digest: str


class GrantTable:
    def __init__(self, grants: List[Grant] = (), *, audit_path: "os.PathLike[str] | str | None" = None) -> None:  # type: ignore[assignment]
        self._grants: Dict[tuple, Grant] = {}
        for g in grants:
            if (g.capability, g.version) in self._grants:
                raise ValueError(f"two grants for {g.capability} version {g.version}")
            self._grants[(g.capability, g.version)] = g
        self._withdrawn: set = set()
        self._lock = threading.Lock()
        self._audit = Path(audit_path) if audit_path is not None else None
        self._last = "0" * 64
        if self._audit is not None:
            self._audit.parent.mkdir(parents=True, exist_ok=True)
            self._last = verify_audit(self._audit)

    def withdraw(self, grant_id: str) -> None:
        """Permission withdrawn. From the next `permit` on, every action under this grant is refused (`withdrawn`)."""
        with self._lock:
            self._withdrawn.add(grant_id)

    def _grant_for(self, capability: Any, version: Any) -> Grant:
        g = self._grants.get((capability, version)) if isinstance(capability, str) else None
        if g is None:
            raise Refused("no_grant", "this receiver has granted nothing for that capability and version")
        return g

    def check_terms(self, terms: Mapping[str, Any], *, now: Optional[int] = None) -> Grant:
        """Before anything is disclosed: is there a grant, in force, naming this decider, whose disclosure ceiling
        covers every field the terms ask to see? Raises Refused. A requester calls this on the offer."""
        t = now_ms() if now is None else now
        g = self._grant_for(terms.get("capability"), terms.get("version"))
        if g.id in self._withdrawn:
            raise Refused("withdrawn", "the permission for this purpose was withdrawn")
        if g.expires_at is not None and t >= g.expires_at:
            raise Refused("grant_expired", "the permission for this purpose has expired")
        if terms.get("requester") != g.requester:
            raise Refused("no_grant", "the grant is for a different requester than the terms name")
        if terms.get("decider") not in g.deciders:
            raise Refused("decider", "this grant does not name that decider")
        asked = set(terms.get("disclose") or ())
        if not asked <= g.disclose_max:
            raise Refused("disclosure", "the terms ask to see fields this receiver will not disclose for this "
                                        "purpose: " + ", ".join(sorted(asked - g.disclose_max)))
        return g

    def permit(self, action: str, verified: Verified, terms: Mapping[str, Any], *, approval: Optional[Approval] = None,
               now: Optional[int] = None) -> Permit:
        """May this receiver perform `action` on what `verified` judged? Permit, or Refused with the reason. Every
        outcome is written to the audit record first-class: if that cannot be written, nothing is permitted."""
        t = now_ms() if now is None else now
        approver = ""
        try:
            if not verified.allowed:
                raise Refused("refused", "a decision that is not a pass permits nothing")
            g = self.check_terms(terms, now=t)
            if verified.envelope.sender != terms.get("decider") or verified.subject != dict(terms["subject"]):
                raise Refused("terms", "the verified decision is not the one the terms describe")
            if action not in g.actions:
                raise Refused("action", f"this grant does not permit {action!r}")
            if g.approvers:
                approver = self._check_approval(g, approval, verified, action, t)
        except Refused as exc:
            self._record(t, action, terms, verified, approver, exc.code, "")
            raise
        digest = self._record(t, action, terms, verified, approver, "permitted", g.id)
        return Permit(grant=g.id, action=action, capability=g.capability, version=g.version,
                      decision_id=verified.envelope.id, subject_digest=verified.subject["digest"], approver=approver,
                      audit_digest=digest)

    def _check_approval(self, g: Grant, approval: Optional[Approval], verified: Verified, action: str, now: int) -> str:
        if approval is None:
            raise Refused("approval_required", "this action needs a person's approval and none was given")
        if approval.approver not in g.approvers:
            raise Refused("approval", "the approver is not one this grant names")
        if approval.approver in (verified.envelope.sender, g.requester):
            raise Refused("approval", "a party cannot approve its own action")
        if (approval.decision_id, approval.action, approval.subject_digest) != (
                verified.envelope.id, action, verified.subject["digest"]):
            raise Refused("approval", "the approval is for a different decision, action or document")
        if isinstance(approval.expires_at, bool) or not isinstance(approval.expires_at, int) or not (
                0 < approval.expires_at <= MAX_INT) or now >= approval.expires_at:
            raise Refused("approval", "the approval has expired")
        try:
            ok = crypto_backend.verify(public_of(approval.approver),
                                       _APPROVAL_TAG + subject_digest(approval.body()).encode("ascii"),
                                       bytes.fromhex(approval.sig))
        except ValueError:
            ok = False
        if not ok:
            raise Refused("approval", "the approval's signature does not verify as the approver")
        return approval.approver

    def _record(self, now: int, action: str, terms: Mapping[str, Any], verified: Verified, approver: str, outcome: str,
                grant: str) -> str:
        entry = {"at": now, "action": action, "outcome": outcome, "grant": grant,
                 "capability": str(terms.get("capability")), "version": terms.get("version") if isinstance(
                     terms.get("version"), int) else 0, "decider": str(terms.get("decider")),
                 "requester": str(terms.get("requester")), "decision_id": verified.envelope.id,
                 "subject_digest": verified.subject.get("digest", ""), "approver": approver,
                 "terms_digest": subject_digest({k: terms[k] for k in sorted(terms)}) if self._plain(terms) else "",
                 "retain_ms": next((g.retain_ms for g in self._grants.values() if g.id == grant), 0)}
        with self._lock:
            entry["prev"] = self._last
            digest = subject_digest(entry)
            if self._audit is not None:
                try:
                    with open(self._audit, "ab", buffering=0) as fh:
                        fh.write((json.dumps({**entry, "digest": digest}, sort_keys=True) + "\n").encode("utf-8"))
                        os.fsync(fh.fileno())
                except OSError as exc:
                    raise Refused("unavailable", f"the audit record could not be written, so nothing is permitted "
                                                 f"({type(exc).__name__})") from None
            self._last = digest
            return digest

    @staticmethod
    def _plain(terms: Mapping[str, Any]) -> bool:
        try:
            subject_digest({k: terms[k] for k in sorted(terms)})
            return True
        except TypeError:
            return False


def verify_audit(path: "os.PathLike[str] | str") -> str:
    """Check an audit file's hash chain and return the digest of its last entry (64 zeros if empty). Refused
    ('unavailable') if any entry was edited, removed from the middle, or reordered."""
    last = "0" * 64
    p = Path(path)
    if not p.exists():
        return last
    for n, line in enumerate(p.read_bytes().splitlines(), 1):
        try:
            e = json.loads(line.decode("utf-8"))
            claimed = e.pop("digest")
            if e["prev"] != last or subject_digest(e) != claimed:
                raise ValueError("chain broken")
        except (ValueError, KeyError, UnicodeDecodeError, TypeError):
            raise Refused("unavailable", f"the audit record is damaged at entry {n}") from None
        last = claimed
    return last

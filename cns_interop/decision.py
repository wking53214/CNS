"""decision: a verdict another system can check on its own, and a guard that acts on it once.

WHY THIS EXISTS

`SuperGate.decide` proves its decisions with an HMAC under a key that never leaves the process, and `DecisionGuard`
spends a decision's nonce in a set that lives in the same process. Both are right for one process and say nothing to
any other. This module is the distributed counterpart:

  `issue` signs a decision as a UAI-1 envelope, bound to the exact terms, the exact document, the exact accept it
    answers and the one identity it is addressed to, and expiring when the terms say.
  `from_super_gate` exports a CNS `Decision` that THIS process's SuperGate issued (`decision.issued`). A hand-built
    or edited Decision is refused at export, so the in-process proof is not laundered into a signature.
  `verify_decision` is everything the receiving system checks, with no access to the decider: the signature, that
    the signer is the decider the terms name, the audience, the reply binding, the terms digest, the document, the
    evidence, that the decision lives no longer than agreed, and (through its ledger) that it is new.
  `RemoteDecisionGuard` is `DecisionGuard` for a decision that came from elsewhere: closed until a verified, allowed
    decision opens it, then permits one action on the one document. Its ledger may be a `FileLedger`, so the
    process that performs the action need not be the one that received the decision.

The verdict vocabulary is CNS's own `GateOutcome`: "pass", "retry", "terminal_breach".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from cns.gate import GateOutcome, subject_digest

from .envelope import Envelope, Refused, now_ms, open_envelope, seal
from .identity import Signer
from .ledger import Ledger
from .negotiate import TERMS_KEYS, terms_digest

__all__ = ["VERDICTS", "Verified", "issue", "from_super_gate", "verify_decision", "RemoteDecisionGuard"]

VERDICTS = tuple(o.value for o in GateOutcome)
_BODY_KEYS = {"verdict", "terms_digest", "subject", "reasons", "evidence", "cns_root"}


def _evidence_list(evidence: Mapping[str, Mapping[str, Any]]) -> list:
    return [{"kind": k, "content": dict(v), "digest": subject_digest(dict(v))} for k, v in sorted(evidence.items())]


def issue(signer: Signer, accept: Envelope, terms: Mapping[str, Any], verdict: str, *, reasons: Sequence[str] = (),
          evidence: Optional[Mapping[str, Mapping[str, Any]]] = None, cns_root: str = "",
          now: Optional[int] = None) -> Envelope:
    """Sign a decision answering `accept`, under `terms`. A pass must carry exactly the evidence the terms name."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    if signer.agent != terms["decider"]:
        raise ValueError("only the decider the terms name can issue this decision")
    evidence = dict(evidence or {})
    if verdict == GateOutcome.PASS.value and sorted(evidence) != list(terms["evidence"]):
        raise ValueError("a pass must carry exactly the evidence the terms require: " + ", ".join(terms["evidence"]))
    if not set(evidence) <= set(terms["evidence"]):
        raise ValueError("evidence the terms did not ask for is not sent")
    body = {"verdict": verdict, "terms_digest": terms_digest(terms), "subject": dict(terms["subject"]),
            "reasons": list(reasons), "evidence": _evidence_list(evidence), "cns_root": cns_root}
    return seal(signer, "decision", body, to=terms["requester"], reply_to=accept,
                ttl_ms=terms["decision_ttl_ms"], now=now)


def from_super_gate(signer: Signer, accept: Envelope, terms: Mapping[str, Any], decision: Any, *,
                    evidence: Optional[Mapping[str, Mapping[str, Any]]] = None, now: Optional[int] = None) -> Envelope:
    """Export a SuperGate Decision. It must have been issued by a SuperGate in this process, and an allowed one must
    have judged the very document the terms name. A pass that `allowed` does not confirm goes out as a breach."""
    from cns_composition.super_gate import Decision

    if not isinstance(decision, Decision) or not decision.issued:
        raise ValueError("only a decision a SuperGate in this process issued can be exported")
    if decision.allowed:
        subject = decision.subject
        if subject is None or (subject.identity, subject.digest) != (terms["subject"]["identity"],
                                                                     terms["subject"]["digest"]):
            raise ValueError("the SuperGate judged a different document than the terms name")
        verdict = GateOutcome.PASS.value
    else:
        verdict = decision.outcome.value if decision.outcome is not GateOutcome.PASS else \
            GateOutcome.TERMINAL_BREACH.value
    return issue(signer, accept, terms, verdict, reasons=decision.reasons(),
                 evidence=evidence if verdict == GateOutcome.PASS.value else None, cns_root=decision.root, now=now)


@dataclass(frozen=True)
class Verified:
    """A decision that passed every check. `allowed` is True only for a pass."""

    verdict: str
    reasons: Tuple[str, ...]
    evidence: Mapping[str, Mapping[str, Any]]
    subject: Mapping[str, str]
    cns_root: str
    envelope: Envelope

    @property
    def allowed(self) -> bool:
        return self.verdict == GateOutcome.PASS.value


def verify_decision(wire: Mapping[str, Any], *, terms: Mapping[str, Any], accept_digest: str, ledger: Ledger,
                    now: Optional[int] = None) -> Verified:
    """Check a decision completely, as the requester (or anyone acting for it) holding only public information."""
    if not isinstance(terms, Mapping) or set(terms) != TERMS_KEYS:
        raise Refused("terms", "the terms to check against are not complete terms")
    env = open_envelope(wire, now=now, audience=terms["requester"], kinds={"decision"})
    if env.sender != terms["decider"]:
        raise Refused("untrusted", "the decision is signed by someone other than the decider the terms name")
    if env.in_reply_to != accept_digest:
        raise Refused("terms", "the decision answers a different accept")
    body = env.body
    if set(body) != _BODY_KEYS:
        raise Refused("malformed", "a decision body has exactly: " + ", ".join(sorted(_BODY_KEYS)))
    if body["terms_digest"] != terms_digest(terms):
        raise Refused("terms", "the decision was made under different terms")
    if body["subject"] != dict(terms["subject"]):
        raise Refused("subject", "the decision judged a different document")
    if body["verdict"] not in VERDICTS:
        raise Refused("malformed", "unknown verdict")
    if env.expires_at is None or env.expires_at - env.issued_at > terms["decision_ttl_ms"]:
        raise Refused("terms", "the decision lives longer than the terms allow")
    if not isinstance(body["reasons"], list) or not all(isinstance(r, str) for r in body["reasons"]):
        raise Refused("malformed", "reasons is a list of text")
    if not isinstance(body["cns_root"], str) or not isinstance(body["evidence"], list):
        raise Refused("malformed", "cns_root is text and evidence a list")
    evidence: Dict[str, Mapping[str, Any]] = {}
    for item in body["evidence"]:
        if not isinstance(item, Mapping) or set(item) != {"kind", "content", "digest"} or not isinstance(
                item["content"], Mapping) or not isinstance(item["kind"], str) or item["kind"] in evidence:
            raise Refused("malformed", "each evidence item is a distinct kind, its content and its digest")
        if subject_digest(dict(item["content"])) != item["digest"]:
            raise Refused("malformed", f"evidence {item['kind']} does not match its digest")
        evidence[item["kind"]] = item["content"]
    if not set(evidence) <= set(terms["evidence"]):
        raise Refused("terms", "the decision carries evidence the terms did not ask for")
    if body["verdict"] == GateOutcome.PASS.value and sorted(evidence) != list(terms["evidence"]):
        raise Refused("terms", "a pass that does not carry the evidence the terms require")
    ledger.spend(env.sender, env.id, env.expires_at)
    return Verified(verdict=body["verdict"], reasons=tuple(body["reasons"]), evidence=evidence,
                    subject=dict(body["subject"]), cns_root=body["cns_root"], envelope=env)


class RemoteDecisionGuard:
    """Closed until a verified, allowed remote decision opens it; then permits one action on that one document.

    `subject_of(artifact)` reads (identity, digest) from whatever the action is about to touch. Like `DecisionGuard`
    it answers True at most once, never raises, and a refusal does not spend the permission."""

    def __init__(self, subject_of: Callable[[object], Tuple[str, str]], *, ledger: Ledger,
                 clock: Callable[[], int] = now_ms) -> None:
        if not callable(subject_of):
            raise ValueError("subject_of must read (identity, digest) from an artifact")
        self._subject_of, self._ledger, self._clock = subject_of, ledger, clock
        self._approved: Optional[Tuple[str, str]] = None
        self._expires_at: Optional[int] = None
        self._spent = False

    def authorize(self, wire: Mapping[str, Any], *, terms: Mapping[str, Any], accept_digest: str) -> Verified:
        if self._approved is not None:
            raise ValueError("this guard was already authorized; one guard serves one decision")
        got = verify_decision(wire, terms=terms, accept_digest=accept_digest, ledger=self._ledger, now=self._clock())
        if not got.allowed:
            raise Refused("refused", "the decision is not a pass: " + "; ".join(got.reasons))
        self._approved = (got.subject["identity"], got.subject["digest"])
        self._expires_at = got.envelope.expires_at
        return got

    def __call__(self, artifact: object) -> bool:
        if self._approved is None or self._spent:
            return False
        if self._expires_at is not None and self._clock() >= self._expires_at:
            return False
        try:
            seen = tuple(self._subject_of(artifact))
        except Exception:
            return False
        if seen != self._approved:
            return False
        self._spent = True
        return True

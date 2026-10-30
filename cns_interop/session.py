"""session: the two roles of a UAI-1 exchange, each run by its own system under its own policy.

`Decider` holds capabilities and decides. `Requester` asks. Neither reaches into the other: everything passes as a
signed envelope, and each side checks what it receives against its own trust policy, its own ledger and its own
record of what it sent. Either can run in any process, on any host, in any language that implements UAI-1
(docs/interop/UAI-1.md); the reference agent in `interop/node/` is one that shares no code with this file.

What each side checks, in order, on every message it receives:

  1. the envelope (envelope.open_envelope): form, version, signature, time, audience
  2. that the message expires (session messages must, so a ledger never grows without bound)
  3. trust (trust.TrustPolicy.admit): the decider admits requesters; the requester only talks to deciders it admitted
     when it read their manifest
  4. that it answers something this side actually sent, and came from the party it was sent to
  5. the ledger: not seen before
  6. the step's own rules: terms (negotiate.py), disclosure (disclosure.py), decision (decision.py)

A failure at 1, 2 or 5 raises `Refused`: an unauthenticated or replayed message gets no reply. A failure after the
sender is authenticated and admitted is answered with a signed `refuse`, so the other side learns why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple, Union

from cns.gate import GateOutcome

from .decision import Verified, from_super_gate, issue, verify_decision
from .disclosure import Committed, open_disclosure
from .envelope import Envelope, Refused, now_ms, open_envelope, seal
from .identity import Signer
from .ledger import Ledger, MemoryLedger
from .manifest import Capability, Manifest, publish, read_manifest
from .negotiate import check_terms, propose_terms, read_request, request_body, terms_digest
from .trust import TrustPolicy

__all__ = ["Judgment", "Judge", "Decider", "Requester"]


@dataclass(frozen=True)
class Judgment:
    """What a capability concluded. `evidence` maps each evidence kind to its content."""

    verdict: str
    reasons: Tuple[str, ...] = ()
    evidence: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


#: A capability's logic: (capability, disclosed field values, subject) -> a Judgment, a CNS SuperGate Decision, or
#: (Decision, evidence). Anything it raises, or a result that cannot be issued, becomes a signed terminal_breach.
Judge = Callable[[Capability, Dict[str, Any], Dict[str, str]], Any]


def _must_expire(env: Envelope) -> None:
    if env.expires_at is None:
        raise Refused("malformed", "session messages must expire")


class Decider:
    def __init__(self, signer: Signer, *, name: str, implementation: str,
                 capabilities: Sequence[Tuple[Capability, Judge]], trust: TrustPolicy,
                 ledger: Optional[Ledger] = None, clock: Callable[[], int] = now_ms, message_ttl_ms: int = 60_000,
                 endorsements: Iterable[Envelope] = ()) -> None:
        self.signer, self.name, self.implementation = signer, name, implementation
        self._caps = {(c.name, c.version): (c, j) for c, j in capabilities}
        self._trust, self._ledger, self._clock, self._ttl = trust, ledger or MemoryLedger(), clock, message_ttl_ms
        self._endorsements = list(endorsements)
        self._presented: Dict[str, Tuple[Mapping[str, Any], ...]] = {}
        self._offers: Dict[str, Tuple[Mapping[str, Any], Capability, Judge]] = {}

    @property
    def agent(self) -> str:
        return self.signer.agent

    def manifest(self) -> Envelope:
        return publish(self.signer, self.name, self.implementation, [c for c, _ in self._caps.values()],
                       endorsements=self._endorsements, ttl_ms=24 * 3600 * 1000, now=self._clock())

    def _refuse(self, env: Envelope, code: str, reason: str) -> Envelope:
        return seal(self.signer, "refuse", {"code": code, "reasons": [reason]}, to=env.sender, reply_to=env,
                    ttl_ms=self._ttl, now=self._clock())

    def handle(self, wire: Mapping[str, Any]) -> Optional[Envelope]:
        """Process one inbound message; return the reply to send, or None (a manifest needs none)."""
        now = self._clock()
        if isinstance(wire, Mapping) and wire.get("kind") == "manifest":
            manifest, _ = read_manifest(wire, now=now)
            self._presented[manifest.agent] = manifest.endorsements
            return None
        env = open_envelope(wire, now=now, audience=self.agent, kinds={"request", "accept"})
        _must_expire(env)
        try:
            self._trust.admit(env.sender, self._presented.get(env.sender, ()), now=now)
        except Refused as exc:
            self._ledger.spend(env.sender, env.id, env.expires_at)
            return self._refuse(env, exc.code, exc.reason)
        if env.kind == "request":
            return self._on_request(env)
        return self._on_accept(env)

    def _on_request(self, env: Envelope) -> Envelope:
        if env.in_reply_to:
            raise Refused("malformed", "a request opens an exchange and answers nothing")
        self._ledger.spend(env.sender, env.id, env.expires_at)
        try:
            req = read_request(env.body)
            if (req["capability"], req["version"]) not in self._caps:
                raise Refused("capability", f"{self.name} does not offer {req['capability']} version {req['version']}")
            cap, judge = self._caps[(req["capability"], req["version"])]
            terms = propose_terms(cap, req, decider=self.agent, requester=env.sender)
        except Refused as exc:
            return self._refuse(env, exc.code, exc.reason)
        offer = seal(self.signer, "offer", {"terms": terms}, to=env.sender, reply_to=env, ttl_ms=self._ttl, now=self._clock())
        self._offers[offer.digest] = (terms, cap, judge)
        return offer

    def _on_accept(self, env: Envelope) -> Envelope:
        pending = self._offers.get(env.in_reply_to)
        if pending is None:
            raise Refused("terms", "the accept answers no offer this decider has open")
        terms, cap, judge = pending
        if env.sender != terms["requester"]:
            raise Refused("terms", "the accept comes from someone the offer was not made to")
        self._ledger.spend(env.sender, env.id, env.expires_at)
        del self._offers[env.in_reply_to]  # one accept per offer
        body = env.body
        try:
            if set(body) != {"terms_digest", "disclosure"} or body["terms_digest"] != terms_digest(terms):
                raise Refused("terms", "the accept does not agree to the terms offered")
            disclosed = open_disclosure(terms["subject"]["digest"], body["disclosure"], terms["disclose"])
        except Refused as exc:
            return self._refuse(env, exc.code, exc.reason)
        try:
            outcome = judge(cap, disclosed, dict(terms["subject"]))
            if isinstance(outcome, Judgment):
                return issue(self.signer, env, terms, outcome.verdict, reasons=outcome.reasons,
                             evidence=outcome.evidence if outcome.verdict == GateOutcome.PASS.value else None,
                             now=self._clock())
            decision, evidence = outcome if isinstance(outcome, tuple) else (outcome, None)
            return from_super_gate(self.signer, env, terms, decision, evidence=evidence, now=self._clock())
        except Exception as exc:  # a capability that fails decides nothing: fail closed, and say so, signed
            return issue(self.signer, env, terms, GateOutcome.TERMINAL_BREACH.value,
                         reasons=[f"the capability failed ({type(exc).__name__}: {exc})"], now=self._clock())


class Requester:
    def __init__(self, signer: Signer, *, trust: TrustPolicy, ledger: Optional[Ledger] = None,
                 clock: Callable[[], int] = now_ms, message_ttl_ms: int = 60_000) -> None:
        self.signer = signer
        self._trust, self._ledger, self._clock, self._ttl = trust, ledger or MemoryLedger(), clock, message_ttl_ms
        self._deciders: Dict[str, Manifest] = {}
        self._requests: Dict[str, Tuple[str, Dict[str, Any], Committed]] = {}
        self._accepts: Dict[str, Tuple[str, Dict[str, Any]]] = {}

    @property
    def agent(self) -> str:
        return self.signer.agent

    def manifest(self, endorsements: Iterable[Envelope] = ()) -> Envelope:
        """A requester's own manifest: no capabilities, just who it is and who vouches for it."""
        return publish(self.signer, "requester", "python/cns_interop", [], endorsements=endorsements,
                       ttl_ms=24 * 3600 * 1000, now=self._clock())

    def discover(self, wire: Mapping[str, Any], *, domain: Optional[str] = None) -> Manifest:
        """Read a decider's manifest and admit it under this requester's trust policy. Only admitted deciders can be
        sent requests."""
        manifest, _ = read_manifest(wire, now=self._clock(), trust=self._trust, domain=domain)
        self._deciders[manifest.agent] = manifest
        return manifest

    def request(self, decider: str, document: Committed, capability: str, version: int, *,
                offer_fields: Iterable[str], require_evidence: Iterable[str] = (), max_ttl_ms: int) -> Envelope:
        if decider not in self._deciders:
            raise Refused("untrusted", "this requester has not read and admitted that decider's manifest")
        self._deciders[decider].capability(capability, version)
        body = request_body(capability, version, identity=document.identity, digest=document.digest,
                            offer_fields=offer_fields, require_evidence=require_evidence, max_ttl_ms=max_ttl_ms)
        env = seal(self.signer, "request", body, to=decider, ttl_ms=self._ttl, now=self._clock())
        self._requests[env.digest] = (decider, body, document)
        return env

    def on_reply(self, wire: Mapping[str, Any]) -> Union[Envelope, Verified]:
        """An offer returns the accept to send; a decision returns it verified; a refuse raises Refused('declined')."""
        now = self._clock()
        env = open_envelope(wire, now=now, audience=self.agent, kinds={"offer", "refuse", "decision"})
        _must_expire(env)
        if env.kind == "decision":
            pending = self._accepts.pop(env.in_reply_to, None)
            if pending is None:
                raise Refused("terms", "the decision answers no accept this requester sent")
            accept_digest, terms = env.in_reply_to, pending[1]
            return verify_decision(wire, terms=terms, accept_digest=accept_digest, ledger=self._ledger, now=now)
        known = self._requests.get(env.in_reply_to) or self._accepts.get(env.in_reply_to)
        if known is None or known[0] != env.sender:
            raise Refused("terms", f"the {env.kind} answers nothing this requester sent to its sender")
        self._ledger.spend(env.sender, env.id, env.expires_at)
        if env.kind == "refuse":
            self._requests.pop(env.in_reply_to, None)
            self._accepts.pop(env.in_reply_to, None)
            reasons = env.body.get("reasons") if isinstance(env.body, Mapping) else None
            raise Refused("declined", "; ".join(r for r in reasons if isinstance(r, str))
                          if isinstance(reasons, list) else "the other side refused")
        decider, body, document = self._requests.pop(env.in_reply_to)
        if set(env.body) != {"terms"}:
            raise Refused("malformed", "an offer carries exactly its terms")
        terms = check_terms(env.body["terms"], body, decider=decider, requester=self.agent)
        accept = seal(self.signer, "accept", {"terms_digest": terms_digest(terms),
                                              "disclosure": document.reveal(terms["disclose"])},
                      to=decider, reply_to=env, ttl_ms=self._ttl, now=self._clock())
        self._accepts[accept.digest] = (decider, terms)
        return accept

"""trust: whether THIS receiver will deal with an identity. Always the receiver's decision, never the sender's.

A valid signature proves who sent a message. It does not make the sender someone to deal with. Each receiver holds
its own `TrustPolicy`, and there are exactly two ways in:

  Pinned       the receiver lists the identity itself.
  Endorsed     an authority the receiver lists has signed an `endorsement` envelope saying the identity belongs to a
               domain, the receiver lets that authority vouch for that domain, and the endorsement has not expired.
               This is how two organisations that have never exchanged keys for each other's agents can still work
               together: each trusts the other's authority for a named domain, and nothing more.

Endorsements must expire; one with no expiry is refused, so a leaked or obsolete endorsement ages out on its own.
`revoked` names identities and endorsement ids the receiver refuses whatever else says yes. Endorsement is one level
deep: an endorsed agent cannot endorse others. Chains, delegation and published revocation lists are not here (see
docs/interop/UAI-1.md, "What remains open").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Iterable, Mapping, Optional

from .envelope import Envelope, Refused, open_envelope, seal
from .identity import Signer, is_agent_id

__all__ = ["Admission", "TrustPolicy", "endorse", "ANY_DOMAIN"]

ANY_DOMAIN = "*"


@dataclass(frozen=True)
class Admission:
    """Why an identity was let in: `via` is "pinned" or "endorsed"."""

    agent: str
    via: str
    authority: str = ""
    domain: str = ""
    endorsement: str = ""


def endorse(authority: Signer, agent: str, domain: str, *, ttl_ms: int, now: Optional[int] = None) -> Envelope:
    """An authority's signed statement that `agent` belongs to `domain`, valid for `ttl_ms`."""
    if not is_agent_id(agent):
        raise ValueError("can only endorse an agent identity")
    if not isinstance(domain, str) or not domain or domain == ANY_DOMAIN:
        raise ValueError("an endorsement names one domain")
    return seal(authority, "endorsement", {"subject": agent, "domain": domain}, to=agent, ttl_ms=ttl_ms, now=now)


@dataclass(frozen=True)
class TrustPolicy:
    """Who this receiver deals with. `authorities` maps an authority's identity to the domains it may vouch for
    ("*" for any)."""

    pinned: FrozenSet[str] = frozenset()
    authorities: Mapping[str, FrozenSet[str]] = field(default_factory=dict)
    revoked: FrozenSet[str] = frozenset()

    def __post_init__(self) -> None:
        for a in list(self.pinned) + list(self.authorities):
            if not is_agent_id(a):
                raise ValueError(f"not an agent identity: {a!r}")
        object.__setattr__(self, "pinned", frozenset(self.pinned))
        object.__setattr__(self, "revoked", frozenset(self.revoked))
        object.__setattr__(self, "authorities", {k: frozenset(v) for k, v in self.authorities.items()})

    def admit(self, agent: str, endorsements: Iterable[Any] = (), *, now: Optional[int] = None,
              domain: Optional[str] = None) -> Admission:
        """Admit `agent` or raise Refused('untrusted'). `endorsements` are wire mappings (or Envelopes) the agent
        presented; each is checked completely. `domain`, if given, is the only domain an endorsement may name. A pinned
        identity is admitted whatever its endorsements say: pinning is the receiver's own word."""
        if agent in self.revoked:
            raise Refused("untrusted", "this receiver has revoked that identity")
        if agent in self.pinned:
            return Admission(agent=agent, via="pinned")
        reasons = []
        for presented in endorsements:
            wire = presented.to_wire() if isinstance(presented, Envelope) else presented
            try:
                env = open_envelope(wire, now=now, kinds={"endorsement"})
            except Refused as exc:
                reasons.append(f"an endorsement was refused ({exc.code}: {exc.reason})")
                continue
            why = self._endorsement_problem(env, agent, domain)
            if why:
                reasons.append(why)
                continue
            return Admission(agent=agent, via="endorsed", authority=env.sender, domain=env.body["domain"],
                             endorsement=env.id)
        raise Refused("untrusted", "the identity is not pinned and no endorsement admits it"
                      + (": " + "; ".join(reasons) if reasons else ""))

    def _endorsement_problem(self, env: Envelope, agent: str, domain: Optional[str]) -> str:
        if env.expires_at is None:
            return "an endorsement with no expiry is never accepted"
        if env.sender in self.revoked or env.id in self.revoked:
            return "an endorsement from a revoked authority, or itself revoked"
        if env.sender not in self.authorities:
            return "an endorsement from an authority this receiver does not recognise"
        body = env.body
        if set(body) != {"subject", "domain"} or not isinstance(body.get("domain"), str):
            return "an endorsement whose body is not exactly subject and domain"
        if body["subject"] != agent:
            return "an endorsement for a different identity"
        allowed = self.authorities[env.sender]
        if ANY_DOMAIN not in allowed and body["domain"] not in allowed:
            return f"an endorsement for domain {body['domain']!r}, which that authority may not vouch for here"
        if domain is not None and body["domain"] != domain:
            return f"an endorsement for domain {body['domain']!r}, not {domain!r}"
        return ""

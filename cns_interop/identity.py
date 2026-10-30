"""identity: who sent something, as a name anyone can check without asking a registry.

An agent's identity is its public key, written `uai:ed25519:<64 hex>`. It is self-certifying: a message signed by
the matching private key proves it came from that identity, and nothing has to be looked up to say so. That keeps
each system its own authority over its own name. Whether a receiver chooses to TRUST an identity is a separate
question, answered by its own `trust.TrustPolicy`, never by the sender.

A `Signer` holds a private key and never shows it. A host that keeps keys in an HSM or an OS keystore builds one
with `Signer.external(agent, sign)`: the protocol only needs a function that signs.
"""

from __future__ import annotations

import re
import secrets
from typing import Callable, Optional

from . import ed25519

__all__ = ["AGENT_PREFIX", "Signer", "agent_id", "public_of", "is_agent_id"]

AGENT_PREFIX = "uai:ed25519:"
_AGENT = re.compile(r"\Auai:ed25519:[0-9a-f]{64}\Z")


def agent_id(public: bytes) -> str:
    """The identity for a 32-byte Ed25519 public key."""
    if not isinstance(public, (bytes, bytearray)) or len(public) != ed25519.PUBLIC_BYTES:
        raise ValueError("an agent's public key is 32 bytes")
    return AGENT_PREFIX + bytes(public).hex()


def is_agent_id(value: object) -> bool:
    """Whether `value` is written exactly as an identity is: the prefix and 64 lowercase hex digits, nothing else."""
    return isinstance(value, str) and _AGENT.match(value) is not None


def public_of(agent: str) -> bytes:
    """The public key an identity names. ValueError for anything not written exactly as an identity."""
    if not is_agent_id(agent):
        raise ValueError("not an agent identity: expected uai:ed25519: and 64 lowercase hex digits")
    return bytes.fromhex(agent[len(AGENT_PREFIX):])


class Signer:
    """One agent's private key, used only to sign. `agent` is its public identity."""

    __slots__ = ("_seed", "_sign", "agent")

    def __init__(self, seed: bytes) -> None:
        if not isinstance(seed, (bytes, bytearray)) or len(seed) != ed25519.SEED_BYTES:
            raise ValueError("a signer's key is a 32-byte seed")
        self._seed: Optional[bytes] = bytes(seed)
        self._sign: Optional[Callable[[bytes], bytes]] = None
        self.agent = agent_id(ed25519.public_key(self._seed))

    @classmethod
    def generate(cls) -> "Signer":
        """A new signer with a key drawn from the operating system's random source."""
        return cls(secrets.token_bytes(ed25519.SEED_BYTES))

    @classmethod
    def external(cls, agent: str, sign: Callable[[bytes], bytes]) -> "Signer":
        """A signer whose key lives somewhere else (an HSM, a keystore). `sign(message)` returns 64 bytes.

        Every signature it returns is checked against `agent` before it leaves, so a misconfigured keystore is an
        error here and not a stream of messages every receiver refuses."""
        public_of(agent)
        if not callable(sign):
            raise ValueError("sign must be a function that signs bytes")
        self = cls.__new__(cls)
        self._seed = None
        self._sign = sign
        self.agent = agent
        return self

    def sign(self, message: bytes) -> bytes:
        if self._seed is not None:
            return ed25519.sign(self._seed, message)
        assert self._sign is not None
        signature = bytes(self._sign(message))
        if not ed25519.verify(public_of(self.agent), message, signature):
            raise ValueError("the external signer returned a signature that does not verify as " + self.agent)
        return signature

    def __repr__(self) -> str:
        return f"Signer({self.agent})"

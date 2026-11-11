"""A reference deployer for the receipt signing hook: Ed25519 keys, a trust list and a revocation set.

This is fixture code for the runner, outside every wheel. It is the DEPLOYER's side of the hook, not Delta's and not CNS's:
Delta (`delta.signing`) builds the bytes and calls a `sign` it is handed; CNS (`strict_problems(..., verify_receipt_signature=)`)
calls a verifier it is handed. Neither holds a key, a trust list or a revocation set. This module is one way to build the two
callables, using the `cryptography` package that only tests and `chains/` may import.

THE ENVELOPE is this deployer's choice and is not part of Delta or CNS: the signature bytes handed to Delta and CNS are

    key_id (UTF-8) + b":" + Ed25519 signature (64 bytes)

so a verifier knows which public key to try without trying them all. A key id is a label, not a secret and not a MAC; it must
not contain ":" (the first ":" ends the id). The Ed25519 signature is over exactly the bytes `sign` was called with.

TRUST LIST: a mapping of key id to an Ed25519 public key. `make_verifier` takes a snapshot of it, so editing the mapping later
changes nothing; to change what is trusted, make a new verifier.

ROTATION: add the new key id to the trust list and start signing with it; keep the old id in the trust list, and what it
signed keeps verifying, until it is retired by building a verifier without it. A receipt signed by a retired key then stops
verifying, which is the point of retiring it.

REVOCATION: an id in the revocation set never verifies, whether or not it is also in the trust list, and whatever the
signature. Revoking is final for that id; a replacement is a new id.

What a verifying signature shows: a holder of a trusted, unrevoked private key signed these bytes. It does not show that the
holder is honest, and a holder can sign a receipt for a ledger that does not exist.
"""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SEPARATOR = b":"


def _key_id_bytes(key_id: Any) -> bytes:
    if type(key_id) is not str or not key_id or ":" in key_id:
        raise ValueError(f"a key id is a non-empty str without ':'; got {key_id!r}")
    return key_id.encode("utf-8")  # a lone surrogate is a UnicodeEncodeError, which is a ValueError


def make_signer(private_key: Ed25519PrivateKey, key_id: str) -> Callable[[bytes], bytes]:
    """A `sign` callable(bytes) -> bytes for Delta's `sign_receipt` and `CheckpointStore.write`: `key_id:` + the signature."""
    prefix = _key_id_bytes(key_id) + SEPARATOR

    def sign(data: bytes) -> bytes:
        return prefix + private_key.sign(data)

    return sign


def make_verifier(trust: Mapping[str, Ed25519PublicKey], revoked: Collection[str] = ()) -> Callable[[bytes, bytes], bool]:
    """A `verify` callable(signing_input, signature) -> bool for CNS and Delta. True only for a signature in the envelope whose
    key id is trusted, not revoked, and whose Ed25519 signature is over exactly `signing_input`. It answers False, never
    raises, for anything else (an unknown id, a revoked id, a bad signature, input that is not bytes, a malformed envelope)."""
    keys: Dict[str, Ed25519PublicKey] = dict(trust)
    gone = frozenset(revoked)

    def verify(data: bytes, signature: bytes) -> bool:
        try:
            if type(data) is not bytes or type(signature) is not bytes:
                return False
            raw_id, separator, body = signature.partition(SEPARATOR)
            if not separator or not body:
                return False
            key_id = raw_id.decode("utf-8")
            key = keys.get(key_id)
            if key is None or key_id in gone:
                return False
            key.verify(body, data)
            return True
        except Exception:  # noqa: BLE001 - a verifier fails closed: whatever went wrong, the signature did not verify
            return False

    return verify

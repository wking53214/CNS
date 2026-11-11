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

REVOCATION: an id in the revocation set never verifies, whatever the signature. Revoking is final for that id; a replacement
is a new id. Revocation is by id, so a list that could be read two ways is refused (ValueError) by `make_verifier` and
`trust_from_json` instead of guessed at: one public key under two ids (revoking one would leave the other), a revoked id that
names no trusted id (a typo, a case difference or a retired key revokes nothing), an id twice in the JSON (the last would win
silently), and an id outside ASCII (NFC and NFD spell one id two ways).

What a verifying signature shows: a holder of a trusted, unrevoked private key signed these bytes. It does not show that the
holder is honest, and a holder can sign a receipt for a ledger that does not exist.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Collection, Dict, List, Mapping, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SEPARATOR = b":"


def _key_id_bytes(key_id: Any) -> bytes:
    if type(key_id) is not str or not key_id or ":" in key_id or not key_id.isascii():
        raise ValueError(f"a key id is a non-empty ASCII str without ':'; got {key_id!r}")
    return key_id.encode("utf-8")  # a lone surrogate is a UnicodeEncodeError, which is a ValueError


def make_signer(private_key: Ed25519PrivateKey, key_id: str) -> Callable[[bytes], bytes]:
    """A `sign` callable(bytes) -> bytes for Delta's `sign_receipt` and `CheckpointStore.write`: `key_id:` + the signature."""
    prefix = _key_id_bytes(key_id) + SEPARATOR

    def sign(data: bytes) -> bytes:
        return prefix + private_key.sign(data)

    return sign


def check_trust(trust: Mapping[str, Ed25519PublicKey], revoked: Collection[str]) -> Tuple[Dict[str, Ed25519PublicKey], frozenset]:
    """A snapshot of the trust list and the revocation set, or ValueError if they can be read two ways (see REVOCATION)."""
    keys: Dict[str, Ed25519PublicKey] = dict(trust)
    gone = frozenset(revoked)
    for key_id in keys:
        _key_id_bytes(key_id)
    owners: Dict[str, str] = {}
    for key_id, public_key in keys.items():
        raw = public_key_hex(public_key)
        if raw in owners:
            raise ValueError(f"one public key is listed under two ids, {owners[raw]!r} and {key_id!r}: revoking one id "
                             "would leave the other")
        owners[raw] = key_id
    for key_id in gone:
        if type(key_id) is not str:
            raise ValueError(f"a revoked key id is a str; got {key_id!r}")
        if key_id not in keys:
            raise ValueError(f"the revoked id {key_id!r} matches no trusted id (ids are compared exactly, in ASCII): it "
                             "would revoke nothing")
    return keys, gone


def make_verifier(trust: Mapping[str, Ed25519PublicKey], revoked: Collection[str] = ()) -> Callable[[bytes, bytes], bool]:
    """A `verify` callable(signing_input, signature) -> bool for CNS and Delta. True only for a signature in the envelope whose
    key id is trusted, not revoked, and whose Ed25519 signature is over exactly `signing_input`. It answers False, never
    raises, for anything else (an unknown id, a revoked id, a bad signature, input that is not bytes, a malformed envelope)."""
    keys, gone = check_trust(trust, revoked)

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


def public_key_hex(public_key: Ed25519PublicKey) -> str:
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def trust_to_json(trust: Mapping[str, Ed25519PublicKey], revoked: Collection[str] = ()) -> str:
    """The trust list as the JSON a consumer reads: public keys only (64 hex characters each), never a private key."""
    return json.dumps({"keys": {k: public_key_hex(v) for k, v in sorted(trust.items())}, "revoked": sorted(revoked)}, indent=2) + "\n"


def _no_duplicate_ids(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    seen: Dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"the trust file holds {key!r} twice in one object: the last would win silently")
        seen[key] = value
    return seen


def trust_from_json(text: str) -> Tuple[Dict[str, Ed25519PublicKey], frozenset]:
    """`(trust, revoked)` from `trust_to_json`'s format; ValueError for anything that is not exactly that shape."""
    data = json.loads(text, object_pairs_hook=_no_duplicate_ids)
    if type(data) is not dict or set(data) != {"keys", "revoked"} or type(data["keys"]) is not dict \
            or type(data["revoked"]) is not list or not all(type(r) is str for r in data["revoked"]):
        raise ValueError('a trust file is {"keys": {key_id: 64 hex characters}, "revoked": [key_id, ...]}')
    trust: Dict[str, Ed25519PublicKey] = {}
    for key_id, hexkey in data["keys"].items():
        _key_id_bytes(key_id)
        if type(hexkey) is not str or len(hexkey) != 64:
            raise ValueError(f"the public key for {key_id!r} is not 64 hex characters")
        trust[key_id] = Ed25519PublicKey.from_public_bytes(bytes.fromhex(hexkey))
    return check_trust(trust, data["revoked"])

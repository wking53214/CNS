"""Verify a package made by `make_package.py`, from files alone: it trusts no object the producer ran.

    python chains/verify_package.py PACKAGE_DIR --checkpoint CHECKPOINT_FILE --public-keys TRUST_JSON [--require-signed | --allow-unsigned]

Exit 0: verified, with a one-line summary carrying the root. Exit 1: refused, every named problem on stderr. Exit 2: usage
error or an input that cannot be read (a missing file, text that is not JSON, a trust file of the wrong shape).

The receipt must be signed: a package with no signature.json is refused (exit 1, naming why) unless `--allow-unsigned` is
passed, and then the summary says `receipt_signature=absent (allowed)`. A signature that is present must always verify.

What it does, in order, and stops at the first step that cannot go on:
  1. reads the checkpoint with Delta's `CheckpointStore` from CHECKPOINT_FILE, which must live outside the package. Its
     signature is verified with the trust list when `--require-signed` is given, and also whenever the file carries one.
  2. `delta.verify_export(export, checkpoint)`: rebuilds the ledger from export.json, recomputing every hash, and requires it
     to contain the history the checkpoint names.
  3. asks Delta for the receipt it issues for that ledger and checkpoint and requires the package's receipt.json to equal it.
  4. `strict_problems(...)` from `cns_composition.spine_trace` on the four contents in contents.json, with that receipt, the
     checkpoint as `held_checkpoint`, Zeta's own KeySet fingerprint rule (built from the real Zeta classes) as
     `keyset_fingerprint_of`, and the receipt signature (signature.json) verified with the trust list. A signature that is
     present must verify; `--require-signed` makes its absence a problem too.
Then it asks CNS for the root, from the same arguments.

A pass shows that the contents of the four stages agree with each other and with the receipt, that the ledger the export holds
is intact and contains the history of the checkpoint, and that a holder of a trusted, unrevoked key signed that receipt. It
does not show that the Decision was right or that the key holder is honest, and it is only as independent as the checkpoint
file and the trust list the caller supplies. This file holds no key.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, NoReturn, Optional

import receipt_keys
from cns.gate import subject_digest
from cns_composition.spine_trace import strict_problems, strict_root
from delta import cns_connector as delta_cns
from delta import verify_export
from delta.store import CheckpointStore, StoreError
from zeta import Key, KeySet


def zeta_keyset_fingerprint(alpha_content: Any) -> str:
    """Zeta's own fingerprint of the KeySet that alpha's content describes, rebuilt by Zeta's constructors from alpha's keys
    (name, present, confidence, reason) and min_confidence. Zeta owns the rule; CNS only compares what this returns."""
    keys = [Key(name=k["name"], present=k["present"], confidence=k["confidence"], reason=k["reason"]) for k in alpha_content["keys"]]
    return KeySet(keys, min_confidence=alpha_content["min_confidence"]).fingerprint()


def unreadable(why: str) -> NoReturn:
    print(f"unreadable: {why}", file=sys.stderr)
    raise SystemExit(2)


def refuse(problems: List[str]) -> NoReturn:
    for problem in problems:
        print(f"refused: {problem}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:  # ValueError covers json.JSONDecodeError and UnicodeDecodeError
        unreadable(f"{path}: {type(exc).__name__}: {exc}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="verify_package", description="Verify a package made by make_package.py.")
    ap.add_argument("package", help="the package directory (export.json, receipt.json, contents.json, signature.json)")
    ap.add_argument("--checkpoint", required=True, help="the checkpoint file, kept outside the package")
    ap.add_argument("--public-keys", required=True, help="the trust list: JSON of public keys and revoked key ids")
    ap.add_argument("--require-signed", action="store_true", help="the checkpoint and the receipt must both carry a verifying signature")
    ap.add_argument("--allow-unsigned", action="store_true",
                    help="accept a package that has no receipt signature (a signature that is present must still verify)")
    a = ap.parse_args(argv)  # a usage error exits 2
    if a.allow_unsigned and a.require_signed:
        ap.error("--allow-unsigned and --require-signed contradict each other")

    export = read_json(os.path.join(a.package, "export.json"))
    receipt = read_json(os.path.join(a.package, "receipt.json"))
    contents = read_json(os.path.join(a.package, "contents.json"))
    signature_path = os.path.join(a.package, "signature.json")
    signature_file: Optional[Any] = read_json(signature_path) if os.path.exists(signature_path) else None
    if not os.path.isfile(a.checkpoint):
        unreadable(f"{a.checkpoint}: no such checkpoint file")
    try:
        with open(a.public_keys, encoding="utf-8") as fh:
            trust, revoked = receipt_keys.trust_from_json(fh.read())
    except (OSError, ValueError) as exc:
        unreadable(f"{a.public_keys}: {type(exc).__name__}: {exc}")
    verify = receipt_keys.make_verifier(trust, revoked)

    # 1. the checkpoint, from storage outside the package
    store = CheckpointStore(a.checkpoint)
    try:
        checkpoint = store.read()
        if a.require_signed or "signature" in read_json(a.checkpoint):
            checkpoint = store.read(verify=verify)
    except StoreError as exc:
        refuse([f"the checkpoint is refused: {exc}"])

    # 2. the export, rebuilt and held to the checkpoint
    try:
        ledger = verify_export(export, checkpoint, require_context=True)
    except (ValueError, TypeError) as exc:
        refuse([f"the ledger export is refused: {exc}"])

    # 3. the receipt Delta itself issues for this ledger and checkpoint
    problems: List[str] = []
    try:
        parts: Dict[str, Any] = {name: contents[name] for name in ("alpha", "zeta", "beta", "delta")}
        beta = parts["beta"]
        index = receipt["index"] if type(receipt) is dict else None
        expected = delta_cns.verification_receipt(
            ledger, checkpoint, context=beta["context"], decision_digest=subject_digest(beta), index=index)
        if receipt != expected:
            problems.append("the receipt in the package is not the one Delta issues for this export and checkpoint")
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"no receipt can be rebuilt from this export, checkpoint and contents: {type(exc).__name__}: {exc}")
        parts = {name: contents.get(name) if type(contents) is dict else None for name in ("alpha", "zeta", "beta", "delta")}

    # 4. CNS's strict check, with the receipt signature and the checkpoint held outside the package
    signature: Optional[bytes] = None
    if signature_file is not None:
        try:
            signature = bytes.fromhex(signature_file["receipt_signature"])
        except (KeyError, TypeError, ValueError):
            problems.append('signature.json is not {"receipt_signature": <hex>}')
    allowed_absent = signature_file is None and a.allow_unsigned
    if signature_file is None and not a.allow_unsigned:
        problems.append("the package has no signature.json, so its receipt is unsigned; pass --allow-unsigned to accept that")
    kw: Dict[str, Any] = dict(
        chain=receipt, held_checkpoint=(checkpoint.length, checkpoint.head), keyset_fingerprint_of=zeta_keyset_fingerprint,
        require_keyset_verifier=True, receipt_signature=signature, verify_receipt_signature=None if allowed_absent else verify,
        require_signed_receipt=a.require_signed)
    problems += strict_problems(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], **kw)
    if problems:
        refuse(problems)
    root = strict_root(parts["alpha"], parts["zeta"], parts["beta"], parts["delta"], **kw)
    print(f"verified: root={root} entries={len(ledger)} checkpoint={checkpoint.length} "
          f"receipt_signature={'verified' if signature is not None else 'absent (allowed)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

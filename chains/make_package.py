"""The producer of a verifiable package: runs the real pipeline and writes what a consumer needs to check it elsewhere.

    python chains/make_package.py PACKAGE_DIR --checkpoint-dir DIR --trust-out FILE [--entries N] [--run-offset K]
                                  [--receipt-key-id ID] [--no-receipt-signature] [--no-checkpoint-signature]
                                  [--older-checkpoint-length K] [--package-entry K]

PACKAGE_DIR gets export.json (Delta's ledger export), receipt.json (Delta's verification receipt for the last entry),
signature.json (the deployer's signature over the receipt, made through Delta's `sign_receipt`), and contents.json (the four
stages' contents). The CHECKPOINT goes to a separately named directory (`--checkpoint-dir`, file checkpoint.json) because a
checkpoint beside the ledger it protects is not independent: the consumer gets it from somewhere the producer cannot rewrite.
`--trust-out` receives the PUBLIC keys (the trust list a consumer passes to `verify_package.py --public-keys`); the private
keys are generated here, per run, and are not written anywhere. Fixture code: the keys and the envelope are
`receipt_keys.py`'s, the deployer's choice, not Delta's or CNS's.

The checkpoint is signed by key k1. The receipt is signed by k1 too, unless `--receipt-key-id ID` names another id, in which
case a second key is generated for it (and both public keys are in the trust list), so a consumer can be shown a trust list
that lacks, revokes or swaps the receipt's key without touching the checkpoint's. `--run-offset` shifts the run numbers so two
packages describe different runs. The `--no-*-signature` flags write an unsigned receipt or checkpoint.
`--older-checkpoint-length K` also writes older.json in the checkpoint directory: a genuinely signed checkpoint of the first K
entries, for showing a consumer what a stale one does. `--package-entry K` packages the receipt, signature and contents of
entry K (0-based) instead of the last one, against the full ledger and its checkpoint: a validly signed receipt for an older
entry, for showing a consumer what choosing the entry looks like.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

import receipt_keys
import spine_run
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cns.gate import subject_digest
from delta import DecisionLedger
from delta import cns_connector as delta_cns
from delta import signing as delta_signing
from delta.ledger import LedgerCheckpoint
from delta.store import CheckpointStore


def _write(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, sort_keys=True, indent=1) + "\n")


def _receipt_for(ledger: DecisionLedger, checkpoint: LedgerCheckpoint, chosen: Dict[str, Any], index: int) -> Any:
    try:
        return delta_cns.verification_receipt(ledger, checkpoint, context=chosen["beta"]["context"],
                                              decision_digest=subject_digest(chosen["beta"]), index=index), ""
    except Exception as exc:  # noqa: BLE001 - delta refused: no receipt
        return None, f"{type(exc).__name__}: {exc}"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="make_package")
    ap.add_argument("package")
    ap.add_argument("--checkpoint-dir", required=True)
    ap.add_argument("--trust-out", required=True)
    ap.add_argument("--entries", type=int, default=3)
    ap.add_argument("--run-offset", type=int, default=0)
    ap.add_argument("--receipt-key-id", default="k1")
    ap.add_argument("--no-receipt-signature", action="store_true")
    ap.add_argument("--no-checkpoint-signature", action="store_true")
    ap.add_argument("--older-checkpoint-length", type=int, default=0)
    ap.add_argument("--package-entry", type=int, default=-1, help="package this entry (0-based) instead of the last")
    a = ap.parse_args(argv)
    if os.path.abspath(a.checkpoint_dir) == os.path.abspath(a.package):
        ap.error("the checkpoint must not be written into the package: it would not be independent")
    keys: Dict[str, Ed25519PrivateKey] = {"k1": Ed25519PrivateKey.generate()}
    if a.receipt_key_id != "k1":
        keys[a.receipt_key_id] = Ed25519PrivateKey.generate()
    ledger = DecisionLedger(require_context=True)
    parts: Dict[str, Any] = {}
    runs: List[Dict[str, Any]] = []
    for i in range(a.entries):
        parts = spine_run.record(ledger, i + a.run_offset)
        runs.append(parts)
    chosen = parts
    if a.package_entry >= 0:
        if a.package_entry >= len(runs):
            ap.error(f"--package-entry {a.package_entry} is not one of the {len(runs)} entries")
        chosen = runs[a.package_entry]
    receipt, why = (spine_run.chain_receipt(parts) if a.package_entry < 0
                    else _receipt_for(ledger, parts["checkpoint"], chosen, a.package_entry))
    if receipt is None:
        print(f"the producer's own ledger issued no receipt: {why}", file=sys.stderr)
        return 1
    _write(os.path.join(a.package, "export.json"), ledger.export())
    _write(os.path.join(a.package, "receipt.json"), receipt)
    _write(os.path.join(a.package, "contents.json"),
           {"alpha": chosen["alpha"], "zeta": chosen["zeta"], "beta": chosen["beta"], "delta": chosen["delta"]})
    if not a.no_receipt_signature:
        sign = receipt_keys.make_signer(keys[a.receipt_key_id], a.receipt_key_id)
        _write(os.path.join(a.package, "signature.json"), {"receipt_signature": delta_signing.sign_receipt(receipt, sign).hex()})
    CheckpointStore(os.path.join(a.checkpoint_dir, "checkpoint.json")).write(
        parts["checkpoint"], sign=None if a.no_checkpoint_signature else receipt_keys.make_signer(keys["k1"], "k1"))
    if a.older_checkpoint_length:
        k = a.older_checkpoint_length
        CheckpointStore(os.path.join(a.checkpoint_dir, "older.json")).write(
            LedgerCheckpoint(k, ledger.entries[k - 1].immutable_hash), sign=receipt_keys.make_signer(keys["k1"], "k1"))
    with open(a.trust_out, "w", encoding="utf-8") as fh:
        fh.write(receipt_keys.trust_to_json({k: v.public_key() for k, v in keys.items()}))
    print(f"package written: {a.entries} entries, checkpoint of {parts['checkpoint'].length} in {a.checkpoint_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Separate processes for the durable-store scenarios of `spine_run.py`. Fixture code, run as a script, never imported.

    producer  records Decisions through DecisionLedger(sink=FileLedgerStore(dir).sink), prints one `ACK <audit_id>` line per
              append that returned (an acknowledged entry), and at the chosen points writes a signed checkpoint into its OWN
              directory and a hand-off (the three upstream stage contents, a signature over Delta's receipt, the trust list).
              It holds the signing key; nothing else does.
    consumer  a fresh process that knows only the three paths and the trust list: it loads the store, reconciles it with the
              signed checkpoint, rebuilds Delta's receipt itself from the loaded ledger, and asks CNS for the strict root with
              the checkpoint and the signature. Exit 0 and a root on stdout, or exit 1 and `REFUSED <reason>` on stderr.
    load      prints the audit ids a store holds after a load (the SIGKILL scenario).

The producer's key is generated per run and never leaves the producer; only the public half goes into the trust list.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, List, NoReturn

import receipt_keys
import spine_run
from cns.gate import subject_digest
from cns_composition.spine_trace import strict_root
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from delta import DecisionLedger
from delta import cns_connector as delta_cns
from delta import signing as delta_signing
from delta.store import CheckpointStore, FileLedgerStore, StoreCorruptError, StoreError, reconcile

KEY_ID = "k1"


def refuse(reason: str) -> NoReturn:
    print(f"REFUSED {reason}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def publish(parts: Any, checkpoint_path: str, handoff: str, sign: Any) -> None:
    """Write the signed checkpoint where the checkpoint lives and the hand-off beside the consumer's inputs."""
    CheckpointStore(checkpoint_path).write(parts["checkpoint"], sign=sign)
    receipt, why = spine_run.chain_receipt(parts)
    if receipt is None:
        raise SystemExit(f"the producer's own ledger issued no receipt: {why}")
    _write(os.path.join(handoff, "contents.json"),
           json.dumps({"alpha": parts["alpha"], "zeta": parts["zeta"], "beta": parts["beta"]}, sort_keys=True))
    _write(os.path.join(handoff, "receipt_signature.hex"), delta_signing.sign_receipt(receipt, sign).hex() + "\n")


def producer(a: argparse.Namespace) -> int:
    key = Ed25519PrivateKey.generate()
    sign = receipt_keys.make_signer(key, KEY_ID)
    _write(os.path.join(a.handoff, "trust.json"), receipt_keys.trust_to_json({KEY_ID: key.public_key()}))
    ledger = DecisionLedger(require_context=True, sink=FileLedgerStore(a.ledger).sink)
    i = 0
    while a.forever or i < a.entries:
        parts = spine_run.record(ledger, i)
        print("ACK", ledger.entries[-1].audit_id, flush=True)
        i += 1
        if i == a.snapshot_at:
            publish(parts, a.snapshot_checkpoint, a.snapshot_handoff, sign)
        if i == (a.checkpoint_at or a.entries):
            publish(parts, a.checkpoint, a.handoff, sign)
    print("DONE", flush=True)
    return 0


def consumer(a: argparse.Namespace) -> int:
    trust, revoked = receipt_keys.trust_from_json(open(os.path.join(a.handoff, "trust.json"), encoding="utf-8").read())
    verify = receipt_keys.make_verifier(trust, revoked)
    store, checkpoints = FileLedgerStore(a.ledger), CheckpointStore(a.checkpoint)
    try:
        result = reconcile(store, checkpoints, require_context=True, verify=verify)
    except StoreCorruptError as exc:
        refuse(f"StoreCorruptError: {exc}")
    except StoreError as exc:
        refuse(f"checkpoint StoreError: {exc}")
    status, tail = result["status"], result["recovered_tail"]
    if status == "UNWITNESSED_TAIL" and a.accept_unwitnessed:
        print(json.dumps({"status": status, "unwitnessed": result["unwitnessed"], "recovered_tail": tail}), flush=True)
        return 0
    if status != "OK":
        refuse(f"reconcile {status}: {json.dumps(result, sort_keys=True)}")
    ledger, _ = store.load(require_context=True)
    checkpoint = checkpoints.read(verify=verify)
    with open(os.path.join(a.handoff, "contents.json"), encoding="utf-8") as fh:
        contents = json.load(fh)
    with open(os.path.join(a.handoff, "receipt_signature.hex"), encoding="utf-8") as fh:
        signature = bytes.fromhex(fh.read().strip())
    context, beta = contents["beta"]["context"], contents["beta"]
    entry = ledger.entries[checkpoint.length - 1]
    delta = delta_cns.entry_content(entry, context=context, decision_digest=subject_digest(beta))
    try:
        receipt = delta_cns.verification_receipt(ledger, checkpoint, context=context, decision_digest=subject_digest(beta))
        root = strict_root(contents["alpha"], contents["zeta"], beta, delta, chain=receipt,
                           held_checkpoint=(checkpoint.length, checkpoint.head),
                           keyset_fingerprint_of=spine_run.zeta_keyset_fingerprint, receipt_signature=signature,
                           verify_receipt_signature=verify, require_signed_receipt=True)
    except ValueError as exc:
        refuse(f"strict check: {exc}")
    print(json.dumps({"root": root, "status": status, "recovered_tail": tail, "entries": len(ledger),
                      "checkpoint_length": checkpoint.length}), flush=True)
    return 0


def load(a: argparse.Namespace) -> int:
    ledger, report = FileLedgerStore(a.ledger).load(require_context=True)
    print(json.dumps({"ids": [e.audit_id for e in ledger.entries], "recovered_tail": report["recovered_tail"]}), flush=True)
    return 0


def main(argv: List[str]) -> int:
    top = argparse.ArgumentParser(prog="store_worker")
    sub = top.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("producer")
    p.add_argument("--ledger", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--handoff", required=True)
    p.add_argument("--entries", type=int, default=0)
    p.add_argument("--forever", action="store_true")
    p.add_argument("--checkpoint-at", type=int, default=0)
    p.add_argument("--snapshot-at", type=int, default=0)
    p.add_argument("--snapshot-checkpoint")
    p.add_argument("--snapshot-handoff")
    c = sub.add_parser("consumer")
    c.add_argument("--ledger", required=True)
    c.add_argument("--checkpoint", required=True)
    c.add_argument("--handoff", required=True)
    c.add_argument("--accept-unwitnessed", action="store_true")
    ld = sub.add_parser("load")
    ld.add_argument("--ledger", required=True)
    a = top.parse_args(argv)
    return {"producer": producer, "consumer": consumer, "load": load}[a.mode](a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""act.py: the process that performs an action, deciding on its own whether the RECEIVER permits it.

A signed decision is not permission. This program acts only under the receiver's own policy, which comes from its
command line and files, never from the job:

    python interop/act.py --acting-for <identity> --capability <name> --capability-version <n>
                          --trust <decider identity>[,...] --ledger <decision ledger file>
                          --grants <grants.json> --grant-store <state.db> --action <name> --audit <audit.jsonl>
                          [--permit-ledger <file>] [--lease-ms <ms>]

The job comes on stdin, one JSON object, and can only narrow what is accepted, never widen it:

    {"decision": <decision envelope>, "terms": <the agreed terms>, "accept_digest": "<hex>",
     "artifact": ["<identity>", "<digest>"], "approval": <a person's signed approval, only if the grant needs one>}

What it checks, in this order: the job is strict JSON (a duplicate key, a float, NaN, or more than 1 MiB is refused
before anything is verified); the decision is genuine, for this requester and capability, from a decider this process
trusts, and new (shared ledger); the receiver's GRANT for that purpose exists, is in force, was not withdrawn, names that
decider and action, and covers the disclosure; a person approved, if the grant says one must; the terms are the terms the
decision was made under; the permit for this decision and action has not been used. Every outcome is written to the audit
record. It prints {"permitted": true|false, "permit": {...}} or {"refused": {"code": ..., "reason": ...}}.

`--decision-only` keeps the behavior of revision 2, in which a verified decision opens the action by itself. It is NOT
receiver-authorized, it says so on stderr, and it is refused if any grants option is also given. Without either set of
options this program refuses to start (exit 2): there is no silent default that lets a signature stand in for policy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from cns_interop.decision import RemoteDecisionGuard
from cns_interop.envelope import Refused
from cns_interop.grants import Approval, GrantStore, GrantTable, load_grants
from cns_interop.ledger import FileLedger
from cns_interop.trust import TrustPolicy
from cns_interop.wire import loads

_APPROVAL_KEYS = {"approver", "decision_id", "action", "subject_digest", "expires_at", "sig"}


def _identity_and_digest(artifact: object) -> Tuple[str, str]:
    if not isinstance(artifact, list) or len(artifact) != 2 or not all(isinstance(x, str) for x in artifact):
        raise ValueError("an artifact here is [identity, digest]")
    return artifact[0], artifact[1]


def _refuse(code: str, reason: str, status: int = 0) -> int:
    print(json.dumps({"refused": {"code": code, "reason": reason}}))
    return status


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="act once on a remote UAI-1 decision, under the receiver's own policy")
    p.add_argument("--acting-for", required=True)
    p.add_argument("--capability", required=True, help="the capability this process acts on; others are refused")
    p.add_argument("--capability-version", required=True, type=int)
    p.add_argument("--trust", required=True, help="comma-separated decider identities this process accepts")
    p.add_argument("--ledger", required=True, help="the decision ledger, shared by every process acting for the identity")
    p.add_argument("--grants", help="the receiver's grants file ({\"grants\": [...]})")
    p.add_argument("--grant-store", help="the SQLite file that holds withdrawals (durable, shared)")
    p.add_argument("--action", help="the action this process performs; a grant must name it")
    p.add_argument("--audit", help="the hash-chained audit record")
    p.add_argument("--permit-ledger", help="where permits are spent (default: the decision ledger path + '.permits')")
    p.add_argument("--lease-ms", type=int, default=30_000, help="how long a decision is leased while permission is checked")
    p.add_argument("--decision-only", action="store_true",
                   help="revision 2 behavior: a verified decision opens the action by itself (NOT receiver-authorized)")
    cfg = p.parse_args(argv)
    policy_args = (cfg.grants, cfg.grant_store, cfg.action, cfg.audit)
    if cfg.decision_only:
        if any(policy_args) or cfg.permit_ledger:
            return _refuse("config", "--decision-only cannot be combined with receiver policy options", 2)
        print("act.py: --decision-only: a signed decision opens this action by itself; it is NOT receiver-authorized",
              file=sys.stderr)
    elif not all(policy_args):
        return _refuse("config", "act.py acts only under the receiver's policy: give --grants, --grant-store, --action "
                                 "and --audit, or --decision-only to accept that a signature alone opens the action", 2)
    stdin = sys.stdin.read()
    try:
        table = None
        if not cfg.decision_only:
            table = GrantTable(load_grants(Path(cfg.grants).read_text(encoding="utf-8")), audit_path=cfg.audit,
                               store=GrantStore(cfg.grant_store),
                               permit_ledger=FileLedger(cfg.permit_ledger or cfg.ledger + ".permits"),
                               permit_lease_ms=cfg.lease_ms)
        guard = RemoteDecisionGuard(_identity_and_digest, acting_for=cfg.acting_for,
                                    capability=(cfg.capability, cfg.capability_version),
                                    trust=TrustPolicy(pinned=frozenset(filter(None, cfg.trust.split(",")))),
                                    ledger=FileLedger(cfg.ledger), grants=table,
                                    action=None if cfg.decision_only else cfg.action)
    except (ValueError, OSError) as exc:
        return _refuse("config", str(exc), 2)
    except Refused as exc:
        return _refuse(exc.code, exc.reason, 2)
    try:
        job = loads(stdin)  # as strict as an envelope: a repeated key, a float or NaN, or over 1 MiB is refused
        needed = {"decision", "terms", "accept_digest", "artifact"}
        if not needed <= set(job) <= needed | {"approval"}:
            raise Refused("malformed", "a job is exactly decision, terms, accept_digest, artifact and optionally approval")
        approval = None
        if "approval" in job:
            a = job["approval"]
            if not isinstance(a, dict) or set(a) != _APPROVAL_KEYS:
                raise Refused("approval", "an approval is exactly " + ", ".join(sorted(_APPROVAL_KEYS)))
            approval = Approval(**a)
        guard.authorize(job["decision"], terms=job["terms"], accept_digest=job["accept_digest"],
                        lease_ms=None if cfg.decision_only else cfg.lease_ms, approval=approval)
    except Refused as exc:
        return _refuse(exc.code, exc.reason)
    permitted = guard(job["artifact"])
    result: dict = {"permitted": permitted}  # type: ignore[type-arg]
    if not cfg.decision_only:
        try:
            if permitted:  # this program only says yes: the permission is spent now, so a second run is refused
                guard.complete()
                permit = guard.permit
                result["permit"] = {"grant": permit.grant, "action": permit.action, "audit_digest": permit.audit_digest,
                                    "idempotency_key": permit.idempotency_key}
            else:
                guard.abort()  # the artifact was not the judged document: nothing was used up
        except Refused as exc:
            return _refuse(exc.code, exc.reason)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

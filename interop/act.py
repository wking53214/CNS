"""act.py: the process that performs an action, deciding on its own whether the RECEIVER permits it.

A signed decision is not permission. This program acts only under the receiver's own policy, which comes from its
command line and files, never from the job:

    python interop/act.py --acting-for <identity> --capability <name> --capability-version <n>
                          --trust <decider identity>[,...] --ledger <decision ledger file>
                          --grants <grants.json> --grant-store <state.db> --action <name> --audit <audit.jsonl>
                          [--permit-ledger <file>] [--lease-ms <ms>]
                          [--ledger-backend postgres --ledger-dsn-env <ENV VAR> [--require-sync-replication]]
                          [--policy-backend postgres [--publish-policy <version>]]  [--diagnostics]

The job comes on stdin, one JSON object, and can only narrow what is accepted, never widen it:

    {"decision": <decision envelope>, "terms": <the agreed terms>, "accept_digest": "<hex>",
     "artifact": ["<identity>", "<digest>"], "approval": <a person's signed approval, only if the grant needs one>}

What it checks, in this order: the job is strict JSON (a duplicate key, a float, NaN, or more than 1 MiB is refused
before anything is verified); the decision is genuine, for this requester and capability, from a decider this process
trusts, and new (shared ledger); the receiver's GRANT for that purpose exists, is in force, was not withdrawn, names that
decider and action, and covers the disclosure; a person approved, if the grant says one must; the terms are the terms the
decision was made under; the permit for this decision and action has not been used. Every outcome is written to the audit
record. It prints {"permitted": true|false, "permit": {...}} or {"refused": {"code": ..., "reason": ...}}.

LEDGER BACKEND (the receiver's choice, never the job's). The default is files, which are safe for processes on ONE host.
`--ledger-backend sqlite` is the same single-host promise in a SQLite file, the format the Node runner (interop/node/act.mjs)
shares. `--ledger-backend postgres` keeps decisions and permits in PostgreSQL (tables `<prefix>_decisions` and `<prefix>_permits`), so
processes on any number of hosts share them. The connection string is read from the environment variable NAMED by
`--ledger-dsn-env`, so it is never on a command line. If the database cannot be reached the program refuses (exit 2): there
is no fallback to files. Under UAI_PROFILE=production the file backend is refused outright. `--diagnostics` connects, then
prints the backends actually in force (the DSN is never printed) and exits without reading a job.

POLICY BACKEND. By default the grant store (withdrawals) is a SQLite file and the audit record a file, both safe for one
host. `--policy-backend postgres` (same DSN variable) keeps withdrawals and ONE hash-chained audit record in PostgreSQL for
every receiver host, and refuses to start if this host's grants file is not the policy an operator published
(`--publish-policy <next version>` publishes it and exits; two operators cannot both publish the same version). Then
`--grant-store` and `--audit` are not given. The production profile requires it.

`--decision-only` keeps the behavior of revision 2, in which a verified decision opens the action by itself. It is NOT
receiver-authorized, it says so on stderr, and it is refused if any grants option is also given. Without either set of
options this program refuses to start (exit 2): there is no silent default that lets a signature stand in for policy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from cns_interop import crypto_backend
from cns_interop.decision import RemoteDecisionGuard
from cns_interop.envelope import Refused
from cns_interop.grants import Approval, GrantStore, GrantTable, load_grants
from cns_interop.ledger import FileLedger, SqliteLedger
from cns_interop.policy_postgres import policy_digest
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


def _shared_policy(cfg: argparse.Namespace, grants: object) -> Tuple[object, object, dict]:  # type: ignore[type-arg]
    if cfg.ledger_backend != "postgres":
        raise ValueError("--policy-backend postgres needs --ledger-backend postgres (one database, one DSN variable)")
    from cns_interop.policy_postgres import PostgresAudit, PostgresGrantStore
    dsn = os.environ.get(cfg.ledger_dsn_env, "")
    kw = {"require_sync_replication": bool(cfg.require_sync_replication)}
    return (PostgresGrantStore(dsn, prefix=cfg.ledger_prefix + "_policy", **kw),  # type: ignore[arg-type]
            PostgresAudit(dsn, prefix=cfg.ledger_prefix + "_audit", **kw), {})  # type: ignore[arg-type]


def _ledgers(cfg: argparse.Namespace) -> Tuple[object, object]:
    """The decision ledger and the permit ledger the receiver chose. Nothing here falls back to a weaker backend."""
    if cfg.ledger_backend == "postgres":
        if cfg.ledger or cfg.permit_ledger:
            raise ValueError("--ledger and --permit-ledger name files; the postgres backend takes only --ledger-dsn-env")
        if not cfg.ledger_dsn_env:
            raise ValueError("--ledger-backend postgres needs --ledger-dsn-env, the name of the variable holding the DSN")
        dsn = os.environ.get(cfg.ledger_dsn_env, "")
        if not dsn:
            raise ValueError(f"the environment variable {cfg.ledger_dsn_env} is not set; there is no fallback to a file ledger")
        from cns_interop.ledger_postgres import PostgresLedger
        kw = {"require_sync_replication": bool(cfg.require_sync_replication)}
        decisions = PostgresLedger(dsn, table=cfg.ledger_prefix + "_decisions", **kw)  # type: ignore[arg-type]
        permits = None if cfg.decision_only else PostgresLedger(dsn, table=cfg.ledger_prefix + "_permits", **kw)  # type: ignore[arg-type]
        return decisions, permits
    if crypto_backend.production():
        raise ValueError("the production profile does not accept a single-host ledger; use --ledger-backend postgres")
    if cfg.ledger_dsn_env or cfg.require_sync_replication:
        raise ValueError("--ledger-dsn-env and --require-sync-replication belong to the postgres backend")
    if not cfg.ledger:
        raise ValueError("the file backend needs --ledger")
    cls = SqliteLedger if cfg.ledger_backend == "sqlite" else FileLedger
    permits = None if cfg.decision_only else cls(cfg.permit_ledger or cfg.ledger + ".permits")
    return cls(cfg.ledger), permits


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="act once on a remote UAI-1 decision, under the receiver's own policy")
    p.add_argument("--acting-for", required=True)
    p.add_argument("--capability", required=True, help="the capability this process acts on; others are refused")
    p.add_argument("--capability-version", required=True, type=int)
    p.add_argument("--trust", required=True, help="comma-separated decider identities this process accepts")
    p.add_argument("--ledger", help="the decision ledger file, shared by every process acting for the identity (file backend)")
    p.add_argument("--ledger-backend", choices=("file", "sqlite", "postgres"), default="file",
                   help="where decisions and permits are spent; file is single-host, postgres is shared across hosts")
    p.add_argument("--ledger-dsn-env", help="the NAME of the environment variable that holds the PostgreSQL connection string")
    p.add_argument("--ledger-prefix", default="uai", help="table name prefix for the postgres backend")
    p.add_argument("--require-sync-replication", action="store_true",
                   help="postgres: refuse to write unless the server demands quorum-durable commit")
    p.add_argument("--policy-backend", choices=("local", "postgres"), default="local",
                   help="where withdrawals and the audit record live; local is one host, postgres is shared by every host")
    p.add_argument("--publish-policy", type=int, metavar="VERSION",
                   help="postgres policy: publish this host's grants file as the policy VERSION (must be the next one), then exit")
    p.add_argument("--diagnostics", action="store_true",
                   help="connect, print the backends in force as JSON, and exit without reading a job")
    p.add_argument("--grants", help="the receiver's grants file ({\"grants\": [...]})")
    p.add_argument("--grant-store", help="the SQLite file that holds withdrawals (durable, shared)")
    p.add_argument("--action", help="the action this process performs; a grant must name it")
    p.add_argument("--audit", help="the hash-chained audit record")
    p.add_argument("--permit-ledger", help="where permits are spent (default: the decision ledger path + '.permits')")
    p.add_argument("--lease-ms", type=int, default=30_000, help="how long a decision is leased while permission is checked")
    p.add_argument("--decision-only", action="store_true",
                   help="revision 2 behavior: a verified decision opens the action by itself (NOT receiver-authorized)")
    cfg = p.parse_args(argv)
    shared_policy = cfg.policy_backend == "postgres"
    if shared_policy and (cfg.grant_store or cfg.audit):
        return _refuse("config", "--policy-backend postgres keeps withdrawals and the audit record in the database; "
                                 "do not give --grant-store or --audit", 2)
    if crypto_backend.production() and not shared_policy and not cfg.decision_only:
        return _refuse("config", "the production profile does not accept host-local withdrawals and audit; "
                                 "use --policy-backend postgres", 2)
    policy_args = (cfg.grants, cfg.action) if shared_policy else (cfg.grants, cfg.grant_store, cfg.action, cfg.audit)
    if cfg.decision_only:
        if any(policy_args) or cfg.permit_ledger:
            return _refuse("config", "--decision-only cannot be combined with receiver policy options", 2)
        print("act.py: --decision-only: a signed decision opens this action by itself; it is NOT receiver-authorized",
              file=sys.stderr)
    elif not all(policy_args):
        return _refuse("config", "act.py acts only under the receiver's policy: give --grants, --grant-store, --action "
                                 "and --audit, or --decision-only to accept that a signature alone opens the action", 2)
    try:
        decisions, permits = _ledgers(cfg)
    except (ValueError, OSError, RuntimeError) as exc:
        return _refuse("config", str(exc), 2)
    except Refused as exc:
        return _refuse(exc.code, exc.reason, 2)
    if cfg.diagnostics:
        try:
            crypto = crypto_backend.diagnostics()
        except RuntimeError as exc:
            return _refuse("config", str(exc), 2)
        print(json.dumps({"ledger_backend": cfg.ledger_backend, "decision_ledger": type(decisions).__name__,
                          "permit_ledger": type(permits).__name__ if permits is not None else None,
                          "mode": "decision-only" if cfg.decision_only else "receiver-policy",
                          "policy_backend": "none" if cfg.decision_only else cfg.policy_backend,
                          "sync_replication_required": bool(cfg.require_sync_replication), "crypto": crypto}, sort_keys=True))
        return 0
    stdin = sys.stdin.read()
    try:
        table = None
        if not cfg.decision_only:
            loaded = load_grants(Path(cfg.grants).read_text(encoding="utf-8"))
            if shared_policy:
                store, sink, extra = _shared_policy(cfg, loaded)
                if cfg.publish_policy is not None:
                    store.publish_policy(cfg.publish_policy, policy_digest(loaded))
                    print(json.dumps({"published": {"version": cfg.publish_policy, "digest": policy_digest(loaded)}}))
                    return 0
                store.require_policy(policy_digest(loaded))  # stale or divergent grants: this host does not act
            else:
                store, sink, extra = GrantStore(cfg.grant_store), None, {"audit_path": cfg.audit}
            table = GrantTable(loaded, store=store, permit_ledger=permits, permit_lease_ms=cfg.lease_ms,
                               audit_sink=sink, **extra)
        guard = RemoteDecisionGuard(_identity_and_digest, acting_for=cfg.acting_for,
                                    capability=(cfg.capability, cfg.capability_version),
                                    trust=TrustPolicy(pinned=frozenset(filter(None, cfg.trust.split(",")))),
                                    ledger=decisions, grants=table,
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

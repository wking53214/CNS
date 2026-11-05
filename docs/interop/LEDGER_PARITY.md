# Node and Python PostgreSQL ledger parity

STATUS: DRAFT (RACE-02 I-08, R2-C-06). The table below was verified from source on branch `race02-parity`, based on
`race02-clock`. Statements are labelled implemented, tested, experimental or planned only in the final version of this
file; in this draft every "plan" is a plan, not a claim.

Scope: the receiver-side storage contract of a UAI-1 receiver that runs on PostgreSQL. Python is
`cns_interop/ledger_postgres.py`, `cns_interop/policy_postgres.py`, `cns_interop/fencing.py`, `cns_interop/grants.py`,
`interop/act.py`. Node is `interop/node/pg.mjs`, `grants.mjs`, `act.mjs`, `uai.mjs`. Node talks to PostgreSQL through the
`psql` binary (no npm dependency). `cns/` is not touched.

## The baseline table, verified from source

| # | Contract element | Python (cite) | Node before this work (cite) | Verdict | Plan |
|---|---|---|---|---|---|
| 1 | Decision and permit ledger (spend, reserve, commit, release, lease takeover, fence, DB clock) | `ledger_postgres.py` `PostgresLedger` (`_grant`, `_commit_sql`, `release`) | `pg.mjs` `PostgresLedger` (same SQL, same table) | equivalent by construction; never run through the conformance properties | run Node through `ledger_conformance` (step 2) |
| 2 | Ledger conformance suite membership | `tests/test_ledger_postgres.py:56` runs every property | no Node entry in `tests/test_ledger_conformance.py` or anywhere | accidental gap | step 2 |
| 3 | Grant withdrawals in PostgreSQL | `policy_postgres.py:53` `PostgresGrantStore.withdraw`/`is_withdrawn`; `act.py` `_shared_policy` | `grants.mjs` `GrantStore` is a SQLite file; `act.mjs:90` refuses `--policy-backend postgres` | accidental: a second receiver host in Node never sees a withdrawal | step 3 |
| 4 | Audit chain in PostgreSQL | `policy_postgres.py:108` `PostgresAudit` (`append`, `head`, `verify`) | `grants.mjs` `appendAudit`/`verifyAudit` write a local file under a lock file | accidental for the shared chain; the local file stays (single host) | step 4 |
| 5 | Policy version publish and require | `policy_postgres.py:80` `publish_policy`, `:97` `require_policy`, `policy_digest`; `act.py` `--publish-policy` | none | accidental | step 5 |
| 6 | Quorum-durable commit | `ledger_postgres.py:143` `_require_quorum`, `:100-105` cancelled-wait notice refused; `--require-sync-replication` | none (`pg.mjs` header says so) | accidental | step 6 |
| 7 | `commit_in` (spend on the caller's transaction) | `ledger_postgres.py:269` | none | the shape cannot be copied: psql is one process per call, there is no caller connection | step 6: an equivalent atomic API, `commitIn(reservation, sql, vars)`, documented as a different shape with the same guarantee |
| 8 | Fencing check | `fencing.py:24` `FencedTarget` | none; `grants.mjs:78` SqliteLedger issues `fence: 0` as Python's file ledgers do | accidental for the target check | step 3 |
| 9 | Error codes `stale_policy`, `conflict`, `fenced` | `contracts/uai1/errors.json` says Python-only | not emitted | follows 3 to 8 | registry changed to `both` when Node emits them |
| 10 | Connection hardening: TCP user timeout, commit-wait watchdog | `ledger_postgres.py:75`, `:94-100` | outer child kill bound only (`pg.mjs` `_boundMs`) | intentional: libpq tool, no per-socket control | document |
| 11 | Connection options | psycopg takes any libpq option | `pg.mjs` `ENV_OF` maps a fixed list and refuses the rest | intentional, refusing not dropping | document |
| 12 | Client | psycopg (optional extra) | the `psql` binary | intentional | document |
| 13 | Audit entry text | `json.dumps(sort_keys=True)` | will be sorted-key `JSON.stringify` | intentional: verification re-parses and re-derives digests, so text bytes are not part of the contract | document, cross-verify tests |
| 14 | `--diagnostics` | `act.py` | absent | intentional for now (operator tool, no safety effect) | document as planned |
| 15 | Signed revocations (identity, endorsement) | `revocation.py` file store | `uai.mjs` `RevocationStore` file store | equivalent: neither language has a PostgreSQL revocation store | document, not a difference |
| 16 | Audit file recovery (`audit_recover`) | `grants.py` `_recover_audit` | none | intentional: explicit operator action in Python only | document |
| 17 | `--ledger-backend file` | `act.py` | none (sqlite only) | intentional: a JSONL file ledger is not a production backend in either language | document |

This is a draft: rows 3 to 9 are confirmed or corrected by the steps that implement them.

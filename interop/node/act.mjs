// act.mjs: the Node twin of interop/act.py. One job on stdin, the receiver's policy on the command line and in files, one
// JSON answer on stdout. It opens the SAME SQLite ledger and grant-store files as `act.py --ledger-backend sqlite`, so a
// decision spent or a grant withdrawn through either program is seen by the other. With `--ledger-backend postgres` it
// spends decisions and permits in the same PostgreSQL tables as `act.py --ledger-backend postgres` (`<prefix>_decisions`,
// `<prefix>_permits`), so receivers in either language on any number of hosts share one ledger. The DSN is read from the
// environment variable named by --ledger-dsn-env, never from the command line; withdrawals and the audit stay in local files. A signed decision is not permission:
// this program acts only under the receiver's grants (--decision-only is the explicit, loud exception).
//
//   node interop/node/act.mjs --acting-for <id> --capability <name> --capability-version <n> --trust <id>[,<id>]
//        --ledger <sqlite file> --grants <grants.json> --grant-store <sqlite file> --action <name> --audit <file>
//        [--permit-ledger <sqlite file>] [--lease-ms <ms>] | --decision-only
//   the shared backend: --ledger-backend postgres --ledger-dsn-env <ENV VAR> [--ledger-prefix <prefix>] in place of --ledger

import { readFileSync } from "node:fs";
import * as U from "./uai.mjs";
import * as G from "./grants.mjs";
import * as P from "./pg.mjs";

const refuse = (code, reason, status = 0) => { console.log(JSON.stringify({ refused: { code, reason } })); return status; };
const APPROVAL_KEYS = "action,approver,decision_id,expires_at,sig,subject_digest";
const FLAGS = new Set(["decision-only"]);

function parse(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) throw new Error(`unexpected argument ${a}`);
    const k = a.slice(2);
    if (FLAGS.has(k)) o[k] = true; else { if (i + 1 >= argv.length) throw new Error(`--${k} needs a value`); o[k] = argv[++i]; }
  }
  return o;
}

function main() {
  let cfg;
  try { cfg = parse(process.argv.slice(2)); } catch (e) { return refuse("config", e.message, 2); }
  for (const k of ["acting-for", "capability", "capability-version", "trust"]) if (!cfg[k]) return refuse("config", `--${k} is required`, 2);
  const backend = cfg["ledger-backend"] ?? "sqlite";
  let ledgerFor;
  if (backend === "postgres") {
    if (cfg.ledger || cfg["permit-ledger"]) return refuse("config", "--ledger and --permit-ledger name files; the postgres backend takes only --ledger-dsn-env", 2);
    if (!cfg["ledger-dsn-env"]) return refuse("config", "--ledger-backend postgres needs --ledger-dsn-env, the name of the variable holding the DSN", 2);
    const dsn = process.env[cfg["ledger-dsn-env"]] ?? "";
    if (!dsn) return refuse("config", `the environment variable ${cfg["ledger-dsn-env"]} is not set; there is no fallback to a file ledger`, 2);
    const prefix = cfg["ledger-prefix"] ?? "uai";
    ledgerFor = (kind) => new P.PostgresLedger(dsn, { table: `${prefix}_${kind}` });
  } else if (backend === "sqlite") {
    if (!cfg.ledger) return refuse("config", "--ledger is required", 2);
    if (cfg["ledger-dsn-env"] || cfg["ledger-prefix"]) return refuse("config", "--ledger-dsn-env and --ledger-prefix belong to the postgres backend", 2);
    ledgerFor = (kind) => new G.SqliteLedger(kind === "decisions" ? cfg.ledger : (cfg["permit-ledger"] ?? cfg.ledger + ".permits"));
  } else return refuse("config", "--ledger-backend is sqlite or postgres", 2);
  const policy = ["grants", "grant-store", "action", "audit"].map((k) => cfg[k]);
  if (cfg["decision-only"]) {
    if (policy.some(Boolean) || cfg["permit-ledger"]) return refuse("config", "--decision-only cannot be combined with receiver policy options", 2);
    console.error("act.mjs: --decision-only: a signed decision opens this action by itself; it is NOT receiver-authorized");
  } else if (!policy.every(Boolean)) {
    return refuse("config", "act.mjs acts only under the receiver's policy: give --grants, --grant-store, --action and --audit, or --decision-only to accept that a signature alone opens the action", 2);
  }
  const stdin = readFileSync(0);
  let guard;
  try {
    let table = null;
    if (!cfg["decision-only"]) {
      table = new G.GrantTable(G.loadGrants(readFileSync(cfg.grants, "utf8")), {
        auditPath: cfg.audit, store: new G.GrantStore(cfg["grant-store"]),
        permitLedger: ledgerFor("permits"), permitLeaseMs: Number(cfg["lease-ms"] ?? 30000) });
    }
    guard = new U.RemoteDecisionGuard((a) => { if (!Array.isArray(a) || a.length !== 2 || !a.every((x) => typeof x === "string")) throw new Error("an artifact here is [identity, digest]"); return a; }, {
      actingFor: cfg["acting-for"], capability: [cfg.capability, Number(cfg["capability-version"])],
      trust: new U.PinnedTrust(cfg.trust.split(",").filter(Boolean)), ledger: ledgerFor("decisions"),
      grants: table, action: cfg["decision-only"] ? null : cfg.action });
  } catch (e) { return e instanceof U.Refused ? refuse(e.code, e.reason, 2) : refuse("config", e.message, 2); }
  let job;
  try {
    job = U.strictParseBytes(stdin);
    const keys = Object.keys(job ?? {}).sort().join();
    if (!["accept_digest,artifact,decision,terms", "accept_digest,approval,artifact,decision,terms"].includes(keys)) throw new U.Refused("malformed", "a job is exactly decision, terms, accept_digest, artifact and optionally approval");
    let approval = null;
    if ("approval" in job) {
      if (!job.approval || typeof job.approval !== "object" || Object.keys(job.approval).sort().join() !== APPROVAL_KEYS) throw new U.Refused("approval", "an approval is exactly " + APPROVAL_KEYS.split(",").join(", "));
      approval = job.approval;
    }
    guard.authorize(job.decision, { terms: job.terms, acceptDigest: job.accept_digest, leaseMs: cfg["decision-only"] ? null : Number(cfg["lease-ms"] ?? 30000), approval });
  } catch (e) { return e instanceof U.Refused ? refuse(e.code, e.reason) : refuse("malformed", String(e.message)); }
  const permitted = guard.call(job.artifact);
  const result = { permitted };
  if (!cfg["decision-only"]) {
    try {
      if (permitted) { guard.complete(); const p = guard.permit; result.permit = { grant: p.grant, action: p.action, audit_digest: p.audit_digest, idempotency_key: p.idempotency_key }; } else guard.abort();
    } catch (e) { return e instanceof U.Refused ? refuse(e.code, e.reason) : refuse("unavailable", String(e.message)); }
  }
  console.log(JSON.stringify(result));
  return 0;
}
process.exitCode = main();

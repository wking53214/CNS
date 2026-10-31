// act.mjs: the Node twin of interop/act.py. One job on stdin, the receiver's policy on the command line and in files, one
// JSON answer on stdout. It opens the SAME SQLite ledger and grant-store files as `act.py --ledger-backend sqlite`, so a
// decision spent or a grant withdrawn through either program is seen by the other. A signed decision is not permission:
// this program acts only under the receiver's grants (--decision-only is the explicit, loud exception).
//
//   node interop/node/act.mjs --acting-for <id> --capability <name> --capability-version <n> --trust <id>[,<id>]
//        --ledger <sqlite file> --grants <grants.json> --grant-store <sqlite file> --action <name> --audit <file>
//        [--permit-ledger <sqlite file>] [--lease-ms <ms>] | --decision-only

import { readFileSync } from "node:fs";
import * as U from "./uai.mjs";
import * as G from "./grants.mjs";

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
  for (const k of ["acting-for", "capability", "capability-version", "trust", "ledger"]) if (!cfg[k]) return refuse("config", `--${k} is required`, 2);
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
        permitLedger: new G.SqliteLedger(cfg["permit-ledger"] ?? cfg.ledger + ".permits"), permitLeaseMs: Number(cfg["lease-ms"] ?? 30000) });
    }
    guard = new U.RemoteDecisionGuard((a) => { if (!Array.isArray(a) || a.length !== 2 || !a.every((x) => typeof x === "string")) throw new Error("an artifact here is [identity, digest]"); return a; }, {
      actingFor: cfg["acting-for"], capability: [cfg.capability, Number(cfg["capability-version"])],
      trust: new U.PinnedTrust(cfg.trust.split(",").filter(Boolean)), ledger: new G.SqliteLedger(cfg.ledger),
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

// Test driver: run a list of policy and fencing operations against interop/node/pg_policy.mjs and fencing.mjs, one JSON result
// per operation. stdin: {"dsn_env": name, "prefix": p, "ops": [[op, ...args], ...]}. The DSN comes from the named environment
// variable, never from the command line.
import { readFileSync } from "node:fs";
import * as U from "../../interop/node/uai.mjs";
import * as G from "../../interop/node/grants.mjs";
import * as F from "../../interop/node/fencing.mjs";
import * as PP from "../../interop/node/pg_policy.mjs";

const job = JSON.parse(readFileSync(0, "utf8"));
const out = [];
const dsn = process.env[job.dsn_env] ?? "";
let store;
try { store = new PP.PostgresGrantStore(dsn, { prefix: job.prefix + "_policy" }); }
catch (e) { console.log(JSON.stringify([{ code: e.code ?? "config", reason: e.reason ?? e.message }])); process.exit(0); }
const target = new F.FencedTarget();
const stubLedger = { reserve() { return { key: "k" }; }, commit() {}, release() {} };
for (const [op, ...a] of job.ops) {
  try {
    if (op === "withdraw") { store.withdraw(a[0]); out.push({ ok: true }); }
    else if (op === "is_withdrawn") out.push({ ok: store.isWithdrawn(a[0]) });
    else if (op === "check_terms") {   // [grants document, terms]: the receiver's grant check against the shared store
      const table = new G.GrantTable(G.loadGrants(JSON.stringify(a[0])), { store, permitLedger: stubLedger });
      out.push({ ok: table.checkTerms(a[1]).id });
    }
    else if (op === "fence") { target.check(a[0], a[1]); out.push({ ok: true }); }
    else throw new Error(`unknown op ${op}`);
  } catch (e) { out.push({ code: e instanceof U.Refused ? e.code : "error", reason: e.reason ?? e.message }); }
}
console.log(JSON.stringify(out));

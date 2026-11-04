// Test driver: run a list of ledger operations against interop/node/pg.mjs and print one JSON result per operation.
// stdin: {"dsn_env": name, "table": t, "psql": optional path, "ops": [[op, ...args], ...]}. The DSN comes from the named
// environment variable, never from the command line. A reservation is referred to by the index of the op that made it.
import { readFileSync } from "node:fs";
import { PostgresLedger } from "../../interop/node/pg.mjs";

const job = JSON.parse(readFileSync(0, "utf8"));
const out = [];
let L;
try { L = new PostgresLedger(process.env[job.dsn_env] ?? "", { table: job.table, ...(job.psql ? { psql: job.psql } : {}) }); }
catch (e) { console.log(JSON.stringify([{ code: e.code ?? "config", reason: e.reason ?? e.message }])); process.exit(0); }
const held = {};
for (const [i, [op, ...a]] of job.ops.entries()) {
  try {
    if (op === "spend") { L.spend(a[0], a[1], a[2] ?? null); out.push({ ok: true }); }
    else if (op === "reserve") { const r = L.reserve(a[0], a[1], a[2] ?? null, { leaseMs: a[3] }); held[i] = r; out.push({ ok: { fence: r.fence, leaseUntil: r.leaseUntil } }); }
    else if (op === "commit") { L.commit(held[a[0]]); out.push({ ok: true }); }
    else if (op === "release") { L.release(a[1] ? { ...held[a[0]], token: "f".repeat(32) } : held[a[0]]); out.push({ ok: true }); }
    else if (op === "sleep") { Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, a[0]); out.push({ ok: true }); }
    else if (op === "server_now") { out.push({ ok: L.serverNowMs() }); }
    else throw new Error(`unknown op ${op}`);
  } catch (e) { out.push({ code: e.code ?? "error", reason: e.reason ?? e.message }); }
}
console.log(JSON.stringify(out));

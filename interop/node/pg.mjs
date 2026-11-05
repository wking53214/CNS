// pg.mjs: the Node twin of cns_interop/ledger_postgres.PostgresLedger. Same table, same SQL, same rules, so a Python and a
// Node receiver on different hosts share ONE ledger: a message spent through either language is refused by the other.
//
// HOW IT TALKS TO POSTGRESQL. Node has no PostgreSQL client in its standard library, and the Node receiver is synchronous,
// so each operation runs the standard `psql` client as a child process (spawnSync), one transaction per call, exactly as
// Python's PgGuard opens one connection per call. There is no npm dependency; the host needs `psql` (postgresql-client).
//   * Values reach SQL only as psql variables quoted by psql itself (:'name'), never by string building. Table names are
//     checked identifiers, as in Python.
//   * The connection string never appears on a command line: it is split into libpq's PG* environment variables for the
//     child alone (a password lands in PGPASSWORD, which only the same user can read from /proc).
//   * Time is the DATABASE's (clock_timestamp()), as in Python. A host with a wrong clock cannot shorten anyone's lease, and a
//     message that has expired by the database's clock is refused ('expired') by spend and reserve, never granted: a row the
//     ledger forgot keepMs after expiry is one no receiver can spend again whatever its own clock says (RACE-02 R2-C-01).
//   * Failure is refusal: psql missing at call time, a connection that cannot be made, a statement or lock timeout, a
//     child that runs past its bound, any error: Refused('unavailable'). An ambiguous commit is 'unavailable' too, and the
//     row may then stay held until its lease lapses, the documented model (docs/interop/CONSISTENCY.md).
//
// NOT HERE. Python's require_sync_replication (quorum-durable commit) is not implemented in Node: a Node receiver against a
// standby setup gets the primary's guarantee only. The receiver's withdrawals and audit record stay in Node's local files
// (grants.mjs); only the decision and permit ledgers are shared.

import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { MAX_INT, Refused } from "./uai.mjs";

export const NAME = /^[a-z_][a-z0-9_]{0,40}$/;
export const NOW_MS = "(extract(epoch from clock_timestamp()) * 1000)::bigint";
const MAX_LEASE_MS = 3600 * 1000;
const EARLIEST_PLAUSIBLE_MS = 946684800000;   // 2000-01-01T00:00:00Z, as Python's _EARLIEST_PLAUSIBLE_MS

// The database's answer to the time query as an integer, or Refused('unavailable') when it is not a plausible time in ms:
// no row, NULL (an empty line), more than one row or column, not decimal digits (so never NaN, a sign, a fraction, an
// exponent or "Infinity"), before 2000, or beyond 2**53 - 1. As Python's _server_time (R2-C-04: NaN used to pass).
export function serverTimeOf(rows) {
  const text = Array.isArray(rows) && rows.length === 1 && Array.isArray(rows[0]) && rows[0].length === 1 ? rows[0][0] : null;
  const value = typeof text === "string" && /^[0-9]{1,16}$/.test(text) ? Number(text) : NaN;
  if (!Number.isSafeInteger(value) || value < EARLIEST_PLAUSIBLE_MS || value > MAX_INT) throw new Refused("unavailable", "the ledger database did not answer the time query with a plausible time in ms, so message lifetimes cannot be judged");
  return value;
}
const ENV_OF = {
  host: "PGHOST", hostaddr: "PGHOSTADDR", port: "PGPORT", user: "PGUSER", password: "PGPASSWORD", dbname: "PGDATABASE",
  sslmode: "PGSSLMODE", sslrootcert: "PGSSLROOTCERT", sslcert: "PGSSLCERT", sslkey: "PGSSLKEY", sslcrl: "PGSSLCRL",
  channel_binding: "PGCHANNELBINDING", target_session_attrs: "PGTARGETSESSIONATTRS", application_name: "PGAPPNAME",
  connect_timeout: "PGCONNECT_TIMEOUT", options: "PGOPTIONS", gssencmode: "PGGSSENCMODE", require_auth: "PGREQUIREAUTH",
};

// A libpq connection string, URL or key=value form, as PG* variables. Anything this cannot map is refused, not dropped.
export function dsnToEnv(dsn) {
  if (typeof dsn !== "string" || !dsn.trim()) throw new RangeError("the PostgreSQL connection string is empty");
  const pairs = [];
  if (/^postgres(ql)?:\/\//.test(dsn)) {
    let u;
    try { u = new URL(dsn); } catch { throw new RangeError("the PostgreSQL connection URL cannot be parsed"); }
    if (u.username) pairs.push(["user", decodeURIComponent(u.username)]);
    if (u.password) pairs.push(["password", decodeURIComponent(u.password)]);
    if (u.hostname) pairs.push(["host", u.hostname.replace(/^\[(.*)\]$/, "$1")]);
    if (u.port) pairs.push(["port", u.port]);
    const db = decodeURIComponent(u.pathname.replace(/^\//, ""));
    if (db) pairs.push(["dbname", db]);
    for (const [k, v] of u.searchParams) pairs.push([k, v]);
  } else {
    const re = /\s*([A-Za-z_]+)\s*=\s*('((?:[^'\\]|\\.)*)'|[^\s']+)/y;
    let m, at = 0;
    while (at < dsn.length && (m = re.exec(dsn))) {
      pairs.push([m[1], m[3] !== undefined ? m[3].replace(/\\(.)/g, "$1") : m[2]]);
      at = re.lastIndex;
    }
    if (dsn.slice(at).trim()) throw new RangeError("the PostgreSQL connection string is not key=value pairs");
  }
  const env = {};
  for (const [k, v] of pairs) {
    if (!(k in ENV_OF)) throw new RangeError(`the PostgreSQL connection option ${k} is not supported here`);
    env[ENV_OF[k]] = v;
  }
  return env;
}

export class PgGuard {
  constructor(dsn, { connectTimeoutS = 3, statementTimeoutMs = 3000, psql = "psql" } = {}) {
    const base = dsnToEnv(dsn);
    const options = [base.PGOPTIONS, `-c statement_timeout=${statementTimeoutMs}`, `-c lock_timeout=${statementTimeoutMs}`].filter(Boolean).join(" ");
    this._env = { ...base, PGCONNECT_TIMEOUT: String(connectTimeoutS), PGOPTIONS: options };
    // the outer bound: connect, one statement, and a margin; past it the child is killed and the answer is 'unavailable'
    this._boundMs = connectTimeoutS * 1000 + 2 * statementTimeoutMs + 2000;
    this._psql = psql;
    const probe = spawnSync(psql, ["--version"], { encoding: "utf8", timeout: 5000 });
    if (probe.error || probe.status !== 0) throw new Error("PostgreSQL support in Node needs the psql client on this host (postgresql-client)");
  }

  // Run one transaction. `vars` become psql variables; the script reads them only as :'name'. Rows come back as arrays.
  _run(sql, vars = {}) {
    const args = ["-X", "-q", "-A", "-t", "-F", "\t", "-v", "ON_ERROR_STOP=1"];
    for (const [k, v] of Object.entries(vars)) args.push("-v", `${k}=${v === null || v === undefined ? "" : String(v)}`);
    const env = { PATH: process.env.PATH ?? "/usr/bin:/bin", ...(process.env.HOME ? { HOME: process.env.HOME } : {}), ...this._env };
    const r = spawnSync(this._psql, args, { input: `BEGIN;\n${sql}\nCOMMIT;\n`, env, encoding: "utf8", timeout: this._boundMs, killSignal: "SIGKILL", maxBuffer: 256 * 1024 * 1024 });
    if (r.error && r.error.code === "ETIMEDOUT") throw new Refused("unavailable", "the ledger database did not answer in time");
    if (r.error) throw new Refused("unavailable", `the ledger database is unreachable (${r.error.code ?? "spawn failed"})`);
    if (r.status !== 0) throw new Refused("unavailable", "the ledger database did not give a definite answer");
    return r.stdout.split("\n").filter((l) => l !== "").map((l) => l.split("\t"));
  }

  // The database's clock, in ms: the clock every lease is judged by. A missing, malformed or implausible answer is
  // Refused('unavailable'), never a number.
  serverNowMs() { return serverTimeOf(this._run(`SELECT ${NOW_MS};`)); }

  // [skew, server]: this host's clock minus the database's, and the database's time. Refuses ('clock_skew') when the skew
  // exceeds maxSkewMs plus half the round trip, which bounds what the measurement cannot know. As Python's PgGuard._measure.
  _measure(maxSkewMs, clock) {
    if (!Number.isSafeInteger(maxSkewMs) || maxSkewMs < 0) throw new RangeError("maxSkewMs is a non-negative integer");
    const t0 = clock(), server = this.serverNowMs(), t1 = clock();
    const skew = Math.round((t0 + t1) / 2 - server), slack = Math.ceil(Math.abs(t1 - t0) / 2);
    if (Math.abs(skew) > maxSkewMs + slack) throw new Refused("clock_skew", `this host's clock differs from the ledger database's by ${skew} ms, more than the ${maxSkewMs} ms allowed, so message lifetimes cannot be judged`);
    return [skew, server];
  }

  // As Python's PgGuard.check_clock: refuse ('clock_skew') when this host's clock and the database's disagree by more than
  // maxSkewMs plus half the round trip. Returns the measured skew, host minus server.
  checkClock(maxSkewMs, { clock = Date.now } = {}) { return this._measure(maxSkewMs, clock)[0]; }
}

// The Node twin of cns_interop.ledger_postgres.TrustedClock: the database's time, carried between readings by this host's
// MONOTONIC clock (performance.now), for a receiver that judges lifetimes by the database's time and not by its wall clock.
// sync() reads the database and refuses ('clock_skew', or 'unavailable' when the database gives no usable answer); the
// tolerance must be strictly below the ledger's retention window keepMs (RangeError, the runner's 'config'), or a row the
// ledger forgot could still be live for a receiver within tolerance. now() never touches the database and never throws.
// A RemoteDecisionGuard whose clock function carries a sync() calls it on every authorize: the check is per decision.
export class TrustedClock {
  constructor(guard, maxSkewMs, { keepMs, wall = Date.now } = {}) {
    if (!Number.isSafeInteger(maxSkewMs) || maxSkewMs < 0) throw new RangeError("maxSkewMs is a non-negative integer");
    if (!Number.isSafeInteger(keepMs) || maxSkewMs >= keepMs) throw new RangeError(`the clock-skew tolerance (${maxSkewMs} ms) must be strictly below the ledger's retention window keepMs (${keepMs} ms): a row the ledger has forgotten must already be expired for every receiver within tolerance`);
    this._guard = guard; this._max = maxSkewMs; this._wall = wall; this._server = null; this._mono = 0;
  }
  sync() {
    const [skew, server] = this._guard._measure(this._max, this._wall);
    this._server = server; this._mono = performance.now();
    return skew;
  }
  now() {
    if (this._server === null) throw new RangeError("a TrustedClock answers only after sync()");
    return this._server + Math.floor(performance.now() - this._mono);
  }
  // A clock function for RemoteDecisionGuard, carrying sync so the guard re-reads the database for every decision.
  asClock() { const f = () => this.now(); f.sync = () => this.sync(); return f; }
}

export class PostgresLedger extends PgGuard {
  constructor(dsn, { table = "uai_spent", keepMs = 120000, allowCallerTime = false, ...kw } = {}) {
    if (!NAME.test(table)) throw new RangeError("table is a lowercase SQL identifier");
    super(dsn, kw);
    this._t = table; this._keep = keepMs; this._callerTime = allowCallerTime;
    this._run(`SELECT pg_advisory_xact_lock(7243001);
CREATE TABLE IF NOT EXISTS ${table} (sender text NOT NULL, id text NOT NULL, state text NOT NULL CHECK (state IN ('leased','committed')), token text, lease_until bigint, expires_at bigint, fence bigint NOT NULL DEFAULT 0, PRIMARY KEY (sender, id));
CREATE INDEX IF NOT EXISTS ${table}_exp ON ${table} (expires_at);
CREATE SEQUENCE IF NOT EXISTS ${table}_fence;`);
  }

  // How long after its expiry a message's row is kept; a receiver's clock-skew tolerance must stay below it.
  get keepMs() { return this._keep; }

  _grant(sender, id, expiresAt, state, token, leaseMs, now) {
    const callerNow = this._callerTime && now !== undefined && now !== null;
    const t = callerNow ? ":'now'::bigint" : NOW_MS, T = this._t;
    const lease = state === "leased" ? `${t} + :'lease'::bigint` : "NULL";
    // The first row says whether the message has already expired by the ledger's clock ('t' or 'f'); then nothing is written
    // for an expired one (as Python refuses before its writes), and the rest is the grant.
    // A database time that is NULL or before 2000 counts as expired HERE too, so that nothing is written on it (the check
    // below then reports it as 'unavailable'): the write is guarded in SQL, not by what JavaScript does afterwards.
    const expired = `(COALESCE(${t} >= NULLIF(:'exp', '')::bigint, false)${callerNow ? "" : ` OR COALESCE(${t} < ${EARLIEST_PLAUSIBLE_MS}, true)`})`;
    // And before it, the database's time as text ('null' for NULL, so no row vanishes): without a usable one nothing is written.
    const [[nowText], [isExpired], ...rows] = this._run(`SELECT COALESCE((${t})::text, 'null');
SELECT ${expired};
DELETE FROM ${T} WHERE expires_at IS NOT NULL AND expires_at <= ${t} - :'keep'::bigint;
INSERT INTO ${T} (sender, id, state, token, lease_until, expires_at, fence) SELECT :'sender', :'id', :'state', NULLIF(:'token', ''), ${lease}, NULLIF(:'exp', '')::bigint, nextval('${T}_fence') WHERE NOT ${expired}
ON CONFLICT (sender, id) DO UPDATE SET state = EXCLUDED.state, token = EXCLUDED.token, lease_until = EXCLUDED.lease_until, expires_at = EXCLUDED.expires_at, fence = EXCLUDED.fence
WHERE ${T}.state = 'leased' AND ${T}.lease_until <= ${t} RETURNING fence, lease_until;`,
    { sender, id, state, token, lease: leaseMs, exp: expiresAt, now, keep: this._keep });
    if (!callerNow) serverTimeOf([[nowText]]);
    if (isExpired === "t") throw new Refused("expired", "the message has expired by the ledger database's clock, so it is not spent");
    if (rows.length === 0) throw new Refused("replayed", "this message was already accepted once or is being redeemed right now");
    return rows[0];
  }

  spend(sender, id, expiresAt = null, { now } = {}) { this._grant(sender, id, expiresAt, "committed", null, 0, now); }

  reserve(sender, id, expiresAt = null, { leaseMs, now } = {}) {
    if (!Number.isSafeInteger(leaseMs) || leaseMs <= 0 || leaseMs > MAX_LEASE_MS) throw new RangeError(`leaseMs is a positive integer, at most ${MAX_LEASE_MS}`);
    const token = randomBytes(16).toString("hex");
    const [fence, leaseUntil] = this._grant(sender, id, expiresAt, "leased", token, leaseMs, now);
    return { sender, id, expiresAt, token, leaseUntil: Number(leaseUntil), fence: Number(fence), key: `${sender} ${id}` };
  }

  // Ours: committed. Gone (forgotten after expiry): spent now. Someone else's: lease_lost. As Python's _commit_sql.
  commit(r) {
    const T = this._t;
    const [[n]] = this._run(`WITH u AS (UPDATE ${T} SET state = 'committed', token = NULL, lease_until = NULL WHERE sender = :'sender' AND id = :'id' AND token = :'token' RETURNING 1),
i AS (INSERT INTO ${T} (sender, id, state, expires_at, fence) SELECT :'sender', :'id', 'committed', NULLIF(:'exp', '')::bigint, 0 WHERE NOT EXISTS (SELECT 1 FROM u) ON CONFLICT DO NOTHING RETURNING 1)
SELECT (SELECT count(*) FROM u) + (SELECT count(*) FROM i);`, { sender: r.sender, id: r.id, token: r.token, exp: r.expiresAt });
    if (n === "0") throw new Refused("lease_lost", "the message was taken by another redemption after this lease lapsed");
  }

  release(r) {
    const T = this._t;
    const [[gone, present]] = this._run(`WITH d AS (DELETE FROM ${T} WHERE sender = :'sender' AND id = :'id' AND token = :'token' RETURNING 1)
SELECT (SELECT count(*) FROM d), (SELECT count(*) FROM ${T} WHERE sender = :'sender' AND id = :'id');`, { sender: r.sender, id: r.id, token: r.token });
    if (gone === "0" && present !== "0") throw new Refused("lease_lost", "only the holder of a lease can release it");
  }
}

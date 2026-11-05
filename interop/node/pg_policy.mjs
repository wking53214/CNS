// pg_policy.mjs: the receiver's policy state in PostgreSQL, the Node twin of cns_interop/policy_postgres.py, over the same
// tables, so a Python and a Node receiver on different hosts share them. This is the RECEIVER's storage: CNS holds no
// authority here. Like pg.mjs it talks to PostgreSQL through the `psql` client (no npm dependency), and every answer that is
// not definite is Refused('unavailable'), never "not withdrawn".
//   * WITHDRAWALS (PostgresGrantStore): `<prefix>_withdrawn (grant_id text PRIMARY KEY, at bigint)`, the same `withdraw` /
//     `isWithdrawn` as grants.GrantStore, so a GrantTable takes it as its `store`. The withdrawal time is the DATABASE's.
//   * THE AUDIT CHAIN (PostgresAudit): `<prefix>_chain (seq bigserial, digest text UNIQUE, entry text)`, the same chain as
//     Python's PostgresAudit. Each entry carries the digest of the one before (uai.mjs `digest` equals cns subject_digest, so a
//     chain either language wrote verifies in the other, and no historical hash changes). One writer at a time on any host: the
//     INSERT takes the same advisory lock Python takes and is conditional on the head still being the one the digest was
//     computed over, because the digest is computed here between two psql calls; a lost race is retried, never chained wrongly.
import { NAME, NOW_MS, PgGuard } from "./pg.mjs";
import { Refused, digest, strictParse } from "./uai.mjs";

const ZERO = "0".repeat(64);
const MAX_APPEND_TRIES = 64;
const HEAD = (t) => `COALESCE((SELECT digest FROM ${t} ORDER BY seq DESC LIMIT 1), :'zero')`;
// Sorted keys at every depth, as Python's json.dumps(sort_keys=True). Verification re-parses the text and re-derives the digest,
// so the exact bytes of an entry are not part of the contract; the parsed entry and its digest are.
const sortedJson = (v) => JSON.stringify(v, (_k, x) => (x && typeof x === "object" && !Array.isArray(x) ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, x[k]])) : x));

export class PostgresGrantStore extends PgGuard {
  constructor(dsn, { prefix = "uai_policy", ...kw } = {}) {
    if (!NAME.test(prefix)) throw new RangeError("prefix is a lowercase SQL identifier");
    super(dsn, kw);
    this._w = prefix + "_withdrawn"; this._p = prefix + "_version";
    this._run(`SELECT pg_advisory_xact_lock(7243002);
CREATE TABLE IF NOT EXISTS ${this._w} (grant_id text PRIMARY KEY, at bigint NOT NULL);
CREATE TABLE IF NOT EXISTS ${this._p} (version bigint PRIMARY KEY, digest text NOT NULL, at bigint NOT NULL);`);
  }

  // Same surface as grants.GrantStore. A withdrawal committed here is seen by the next check on every host.
  withdraw(grantId) {
    this._run(`INSERT INTO ${this._w} VALUES (:'g', ${NOW_MS}) ON CONFLICT DO NOTHING;`, { g: grantId });
  }
  isWithdrawn(grantId) { return this._run(`SELECT 1 FROM ${this._w} WHERE grant_id = :'g';`, { g: grantId }).length > 0; }
}

export class PostgresAudit extends PgGuard {
  constructor(dsn, { prefix = "uai_audit", ...kw } = {}) {
    if (!NAME.test(prefix)) throw new RangeError("prefix is a lowercase SQL identifier");
    super(dsn, kw);
    this._t = prefix + "_chain";
    this._run(`SELECT pg_advisory_xact_lock(7243004);
CREATE TABLE IF NOT EXISTS ${this._t} (seq bigserial PRIMARY KEY, digest text NOT NULL UNIQUE, entry text NOT NULL);`);
  }

  // Append one entry; returns its digest. Refused('unavailable') when the database gives no definite answer.
  append(entry) {
    const T = this._t;
    for (let attempt = 0; attempt < MAX_APPEND_TRIES; attempt++) {
      const [[prev]] = this._run(`SELECT ${HEAD(T)};`, { zero: ZERO });
      const body = { ...entry, prev };
      const d = digest(body);
      const rows = this._run(`SELECT pg_advisory_xact_lock(hashtext('${T}'));
INSERT INTO ${T} (digest, entry) SELECT :'d', :'text' WHERE ${HEAD(T)} = :'prev' RETURNING 1;`,
      { d, text: sortedJson({ ...body, digest: d }), prev, zero: ZERO });
      if (rows.length === 1) return d;
    }
    throw new Refused("unavailable", "the audit chain kept changing under this writer, so the entry was not written");
  }

  head() { return this._run(`SELECT ${HEAD(this._t)};`, { zero: ZERO })[0][0]; }

  // Re-derive the whole chain and return the last digest; Refused('unavailable') if any entry was edited, removed from the
  // middle or reordered. In pages by seq, so a long chain does not need one huge answer.
  verify() {
    let last = ZERO, n = 0, after = "-9223372036854775807";
    for (;;) {
      const rows = this._run(`SELECT seq, digest, entry FROM ${this._t} WHERE seq > :'after'::bigint ORDER BY seq LIMIT 500;`, { after });
      if (rows.length === 0) return last;
      for (const row of rows) {
        n += 1;
        try {
          if (row.length !== 3) throw new Error("chain broken");
          const [seq, stored, text] = row;
          const e = strictParse(text);
          const claimed = e.digest; delete e.digest;
          if (e.prev !== last || digest(e) !== claimed || claimed !== stored) throw new Error("chain broken");
          last = claimed; after = seq;
        } catch (err) {
          if (err instanceof Refused && err.code === "unavailable") throw err;
          throw new Refused("unavailable", `the audit record is damaged at entry ${n}`);
        }
      }
    }
  }
}

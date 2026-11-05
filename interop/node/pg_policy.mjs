// pg_policy.mjs: the receiver's policy state in PostgreSQL, the Node twin of cns_interop/policy_postgres.py, over the same
// tables, so a Python and a Node receiver on different hosts share them. This is the RECEIVER's storage: CNS holds no
// authority here. Like pg.mjs it talks to PostgreSQL through the `psql` client (no npm dependency), and every answer that is
// not definite is Refused('unavailable'), never "not withdrawn".
//   * WITHDRAWALS (PostgresGrantStore): `<prefix>_withdrawn (grant_id text PRIMARY KEY, at bigint)`, the same `withdraw` /
//     `isWithdrawn` as grants.GrantStore, so a GrantTable takes it as its `store`. The withdrawal time is the DATABASE's.
import { NAME, NOW_MS, PgGuard } from "./pg.mjs";

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

"""ledger_postgres: a ledger whose truth lives in PostgreSQL, so several hosts share it.

WHAT IT GUARANTEES, AND WHAT IT NEEDS TO

  * One row per message `(sender, id)`. `reserve` and `spend` are a single `INSERT ... ON CONFLICT DO UPDATE ... WHERE`
    statement: the row lock makes it atomic, so of any number of concurrent callers on any number of hosts exactly one is
    granted. A lapsed lease is taken over by the same statement; a live lease or a committed message is `replayed`.
  * Time is the DATABASE's. Every lease is judged by the server's clock; the caller's clock is ignored unless a test
    stand-in is allowed to drive time (`allow_caller_time`). A host with a wrong clock cannot shorten anyone's lease.
  * Each grant draws a fence from a sequence, so it only ever grows (see fencing.FencedTarget).
  * Failure is refusal. A connection that cannot be made, a statement that times out (`statement_timeout`,
    `lock_timeout`, `tcp_user_timeout`), a dropped link, a server that is down or in recovery: `Refused("unavailable")`.
    An ambiguous commit (the server may have committed and the answer was lost) is also `unavailable`; the row may then be
    held until its lease lapses, which is the documented model (docs/interop/CONSISTENCY.md).

AND WHAT IT DOES NOT GUARANTEE BY ITSELF. A single PostgreSQL node is exactly as available and durable as that node.
Several hosts sharing it are safe from double redemption while it is up. HIGH AVAILABILITY needs a standby, and an
asynchronous standby can lose an acknowledged reservation on failover (measured with Redis in CONSISTENCY.md; PostgreSQL
behaves the same way). Pass `require_sync_replication=True` to make every write demand quorum-durable commit
(`synchronous_standby_names` set, `synchronous_commit` of `on` or stronger): the ledger then refuses to write unless the
server is configured that way, and a commit that the standby cannot confirm times out as `unavailable` instead of being
acknowledged. That is a configuration check plus a timeout; it is not a proof of the server's replication.

EXACTLY-ONCE EFFECTS. `commit_in(connection, reservation)` runs the commit on the CALLER's open transaction, so a business
write and the spend of the message happen together or not at all. That is the one place this ledger can support an
exactly-once effect; a target that is not in the same database gets at-least-once and the idempotency key.
"""

from __future__ import annotations

import re
import secrets
import threading
from typing import Any, Callable, Optional

from .envelope import Refused
from .ledger import Reservation, _check_lease

__all__ = ["PostgresLedger"]

_NAME = re.compile(r"\A[a-z_][a-z0-9_]{0,40}\Z")
_NOW_MS = "(extract(epoch from clock_timestamp()) * 1000)::bigint"


class PostgresLedger:
    def __init__(self, dsn: str, *, table: str = "uai_spent", keep_ms: int = 120_000, connect_timeout_s: int = 3,
                 statement_timeout_ms: int = 3_000, tcp_user_timeout_ms: int = 3_000,
                 require_sync_replication: bool = False, allow_caller_time: bool = False) -> None:
        try:
            import psycopg
        except ImportError:
            raise RuntimeError("PostgresLedger needs the optional extra: pip install 'cns[postgres]'") from None
        if not _NAME.match(table):
            raise ValueError("table is a lowercase SQL identifier")
        self._pg, self._dsn, self._t, self._keep = psycopg, dsn, table, keep_ms
        self._connect_kw: dict[str, Any] = {"connect_timeout": connect_timeout_s, "tcp_user_timeout": tcp_user_timeout_ms,
                            "options": f"-c statement_timeout={statement_timeout_ms} -c lock_timeout={statement_timeout_ms}"}
        self._sync, self._caller_time = require_sync_replication, allow_caller_time
        self._commit_wait_s = statement_timeout_ms / 1000.0
        self._guard(self._create)

    # ------------------------------------------------------------------------------------------------ plumbing
    def _connect(self) -> Any:
        return self._pg.connect(self._dsn, autocommit=False, **self._connect_kw)

    def _guard(self, fn: Callable[[Any], Any]) -> Any:
        """Run `fn(connection)` in one transaction. Anything that is not a definite answer is Refused('unavailable')."""
        try:
            with self._connect() as db:
                notices: list = []
                db.add_notice_handler(lambda n: notices.append(str(getattr(n, "message_primary", n))))
                if self._sync:
                    self._require_quorum(db)
                out = fn(db)
                # statement_timeout does NOT interrupt a COMMIT that is waiting for the standby (measured: the backend
                # stays in SyncRep past it), so a watchdog cancels the wait from outside. The server then answers the
                # commit with success plus a notice, which is checked below and refused.
                watchdog = threading.Timer(self._commit_wait_s, db.cancel)
                watchdog.daemon = True
                watchdog.start()
                try:
                    db.commit()
                finally:
                    watchdog.cancel()
                # PostgreSQL answers a COMMIT whose wait for the standby was cancelled (statement_timeout, a cancel) with
                # SUCCESS and a warning: the transaction is committed on THIS node and may not exist anywhere else. Taking
                # that as "granted" is the acknowledged-write-lost failure, so it is refused, and the row stays held.
                if any("synchronous replication" in n for n in notices):
                    raise Refused("unavailable", "the commit was not confirmed by the standby, so it is not treated as "
                                                 "granted (it may be held on this node until its lease lapses)")
                return out
        except Refused:
            raise
        except self._pg.Error as exc:
            raise Refused("unavailable", f"the ledger database did not give a definite answer ({type(exc).__name__})") from None
        except OSError as exc:
            raise Refused("unavailable", f"the ledger database is unreachable ({type(exc).__name__})") from None

    def _require_quorum(self, db: Any) -> None:
        names = db.execute("SHOW synchronous_standby_names").fetchone()[0]
        mode = db.execute("SHOW synchronous_commit").fetchone()[0]
        if not names or mode not in ("on", "remote_apply"):
            raise Refused("unavailable", "this ledger was told to require quorum-durable commits and the server is not "
                                         "configured for them (synchronous_standby_names and synchronous_commit)")
        db.execute("SET LOCAL synchronous_commit = 'remote_apply'")

    def _create(self, db: Any) -> None:
        db.execute("SELECT pg_advisory_xact_lock(7243001)")  # two hosts creating the table at once must not race
        db.execute(f"CREATE TABLE IF NOT EXISTS {self._t} (sender text NOT NULL, id text NOT NULL, state text NOT NULL "
                   "CHECK (state IN ('leased','committed')), token text, lease_until bigint, expires_at bigint, "
                   "fence bigint NOT NULL DEFAULT 0, PRIMARY KEY (sender, id))")
        db.execute(f"CREATE INDEX IF NOT EXISTS {self._t}_exp ON {self._t} (expires_at)")
        db.execute(f"CREATE SEQUENCE IF NOT EXISTS {self._t}_fence")

    def _time(self, now: Optional[int]) -> tuple:
        if self._caller_time and now is not None:
            return "%s", (now,)
        return _NOW_MS, ()

    # ------------------------------------------------------------------------------------------------ the ledger
    def _grant(self, db: Any, sender: str, message_id: str, expires_at: Optional[int], state: str, token: Optional[str],
               lease_ms: int, now: Optional[int]) -> Optional[tuple]:
        t_sql, t_args = self._time(now)
        db.execute(f"DELETE FROM {self._t} WHERE expires_at IS NOT NULL AND expires_at <= {t_sql} - %s",
                   (*t_args, self._keep))
        lease = f"{t_sql} + %s" if state == "leased" else "NULL"
        lease_args = (*t_args, lease_ms) if state == "leased" else ()
        row = db.execute(
            f"INSERT INTO {self._t} (sender, id, state, token, lease_until, expires_at, fence) "
            f"VALUES (%s, %s, %s, %s, {lease}, %s, nextval('{self._t}_fence')) "
            f"ON CONFLICT (sender, id) DO UPDATE SET state = EXCLUDED.state, token = EXCLUDED.token, "
            f"lease_until = EXCLUDED.lease_until, expires_at = EXCLUDED.expires_at, fence = EXCLUDED.fence "
            f"WHERE {self._t}.state = 'leased' AND {self._t}.lease_until <= {t_sql} "
            f"RETURNING fence, lease_until",
            (sender, message_id, state, token, *lease_args, expires_at, *t_args)).fetchone()
        return row

    def spend(self, sender: str, message_id: str, expires_at: Optional[int], *, now: Optional[int] = None) -> None:
        row = self._guard(lambda db: self._grant(db, sender, message_id, expires_at, "committed", None, 0, now))
        if row is None:
            raise Refused("replayed", "this message was already accepted once or is being redeemed right now")

    def reserve(self, sender: str, message_id: str, expires_at: Optional[int], *, lease_ms: int,
                now: Optional[int] = None) -> Reservation:
        lease, token = _check_lease(lease_ms), secrets.token_hex(16)
        row = self._guard(lambda db: self._grant(db, sender, message_id, expires_at, "leased", token, lease, now))
        if row is None:
            raise Refused("replayed", "this message was already accepted once or is being redeemed right now")
        return Reservation(sender, message_id, expires_at, token, int(row[1]), int(row[0]))

    def _commit_sql(self, db: Any, r: Reservation) -> None:
        done = db.execute(f"UPDATE {self._t} SET state = 'committed', token = NULL, lease_until = NULL "
                          "WHERE sender = %s AND id = %s AND token = %s RETURNING 1",
                          (r.sender, r.message_id, r.token)).fetchone()
        if done is None:  # nothing of ours: forgotten after expiry (spend it now) or taken by someone else
            added = db.execute(f"INSERT INTO {self._t} (sender, id, state, expires_at, fence) "
                               f"VALUES (%s, %s, 'committed', %s, 0) ON CONFLICT DO NOTHING RETURNING 1",
                               (r.sender, r.message_id, r.expires_at)).fetchone()
            if added is None:
                raise Refused("lease_lost", "the message was taken by another redemption after this lease lapsed")

    def commit(self, reservation: Reservation, *, now: Optional[int] = None) -> None:
        self._guard(lambda db: self._commit_sql(db, reservation))

    def commit_in(self, connection: Any, reservation: Reservation) -> None:
        """Spend the message on the CALLER's open transaction, so a business write and this commit are one atomic unit:
        both persist or neither does (a client that dies before COMMIT leaves the lease to lapse and the message
        redeemable). The caller commits, and against a synchronous standby the caller must bound that COMMIT itself the
        way `_guard` does (a cancel timer, and a refusal if the server reports the wait was cancelled). Errors surface as Refused, as everywhere else in this ledger."""
        try:
            self._commit_sql(connection, reservation)
        except Refused:
            raise
        except self._pg.Error as exc:
            raise Refused("unavailable", f"the ledger database did not give a definite answer ({type(exc).__name__})") from None

    def release(self, reservation: Reservation, *, now: Optional[int] = None) -> None:
        def run(db: Any) -> None:
            gone = db.execute(f"DELETE FROM {self._t} WHERE sender = %s AND id = %s AND token = %s RETURNING 1",
                              (reservation.sender, reservation.message_id, reservation.token)).fetchone()
            if gone is None:
                other = db.execute(f"SELECT 1 FROM {self._t} WHERE sender = %s AND id = %s",
                                   (reservation.sender, reservation.message_id)).fetchone()
                if other is not None:
                    raise Refused("lease_lost", "only the holder of a lease can release it")
        self._guard(run)

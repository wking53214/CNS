"""Node and Python share the receiver's policy state in PostgreSQL (withdrawals first), and their fencing checks agree.

A withdrawal written by one language is honoured by the other on the very next check, in both directions, through the
receiver's own grant check (GrantTable.check_terms / checkTerms) and not only through the store. A database outage is
`unavailable`, never "not withdrawn". The fencing check answers identically for the same sequence in both languages, and a
stale fence issued by one language's ledger is refused by the other language's target. One machine; separate processes stand in
for hosts. Not shown: a multi-host deployment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, List

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from pg_cluster import Cluster  # type: ignore[import-not-found]  # noqa: E402

from cns_interop.envelope import Refused  # noqa: E402
from cns_interop.fencing import FencedTarget  # noqa: E402
from cns_interop.grants import GrantTable, load_grants  # noqa: E402
from cns_interop.ledger_postgres import PostgresLedger  # noqa: E402
from cns_interop.policy_postgres import PostgresGrantStore  # noqa: E402

DRIVER = Path(__file__).parent / "node_policy_driver.mjs"
REQ = "uai:ed25519:" + "1" * 64
DEC = "uai:ed25519:" + "2" * 64
GRANTS = {"grants": [{"id": "g1", "capability": "pay", "version": 1, "requester": REQ, "deciders": [DEC], "actions": ["send"]}]}
TERMS = {"capability": "pay", "version": 1, "requester": REQ, "decider": DEC, "disclose": []}


@pytest.fixture(scope="module")
def cluster():
    c = Cluster().start()
    c.wait_ready()
    yield c
    c.cleanup()


def prefix() -> str:
    return "n_" + uuid.uuid4().hex[:10]


def node(dsn: str, pre: str, ops: List[list]) -> list:  # type: ignore[type-arg]
    exe = shutil.which("node")
    assert exe, "Node.js is not installed (need node 22 or later)"
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "POLICY_DSN": dsn}
    done = subprocess.run([exe, str(DRIVER)], input=json.dumps({"dsn_env": "POLICY_DSN", "prefix": pre, "ops": ops}),
                          capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)  # type: ignore[no-any-return]


def codes(results: list) -> list:  # type: ignore[type-arg]
    return [r.get("code", "ok") for r in results]


def py_check(store: Any) -> str:
    table = GrantTable(load_grants(json.dumps(GRANTS)), store=store)
    try:
        return table.check_terms(TERMS).id  # type: ignore[no-any-return]
    except Refused as exc:
        return exc.code  # type: ignore[no-any-return]


def test_a_withdrawal_written_by_python_is_honoured_by_node_on_the_next_check(cluster):
    pre = prefix()
    py = PostgresGrantStore(cluster.dsn, prefix=pre + "_policy")
    assert node(cluster.dsn, pre, [["check_terms", GRANTS, TERMS], ["is_withdrawn", "g1"]]) == [{"ok": "g1"}, {"ok": False}]
    py.withdraw("g1")
    assert node(cluster.dsn, pre, [["is_withdrawn", "g1"], ["check_terms", GRANTS, TERMS]])[0] == {"ok": True}
    assert codes(node(cluster.dsn, pre, [["check_terms", GRANTS, TERMS]])) == ["withdrawn"]


def test_a_withdrawal_written_by_node_is_honoured_by_python_on_the_next_check(cluster):
    pre = prefix()
    py = PostgresGrantStore(cluster.dsn, prefix=pre + "_policy")
    assert py_check(py) == "g1"
    assert node(cluster.dsn, pre, [["withdraw", "g1"], ["withdraw", "g1"]]) == [{"ok": True}, {"ok": True}]   # idempotent
    assert py.is_withdrawn("g1") is True and py_check(py) == "withdrawn"
    assert py.is_withdrawn("other") is False


def test_a_withdrawal_is_visible_immediately_in_both_directions_alternating(cluster):
    pre = prefix()
    py = PostgresGrantStore(cluster.dsn, prefix=pre + "_policy")
    for i in range(3):
        gid = f"g{i}"
        assert node(cluster.dsn, pre, [["is_withdrawn", gid]]) == [{"ok": False}] and not py.is_withdrawn(gid)
        (py.withdraw(gid) if i % 2 == 0 else node(cluster.dsn, pre, [["withdraw", gid]]))
        assert node(cluster.dsn, pre, [["is_withdrawn", gid]]) == [{"ok": True}] and py.is_withdrawn(gid)


def test_node_and_python_use_the_same_tables_and_the_withdrawal_time_is_the_databases(cluster):
    import psycopg
    pre = prefix()
    node(cluster.dsn, pre, [["withdraw", "g9"]])
    with psycopg.connect(cluster.dsn, autocommit=True) as db:
        at = db.execute(f"SELECT at FROM {pre}_policy_withdrawn WHERE grant_id = 'g9'").fetchone()[0]
        now = db.execute("SELECT (extract(epoch from clock_timestamp()) * 1000)::bigint").fetchone()[0]
    assert 0 <= now - at < 60_000


def test_an_unreachable_database_is_unavailable_never_not_withdrawn(cluster):
    dead = "host=127.0.0.1 port=1 user=postgres dbname=postgres"
    assert codes(node(dead, prefix(), [])) == ["unavailable"]
    with pytest.raises(Refused) as e:
        PostgresGrantStore(dead, prefix=prefix() + "_policy", connect_timeout_s=1)
    assert e.value.code == "unavailable"


def test_a_bad_prefix_is_a_caller_error_in_both(cluster):
    with pytest.raises(ValueError):
        PostgresGrantStore(cluster.dsn, prefix="x; DROP TABLE y")
    assert codes(node(cluster.dsn, "x; DROP TABLE y", [])) == ["config"]


FENCE_SEQUENCE = [["acct", 5], ["acct", 5], ["acct", 7], ["acct", 6], ["other", 1], ["acct", 7], ["acct", 0], ["acct", -1],
                  ["acct", 1.5], ["acct", True], ["acct", "9"], ["fresh", 0], ["acct", 8]]


def test_the_fencing_check_answers_identically_in_both_languages(cluster):
    target = FencedTarget()
    py: List[str] = []
    for resource, fence in FENCE_SEQUENCE:
        try:
            target.check(resource, fence)
            py.append("ok")
        except Refused as exc:
            py.append(exc.code)
    assert py == ["ok", "ok", "ok", "fenced", "ok", "ok", "fenced", "fenced", "fenced", "fenced", "fenced", "fenced", "ok"]
    assert codes(node(cluster.dsn, prefix(), [["fence", r, f] for r, f in FENCE_SEQUENCE])) == py
    lenient = FencedTarget(require_fence=False)
    lenient.check("x", 0)


def test_a_stale_fence_from_one_languages_ledger_is_refused_by_the_other_languages_target(cluster):
    from test_node_postgres import run as node_ledger  # type: ignore[import-not-found]
    S = "uai:ed25519:" + "c" * 64
    t = "t_" + uuid.uuid4().hex[:12]
    py = PostgresLedger(cluster.dsn, table=t)
    stale = py.reserve(S, "m", None, lease_ms=500)
    time.sleep(0.8)
    fresh = node_ledger(cluster.dsn, t, [["reserve", S, "m", None, 30000]])[0]["ok"]["fence"]
    assert 0 < stale.fence < fresh
    assert codes(node(cluster.dsn, prefix(), [["fence", "acct", fresh], ["fence", "acct", stale.fence]])) == ["ok", "fenced"]
    # and the other way: a fence Node issued is stale against a Python-issued one
    time.sleep(0.01)
    stale2 = node_ledger(cluster.dsn, t, [["reserve", S, "n", None, 500]])[0]["ok"]["fence"]
    time.sleep(0.8)
    fresh2 = py.reserve(S, "n", None, lease_ms=30000)
    target = FencedTarget()
    target.check("acct", fresh2.fence)
    with pytest.raises(Refused) as e:
        target.check("acct", stale2)
    assert e.value.code == "fenced"

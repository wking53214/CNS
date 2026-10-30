"""act.py: the process that performs an action, deciding on its own whether a remote decision permits it.

It is deliberately a separate program. Its own configuration comes from its command line, set by whoever deploys it:

    python interop/act.py --acting-for <identity> --capability <name> --capability-version <n>
                          --trust <decider identity>[,...] --ledger <shared ledger file>

The job comes on stdin, one JSON object, and can only narrow what is accepted, never widen it:

    {"decision": <decision envelope>, "terms": <the agreed terms>, "accept_digest": "<hex>",
     "artifact": ["<identity>", "<digest>"]}

The job is read with `cns_interop.wire.loads`, so a duplicate key, a float, NaN or Infinity, or a job that is not
one JSON object is refused before anything is verified. It prints {"permitted": true|false} or
{"refused": {"code": ..., "reason": ...}}. It holds no key and no secret,
shares no memory with whoever received the decision, and trusts nothing but the signature, its own list of
deciders, and its ledger. A decider the job names but this process does not trust is refused, and two runs against
the same ledger file permit at most one action, even though they are two processes.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Tuple

from cns_interop.decision import RemoteDecisionGuard
from cns_interop.envelope import Refused
from cns_interop.ledger import FileLedger
from cns_interop.trust import TrustPolicy
from cns_interop.wire import loads


def _identity_and_digest(artifact: object) -> Tuple[str, str]:
    if not isinstance(artifact, list) or len(artifact) != 2 or not all(isinstance(x, str) for x in artifact):
        raise ValueError("an artifact here is [identity, digest]")
    return artifact[0], artifact[1]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="act once on a remote UAI-1 decision")
    p.add_argument("--acting-for", required=True)
    p.add_argument("--capability", required=True, help="the capability this process acts on; others are refused")
    p.add_argument("--capability-version", required=True, type=int)
    p.add_argument("--trust", required=True, help="comma-separated decider identities this process accepts")
    p.add_argument("--ledger", required=True)
    cfg = p.parse_args(argv)
    stdin = sys.stdin.read()
    try:
        guard = RemoteDecisionGuard(_identity_and_digest, acting_for=cfg.acting_for,
                                    capability=(cfg.capability, cfg.capability_version),
                                    trust=TrustPolicy(pinned=frozenset(filter(None, cfg.trust.split(",")))),
                                    ledger=FileLedger(cfg.ledger))
    except ValueError as exc:
        print(json.dumps({"refused": {"code": "config", "reason": str(exc)}}))
        return 2
    try:
        job = loads(stdin)  # as strict as an envelope: a repeated key, a float or NaN, or over 1 MiB is refused
        guard.authorize(job["decision"], terms=job["terms"], accept_digest=job["accept_digest"])
    except Refused as exc:
        print(json.dumps({"refused": {"code": exc.code, "reason": exc.reason}}))
        return 0
    print(json.dumps({"permitted": guard(job["artifact"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""act.py: the process that performs an action, deciding on its own whether a remote decision permits it.

It is deliberately a separate program. It receives, on stdin, one JSON object:

    {"decision": <decision envelope>, "terms": <the agreed terms>, "accept_digest": "<hex>",
     "artifact": ["<identity>", "<digest>"], "ledger": "<path to a shared ledger file>"}

and prints {"permitted": true|false} or {"refused": {"code": ..., "reason": ...}}. It holds no key and no secret,
shares no memory with whoever received the decision, and trusts nothing but the signature, the terms and its ledger.
Two runs against the same ledger file permit at most one action, even though they are two processes.
"""

from __future__ import annotations

import json
import sys
from typing import Tuple

from cns_interop.decision import RemoteDecisionGuard
from cns_interop.envelope import Refused
from cns_interop.ledger import FileLedger


def _identity_and_digest(artifact: object) -> Tuple[str, str]:
    if not isinstance(artifact, list) or len(artifact) != 2 or not all(isinstance(x, str) for x in artifact):
        raise ValueError("an artifact here is [identity, digest]")
    return artifact[0], artifact[1]


def main() -> int:
    job = json.loads(sys.stdin.read())
    guard = RemoteDecisionGuard(_identity_and_digest, ledger=FileLedger(job["ledger"]))
    try:
        guard.authorize(job["decision"], terms=job["terms"], accept_digest=job["accept_digest"])
    except Refused as exc:
        print(json.dumps({"refused": {"code": exc.code, "reason": exc.reason}}))
        return 0
    print(json.dumps({"permitted": guard(job["artifact"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

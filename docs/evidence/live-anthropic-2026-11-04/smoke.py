"""Step 2 smoke call: one short request to claude-haiku-5-5 through cns_interop's own Anthropic client.

    UAI_ANTHROPIC_API_KEY=... python docs/evidence/live-anthropic-2026-11-04/smoke.py OUT.json

Reads the key from UAI_ANTHROPIC_API_KEY, else ANTHROPIC_API_KEY. Writes the answer and the provenance record (digests,
model as reported, latency, stop reason). The key is never written or printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cns_interop.providers import ProvenanceLog, anthropic_complete  # noqa: E402

PROMPT = "Reply with exactly the word OK and nothing else."


def main(out: str) -> int:
    key = next((v for v in (os.environ.get(n, "").strip() for n in ("UAI_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")) if v), "")
    if not key:
        print("NOT EXECUTED: set UAI_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY")
        return 3
    log = ProvenanceLog()
    complete = anthropic_complete(key, "claude-haiku-5-5", log, timeout_s=120.0, max_tokens=256)
    result = {"model": "claude-haiku-5-5", "prompt": PROMPT, "max_tokens": 256}
    try:
        result["answer"] = complete(PROMPT)
    except Exception as exc:
        result["refused"] = f"{getattr(exc, 'code', type(exc).__name__)}: {getattr(exc, 'reason', exc)}"[:300]
    result["provenance"] = [r.__dict__ for r in log.records]
    Path(out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: result.get(k) for k in ("answer", "refused")}))
    return 0 if result.get("answer") == "OK" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

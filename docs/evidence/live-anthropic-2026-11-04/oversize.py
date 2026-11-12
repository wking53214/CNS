"""Step 8: the response size cap against the real Anthropic API.

    UAI_ANTHROPIC_API_KEY=... python docs/evidence/live-anthropic-2026-11-04/oversize.py OUT.json

A real, ordinary answer from claude-haiku-5-5 is larger than a deliberately tiny max_response_bytes (64), so the client must
refuse it as too large and must not hand any of it on. A control call with the default cap shows the same prompt succeeds.
The key is read from UAI_ANTHROPIC_API_KEY, else ANTHROPIC_API_KEY, and is never written or printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cns_interop.providers import ProvenanceLog, anthropic_complete  # noqa: E402

PROMPT = "In one short sentence, what is a paystub?"


def run(key: str, **kw: Any) -> Dict[str, Any]:
    log = ProvenanceLog()
    complete = anthropic_complete(key, "claude-haiku-5-5", log, timeout_s=120.0, max_tokens=256, **kw)
    out: Dict[str, Any] = {"options": kw}
    try:
        out["returned"] = complete(PROMPT)
    except Exception as exc:
        out["refused"] = f"{getattr(exc, 'code', type(exc).__name__)}: {getattr(exc, 'reason', exc)}"[:300]
    out["provenance"] = [r.__dict__ for r in log.records]
    return out


def main(out_path: str) -> int:
    key = next((v for v in (os.environ.get(n, "").strip() for n in ("UAI_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")) if v), "")
    if not key:
        print("NOT EXECUTED: set UAI_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY")
        return 3
    results = {"prompt": PROMPT, "control_default_cap": run(key), "tiny_cap_64_bytes": run(key, max_response_bytes=64)}
    text = json.dumps(results, indent=1, sort_keys=True) + "\n"
    assert key not in text
    Path(out_path).write_text(text)
    tiny = results["tiny_cap_64_bytes"]
    ok = "returned" in results["control_default_cap"] and "returned" not in tiny and "larger than" in tiny.get("refused", "")
    print("control returned:", "returned" in results["control_default_cap"], "| tiny cap:", tiny.get("refused", "RETURNED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

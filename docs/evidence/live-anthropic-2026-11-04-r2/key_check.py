"""Step 2: confirm UAI_ANTHROPIC_API_KEY is set and non-empty without printing it, and write key_check.json.

    python docs/evidence/live-anthropic-2026-11-04-r2/key_check.py key_check.json

Only booleans are recorded: never the key, its length or any part of it. No request is sent, so this spends nothing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(out_path: str) -> int:
    raw = os.environ.get("UAI_ANTHROPIC_API_KEY")
    record = {"variable": "UAI_ANTHROPIC_API_KEY", "set": raw is not None, "non_empty": bool((raw or "").strip()),
              "had_surrounding_whitespace": raw is not None and raw != raw.strip()}
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    assert not raw or raw.strip() not in text
    Path(out_path).write_text(text)
    print(f"UAI_ANTHROPIC_API_KEY non_empty={record['non_empty']}")
    return 0 if record["non_empty"] else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

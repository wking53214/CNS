"""Step 3 checks against the real Anthropic API, through cns_interop's own client and strict reader.

    UAI_ANTHROPIC_API_KEY=... python docs/evidence/live-anthropic-2026-11-04/checks.py OUT.json

1. raw: the runner's exact prompt (render_prompt, income 512000) once per model, with the raw text kept, so the
   strict reader's refusals in live-*.json can be explained from what the model actually said.
2. malformed: real responses the client or the strict reader must refuse, never repair:
   a. max_tokens 16 on Opus: the answer stops at max_tokens and is refused as possibly cut off.
   b. a model name that does not exist: HTTP 404, refused.
   c. a key that is well formed but wrong: HTTP 401, refused, and the key is not in the record.
   d. a prompt asking for prose: a real end_turn answer the strict reader refuses as not one JSON object.
3. timeout: the runner's prompt to Opus with timeout_s 1.0 (Opus took over 7 seconds in the runner): refused as
   unreachable or timed out, recorded as a provider failure.

The key is read from UAI_ANTHROPIC_API_KEY, else ANTHROPIC_API_KEY, and is never written or printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cns_interop.adapter import parse_recommendation, render_prompt  # noqa: E402
from cns_interop.providers import ProvenanceLog, anthropic_complete  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "interop"))
from live_providers import CAP  # noqa: E402

MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
PROMPT = render_prompt(CAP, {"doc_type": "paystub", "monthly_income_cents": 512_000}, {"identity": "live-demo", "digest": "00" * 32})


def attempt(fn: Callable[[], Any]) -> Dict[str, Any]:
    try:
        return {"returned": fn()}
    except Exception as exc:
        return {"refused": f"{getattr(exc, 'code', type(exc).__name__)}: {getattr(exc, 'reason', exc)}"[:300]}


def one(key: str, model: str, prompt: str, *, strict: bool, **kw: Any) -> Dict[str, Any]:
    log = ProvenanceLog()
    complete = anthropic_complete(key, model, log, **{"timeout_s": 120.0, **kw})
    out: Dict[str, Any] = {"model": model, **{k: v for k, v in kw.items()}}
    got = attempt(lambda: complete(prompt))
    if "returned" in got:
        out["raw_text"] = got["returned"]
        if strict:
            parsed = attempt(lambda: parse_recommendation(got["returned"], CAP).verdict)
            out["strict_reader"] = {"verdict": parsed["returned"]} if "returned" in parsed else parsed
    else:
        out["client"] = got
    out["provenance"] = [r.__dict__ for r in log.records]
    return out


def main(out_path: str) -> int:
    key = next((v for v in (os.environ.get(n, "").strip() for n in ("UAI_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")) if v), "")
    if not key:
        print("NOT EXECUTED: set UAI_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY")
        return 3
    wrong = "sk-ant-api03-" + "x" * 95
    results: Dict[str, Any] = {
        "prompt": PROMPT,
        "raw": [one(key, m, PROMPT, strict=True) for m in MODELS],
        "malformed": {
            "a_max_tokens_16": one(key, "claude-opus-5-5", PROMPT, strict=True, max_tokens=16),
            "b_unknown_model": one(key, "claude-no-such-model-0", PROMPT, strict=True),
            "c_wrong_key": one(wrong, "claude-haiku-5-5", PROMPT, strict=True),
            "d_prose_answer": one(key, "claude-haiku-5-5", "In one short sentence, what is a paystub?", strict=True,
                                  max_tokens=256),
        },
        "timeout": one(key, "claude-opus-5-5", PROMPT, strict=True, timeout_s=1.0),
    }
    text = json.dumps(results, indent=1, sort_keys=True) + "\n"
    assert key not in text and wrong not in text
    Path(out_path).write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

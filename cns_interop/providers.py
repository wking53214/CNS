"""providers: real model providers behind the provider-neutral adapter contract (adapter.py), on the standard library.

Two ecosystems, so nothing in UAI-1 depends on either: Anthropic (Messages API) and Google (Gemini generateContent). Each is
only a `complete(prompt) -> text` function handed to `adapter.PromptedModelAdapter`; everything else (strict reading of the
output, the decider's policy, grants, approval) is unchanged, and none of it is given a key, a signer or an authority.

WHAT THIS MODULE DOES
  * bounded: a connect and read timeout, a response size cap, no redirects followed (a redirect would carry the key elsewhere)
  * strict: the provider's own envelope is read exactly (one text block / one candidate that finished normally); anything else
    is refused as `provider` with a reason: an HTTP error, a rate limit, a truncated or filtered answer, a missing or extra shape
  * provenance: every call records the provider, the model asked for and the model the provider reported, the digests of the
    exact request and response, the latency, why it finished, and whether the output was accepted or rejected and why
  * keys: held in the closure only; never in an exception, a record or a log line

WHAT IT IS NOT. Nothing here treats a model's confidence, a stated approval or a claimed authority as anything: the strict
parser refuses any key beyond verdict, reasons, evidence and escalate. A model recommends; the decider's policy decides; a grant
permits; a person approves.

HONESTY ABOUT WHAT HAS BEEN EXECUTED. The tests run these clients against local servers that speak each provider's wire format
(labeled STUB in the tests). That checks this code's handling of the protocol, not any provider. A live call needs a key
(`interop/live_providers.py`), prints NOT EXECUTED without one, and is the only thing that may set `ProviderInfo.live`.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .envelope import Refused

__all__ = ["Provenance", "ProvenanceLog", "anthropic_complete", "gemini_complete", "MAX_RESPONSE_BYTES"]

MAX_RESPONSE_BYTES = 262_144


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Provenance:
    provider: str
    model_requested: str
    model_reported: str = ""
    request_sha256: str = ""
    response_sha256: str = ""
    latency_ms: int = 0
    finish_reason: str = ""
    call: str = "not-made"      # ok, or why no usable answer came back
    outcome: str = "pending"    # accepted or rejected (by the adapter's strict reading and the decider's policy)
    reason: str = ""


class ProvenanceLog:
    """What was requested, returned, accepted and rejected, in order. In memory, and appended as JSON lines to `path` if given."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.records: List[Provenance] = []
        self._path = path

    def add(self, rec: Provenance) -> Provenance:
        self.records.append(rec)
        return rec

    def settle(self, rec: Provenance, outcome: str, reason: str = "") -> None:
        if rec.outcome != "pending":
            return  # settled once: a provider failure is not rewritten when the adapter reports it again
        rec.outcome, rec.reason = outcome, reason
        if self._path:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(rec), sort_keys=True) + "\n")

    def observer(self) -> Callable[[Any, Any, Any, Optional[Exception]], None]:
        """For `AdapterJudge(observer=...)`: settles the most recent call as accepted or rejected, with the reason."""
        def observe(raw: Any, rec: Any, judgment: Any, error: Optional[Exception]) -> None:
            if not self.records:
                return
            last = self.records[-1]
            if error is not None:
                self.settle(last, "rejected", getattr(error, "code", type(error).__name__) + ": " + str(getattr(error, "reason", error))[:160])
            else:
                self.settle(last, "accepted", f"verdict {judgment.verdict}" if judgment is not None else "")
        return observe


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a: Any, **k: Any) -> None:
        return None


def _post(url: str, headers: Dict[str, str], body: Dict[str, Any], timeout_s: float, max_bytes: int) -> Tuple[int, bytes]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "content-type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=timeout_s) as resp:
            raw = resp.read(max_bytes + 1)
            return int(resp.status), raw
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(2048)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise Refused("provider", f"the provider could not be reached or timed out ({type(reason).__name__})") from None


def _read_json(status: int, raw: bytes, max_bytes: int) -> Dict[str, Any]:
    if len(raw) > max_bytes:
        raise Refused("provider", f"the provider's answer is larger than {max_bytes} bytes")
    if status == 429:
        raise Refused("provider", "the provider is rate limiting this caller (HTTP 429)")
    if not 200 <= status < 300:
        raise Refused("provider", f"the provider answered HTTP {status}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise Refused("provider", "the provider's answer is not JSON") from None
    if not isinstance(value, dict):
        raise Refused("provider", "the provider's answer is not a JSON object")
    return value


def _client(name: str, model: str, log: ProvenanceLog, call: Callable[[str, Provenance], str]) -> Callable[[str], str]:
    def complete(prompt: str) -> str:
        rec = log.add(Provenance(provider=name, model_requested=model))
        started = time.perf_counter()
        try:
            text = call(prompt, rec)
            rec.call = "ok"
            return text
        except Refused as exc:
            rec.call = exc.reason[:160]
            log.settle(rec, "rejected", f"provider: {exc.reason}"[:200])
            raise
        finally:
            rec.latency_ms = int((time.perf_counter() - started) * 1000)
    return complete


def anthropic_complete(api_key: str, model: str, log: ProvenanceLog, *, base_url: str = "https://api.anthropic.com",
                       timeout_s: float = 30.0, max_tokens: int = 512,
                       max_response_bytes: int = MAX_RESPONSE_BYTES) -> Callable[[str], str]:
    """`complete(prompt)` over the Anthropic Messages API. The key lives only in this closure."""
    if not api_key or not model:
        raise ValueError("an API key and a model name are needed")

    def call(prompt: str, rec: Provenance) -> str:
        body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
        rec.request_sha256 = _digest(json.dumps(body, sort_keys=True).encode())
        status, raw = _post(base_url.rstrip("/") + "/v1/messages",
                            {"x-api-key": api_key, "anthropic-version": "2023-06-01"}, body, timeout_s, max_response_bytes)
        rec.response_sha256 = _digest(raw[:max_response_bytes])
        out = _read_json(status, raw, max_response_bytes)
        rec.model_reported, rec.finish_reason = str(out.get("model", "")), str(out.get("stop_reason", ""))
        blocks = out.get("content")
        if rec.finish_reason != "end_turn":
            raise Refused("provider", f"the answer did not end normally (stop_reason {rec.finish_reason!r}): it may be cut off")
        if not isinstance(blocks, list) or len(blocks) != 1 or not isinstance(blocks[0], dict) or blocks[0].get("type") != "text" \
                or not isinstance(blocks[0].get("text"), str):
            raise Refused("provider", "the answer is not exactly one text block")
        return str(blocks[0]["text"])
    return _client("anthropic", model, log, call)


def gemini_complete(api_key: str, model: str, log: ProvenanceLog, *, base_url: str = "https://generativelanguage.googleapis.com",
                    timeout_s: float = 30.0, max_response_bytes: int = MAX_RESPONSE_BYTES) -> Callable[[str], str]:
    """`complete(prompt)` over Google's Gemini generateContent. The key is sent in a header, never in the URL."""
    if not api_key or not model or "/" in model or "?" in model:
        raise ValueError("an API key and a plain model name are needed")

    def call(prompt: str, rec: Provenance) -> str:
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        rec.request_sha256 = _digest(json.dumps(body, sort_keys=True).encode())
        url = f"{base_url.rstrip('/')}/v1beta/models/{urllib.parse.quote(model)}:generateContent"
        status, raw = _post(url, {"x-goog-api-key": api_key}, body, timeout_s, max_response_bytes)
        rec.response_sha256 = _digest(raw[:max_response_bytes])
        out = _read_json(status, raw, max_response_bytes)
        rec.model_reported = str(out.get("modelVersion", ""))
        cands = out.get("candidates")
        if not isinstance(cands, list) or len(cands) != 1 or not isinstance(cands[0], dict):
            raise Refused("provider", "the answer is not exactly one candidate (a blocked prompt returns none)")
        rec.finish_reason = str(cands[0].get("finishReason", ""))
        if rec.finish_reason != "STOP":
            raise Refused("provider", f"the answer did not finish normally (finishReason {rec.finish_reason!r})")
        parts = (cands[0].get("content") or {}).get("parts") if isinstance(cands[0].get("content"), dict) else None
        if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], dict) or not isinstance(parts[0].get("text"), str):
            raise Refused("provider", "the answer is not exactly one text part")
        return str(parts[0]["text"])
    return _client("google", model, log, call)

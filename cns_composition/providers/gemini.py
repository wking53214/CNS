"""Google Gemini (generateContent) adapter for the provider-neutral model protocol.

Standard library only. One synchronous request, no retries. The key travels in the
`x-goog-api-key` header, never in the URL, so it cannot land in a logged address.
"""

from __future__ import annotations

import urllib.parse

from ._http import ProviderError, Transport, check_https, check_key, default_transport, post_json
from .protocol import CompletionStatus, ModelProvider, ModelRequest, ModelResponse, TokenUsage

__all__ = ["GeminiProvider"]

_SETTINGS = {"temperature": "temperature", "top_p": "topP", "top_k": "topK"}
_STATUS = {"STOP": CompletionStatus.COMPLETE, "MAX_TOKENS": CompletionStatus.MAX_TOKENS}


class GeminiProvider(ModelProvider):
    def __init__(self, api_key: str, *, base_url: str = "https://generativelanguage.googleapis.com/v1beta",
                 timeout_s: float = 45.0, transport: Transport = default_transport) -> None:
        check_key("gemini", api_key)
        check_https("gemini", base_url)
        self._key, self._base, self._timeout, self._transport = api_key, base_url.rstrip("/"), timeout_s, transport

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("request must be a ModelRequest")
        extra = sorted(set(request.generation_settings) - set(_SETTINGS))
        if extra:
            raise ProviderError("gemini", "unsupported_feature", "unsupported generation setting(s): " + ", ".join(extra))
        config: dict[str, object] = {"maxOutputTokens": request.max_output_tokens}
        config.update({_SETTINGS[k]: v for k, v in request.generation_settings.items() if v is not None})
        body: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": m}]} for m in request.user_messages],
            "generationConfig": config,
        }
        if request.system_instruction:
            body["systemInstruction"] = {"parts": [{"text": request.system_instruction}]}
        model = request.model[len("models/"):] if request.model.startswith("models/") else request.model
        url = f"{self._base}/models/{urllib.parse.quote(model, safe='')}:generateContent"
        out = post_json("gemini", self._transport, url, {"x-goog-api-key": self._key}, body, self._timeout)
        return _normalize(out, request.model)


def _normalize(out: object, requested: str) -> ModelResponse:
    try:
        candidates = out["candidates"]  # type: ignore[index]
        if len(candidates) != 1:
            raise ValueError
        parts = candidates[0]["content"]["parts"]
        if any(set(p) != {"text"} or not isinstance(p["text"], str) for p in parts):
            raise ValueError
        usage = out.get("usageMetadata")  # type: ignore[attr-defined]
        tokens = (TokenUsage(usage["promptTokenCount"], usage.get("candidatesTokenCount", 0))
                  if isinstance(usage, dict) else None)
        rid = out.get("responseId")  # type: ignore[attr-defined]
        model = out.get("modelVersion") or requested  # type: ignore[attr-defined]
        return ModelResponse(content="".join(p["text"] for p in parts), provider="gemini", model=model,
                             completion_status=_STATUS.get(candidates[0].get("finishReason"), CompletionStatus.UNKNOWN),
                             usage=tokens, request_id=rid if isinstance(rid, str) and rid.strip() else None,
                             native_response=out)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise ProviderError("gemini", "invalid_response", "unexpected response structure") from None

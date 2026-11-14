"""Groq adapter (OpenAI-compatible Chat Completions) for the provider-neutral model protocol.

Standard library only. One synchronous request, no retries. The API key is passed in
by the caller and is never stored in a log or an error.
"""

from __future__ import annotations

from ._http import ProviderError, Transport, check_https, check_key, default_transport, post_json
from .protocol import CompletionStatus, ModelProvider, ModelRequest, ModelResponse, TokenUsage

__all__ = ["GroqProvider"]

_ALLOWED = {"temperature", "top_p"}
_STATUS = {"stop": CompletionStatus.COMPLETE, "length": CompletionStatus.MAX_TOKENS}


class GroqProvider(ModelProvider):
    def __init__(self, api_key: str, *, base_url: str = "https://api.groq.com/openai/v1",
                 timeout_s: float = 30.0, transport: Transport = default_transport) -> None:
        check_key("groq", api_key)
        check_https("groq", base_url)
        self._key, self._base, self._timeout, self._transport = api_key, base_url.rstrip("/"), timeout_s, transport

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("request must be a ModelRequest")
        extra = sorted(set(request.generation_settings) - _ALLOWED)
        if extra:
            raise ProviderError("groq", "unsupported_feature", "unsupported generation setting(s): " + ", ".join(extra))
        messages = [{"role": "system", "content": request.system_instruction}] if request.system_instruction else []
        messages += [{"role": "user", "content": m} for m in request.user_messages]
        body: dict[str, object] = {"model": request.model, "messages": messages, "max_tokens": request.max_output_tokens}
        body.update({k: v for k, v in request.generation_settings.items() if v is not None})
        out = post_json("groq", self._transport, self._base + "/chat/completions",
                        {"authorization": "Bearer " + self._key}, body, self._timeout)
        return _normalize(out, request.model)


def _normalize(out: object, requested: str) -> ModelResponse:
    try:
        choices = out["choices"]  # type: ignore[index]
        if len(choices) != 1:
            raise ValueError
        message = choices[0]["message"]
        content = message["content"]
        if not isinstance(content, str) or message.get("tool_calls"):
            raise ValueError
        reason = choices[0].get("finish_reason")
        usage = out.get("usage")  # type: ignore[attr-defined]
        tokens = TokenUsage(usage["prompt_tokens"], usage["completion_tokens"]) if isinstance(usage, dict) else None
        rid = out.get("id")  # type: ignore[attr-defined]
        model = out.get("model") or requested  # type: ignore[attr-defined]
        return ModelResponse(content=content, provider="groq", model=model,
                             completion_status=_STATUS.get(reason, CompletionStatus.UNKNOWN), usage=tokens,
                             request_id=rid if isinstance(rid, str) and rid.strip() else None, native_response=out)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise ProviderError("groq", "invalid_response", "unexpected response structure") from None

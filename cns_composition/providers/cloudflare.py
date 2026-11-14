"""Cloudflare Workers AI adapter for the provider-neutral model protocol.

Standard library only. One synchronous request, no retries. Older catalog models
answer `{"result": {"response": text}}` and do not say why generation ended, so the
completion status is UNKNOWN for them. Newer models answer in the Chat Completions
shape, whose `finish_reason` is read. The account id is the caller's own.
"""

from __future__ import annotations

import urllib.parse

from ._http import ProviderError, Transport, check_https, check_key, default_transport, post_json
from .protocol import CompletionStatus, ModelProvider, ModelRequest, ModelResponse, TokenUsage

__all__ = ["CloudflareProvider"]

_STATUS = {"stop": CompletionStatus.COMPLETE, "length": CompletionStatus.MAX_TOKENS}


class CloudflareProvider(ModelProvider):
    def __init__(self, api_token: str, account_id: str, *, base_url: str = "https://api.cloudflare.com/client/v4",
                 timeout_s: float = 45.0, transport: Transport = default_transport) -> None:
        check_key("cloudflare", api_token)
        check_https("cloudflare", base_url)
        if not isinstance(account_id, str) or not account_id.isalnum():
            raise ValueError("cloudflare: an account id of letters and digits is needed")
        self._key, self._acct, self._base = api_token, account_id, base_url.rstrip("/")
        self._timeout, self._transport = timeout_s, transport

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("request must be a ModelRequest")
        if "?" in request.model or "#" in request.model or ".." in request.model:
            raise ValueError("cloudflare: a plain model name is needed")
        extra = sorted(set(request.generation_settings) - {"temperature", "top_p", "top_k"})
        if extra:
            raise ProviderError("cloudflare", "unsupported_feature",
                                "unsupported generation setting(s): " + ", ".join(extra))
        messages = [{"role": "system", "content": request.system_instruction}] if request.system_instruction else []
        messages += [{"role": "user", "content": m} for m in request.user_messages]
        body: dict[str, object] = {"messages": messages, "max_tokens": request.max_output_tokens}
        body.update({k: v for k, v in request.generation_settings.items() if v is not None})
        url = f"{self._base}/accounts/{self._acct}/ai/run/{urllib.parse.quote(request.model, safe='/@')}"
        out = post_json("cloudflare", self._transport, url, {"authorization": "Bearer " + self._key}, body, self._timeout)
        return _normalize(out, request.model)


def _normalize(out: object, requested: str) -> ModelResponse:
    try:
        if out.get("success") is False:  # type: ignore[attr-defined]
            raise ValueError
        result = out["result"]  # type: ignore[index]
        status = CompletionStatus.UNKNOWN
        if "choices" in result:
            if len(result["choices"]) != 1:
                raise ValueError
            choice = result["choices"][0]
            content = choice["message"]["content"]
            status = _STATUS.get(choice.get("finish_reason"), CompletionStatus.UNKNOWN)
        else:
            content = result["response"]
        if not isinstance(content, str):
            raise ValueError
        usage = result.get("usage")
        tokens = TokenUsage(usage["prompt_tokens"], usage["completion_tokens"]) if isinstance(usage, dict) else None
        return ModelResponse(content=content, provider="cloudflare", model=requested, completion_status=status,
                             usage=tokens, native_response=out)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise ProviderError("cloudflare", "invalid_response", "unexpected response structure") from None

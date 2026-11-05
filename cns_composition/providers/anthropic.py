"""Anthropic Messages API adapter for the provider-neutral model protocol.

Install the official `anthropic` Python SDK separately to use this module. This
adapter performs one synchronous request and does not implement retries. The
injected SDK client controls retry behavior.
"""

from __future__ import annotations

from typing import Any

import anthropic

from .protocol import CompletionStatus, ModelProvider, ModelRequest, ModelResponse, TokenUsage

__all__ = [
    "AnthropicProvider", "AnthropicProviderError", "AnthropicAuthenticationError",
    "AnthropicPermissionDeniedError",
    "AnthropicRateLimitError", "AnthropicConnectionError", "AnthropicTimeoutError",
    "AnthropicInvalidRequestError", "AnthropicServerError", "AnthropicResponseError",
    "UnsupportedAnthropicFeatureError",
]


class AnthropicProviderError(Exception):
    """Base class for sanitized Anthropic adapter failures."""

    category = "provider_error"

    def __init__(self, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id


class AnthropicAuthenticationError(AnthropicProviderError):
    category = "authentication"


class AnthropicPermissionDeniedError(AnthropicProviderError):
    category = "permission_denied"


class AnthropicRateLimitError(AnthropicProviderError):
    category = "rate_limit"


class AnthropicConnectionError(AnthropicProviderError):
    category = "connection"


class AnthropicTimeoutError(AnthropicProviderError):
    category = "timeout"


class AnthropicInvalidRequestError(AnthropicProviderError):
    category = "invalid_request"


class AnthropicServerError(AnthropicProviderError):
    category = "server"


class AnthropicResponseError(AnthropicProviderError):
    category = "invalid_response"


class UnsupportedAnthropicFeatureError(AnthropicProviderError):
    category = "unsupported_feature"


class AnthropicProvider(ModelProvider):
    """Use an injected official SDK client to implement `ModelProvider`."""

    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(getattr(client, "messages", None), "create", None)):
            raise TypeError("client must expose a callable messages.create method")
        self._client = client

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise TypeError("request must be a ModelRequest")
        params = self._request_params(request)
        try:
            native = self._client.messages.create(**params)
        except anthropic.APITimeoutError:
            raise AnthropicTimeoutError("Anthropic request timed out") from None
        except anthropic.AuthenticationError as error:
            raise AnthropicAuthenticationError(
                "Anthropic authentication failed", _safe_request_id(error)
            ) from None
        except anthropic.PermissionDeniedError as error:
            raise AnthropicPermissionDeniedError(
                "Anthropic denied permission for the request", _safe_request_id(error)
            ) from None
        except anthropic.RateLimitError as error:
            raise AnthropicRateLimitError("Anthropic rate limit reached", _safe_request_id(error)) from None
        except anthropic.APIConnectionError:
            raise AnthropicConnectionError("Could not connect to Anthropic") from None
        except anthropic.BadRequestError as error:
            raise AnthropicInvalidRequestError("Anthropic rejected the request", _safe_request_id(error)) from None
        except anthropic.InternalServerError as error:
            raise AnthropicServerError("Anthropic reported a server error", _safe_request_id(error)) from None
        except anthropic.APIStatusError as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            request_id = _safe_request_id(error)
            if isinstance(status, int) and status >= 500:
                raise AnthropicServerError("Anthropic reported a server error", request_id) from None
            raise AnthropicProviderError("Anthropic returned an unsuccessful status", request_id) from None
        except anthropic.APIError:
            raise AnthropicProviderError("Anthropic SDK request failed") from None
        return _normalize_response(native)

    @staticmethod
    def _request_params(request: ModelRequest) -> dict[str, object]:
        params: dict[str, object] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": "user", "content": message}
                          for message in request.user_messages],
        }
        if request.system_instruction:
            params["system"] = request.system_instruction
        allowed = {"temperature", "top_p", "top_k"}
        unsupported = sorted(set(request.generation_settings) - allowed)
        if unsupported:
            raise UnsupportedAnthropicFeatureError(
                "Unsupported generation setting(s): " + ", ".join(unsupported)
            )
        for key, value in request.generation_settings.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise UnsupportedAnthropicFeatureError(
                    f"Generation setting {key!r} must be numeric for Anthropic"
                )
            if key in ("temperature", "top_p") and not isinstance(value, float):
                value = float(value)
            if key == "top_k" and not isinstance(value, int):
                raise UnsupportedAnthropicFeatureError("Generation setting top_k must be an integer")
            params[key] = value
        return params


def _safe_request_id(error: BaseException) -> str | None:
    """Return only the SDK request id, never exception text or headers."""
    value = getattr(error, "request_id", None)
    if not isinstance(value, str) or not value.strip():
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        getter = getattr(headers, "get", None)
        value = getter("request-id") if callable(getter) else None
    return value if isinstance(value, str) and value.strip() else None


def _normalize_response(native: object) -> ModelResponse:
    """Validate and normalize the supported text response while retaining native data."""
    if not _has(native, "content", "model", "stop_reason", "usage"):
        raise AnthropicResponseError("Anthropic returned an unexpected response structure")
    blocks = getattr(native, "content")
    if not isinstance(blocks, (list, tuple)):
        raise AnthropicResponseError("Anthropic response content was not a sequence")
    text_parts: list[str] = []
    for block in blocks:
        if not _has(block, "type"):
            raise AnthropicResponseError("Anthropic response contained an unrecognized content block")
        block_type = getattr(block, "type")
        if block_type != "text" or not _has(block, "text") or not isinstance(getattr(block, "text"), str):
            raise UnsupportedAnthropicFeatureError(
                f"Anthropic response content block {block_type!r} is not supported by the text contract"
            )
        text_parts.append(getattr(block, "text"))
    model = getattr(native, "model")
    stop_reason = getattr(native, "stop_reason")
    if not isinstance(model, str) or not model.strip():
        raise AnthropicResponseError("Anthropic response omitted a valid model identifier")
    status = {
        "end_turn": CompletionStatus.COMPLETE,
        "max_tokens": CompletionStatus.MAX_TOKENS,
        "stop_sequence": CompletionStatus.STOPPED,
    }.get(stop_reason, CompletionStatus.UNKNOWN)
    usage_data = getattr(native, "usage")
    usage: TokenUsage | None = None
    if usage_data is not None:
        if not _has(usage_data, "input_tokens", "output_tokens"):
            raise AnthropicResponseError("Anthropic response usage had an unexpected structure")
        input_tokens = getattr(usage_data, "input_tokens")
        output_tokens = getattr(usage_data, "output_tokens")
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0
               for v in (input_tokens, output_tokens)):
            raise AnthropicResponseError("Anthropic response usage contained invalid token counts")
        usage = TokenUsage(input_tokens, output_tokens)
    request_id = getattr(native, "_request_id", None)
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = None
    return ModelResponse(
        content="".join(text_parts), provider="anthropic", model=model,
        completion_status=status, usage=usage, request_id=request_id, native_response=native,
    )


def _has(value: object, *names: str) -> bool:
    return all(hasattr(value, name) for name in names)

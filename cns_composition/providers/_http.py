"""Shared stdlib HTTPS transport and sanitized errors for the REST provider adapters.

Used by the Groq, Gemini and Cloudflare adapters. It makes one request and does
not retry. Error text never carries the key, a header or a response body.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Tuple

__all__ = ["ProviderError", "Transport", "default_transport", "post_json", "check_https", "check_key"]

MAX_RESPONSE_BYTES = 1_000_000

# (url, headers, body, timeout_s) -> (status, response bytes, response headers)
Transport = Callable[[str, Mapping[str, str], bytes, float], Tuple[int, bytes, Mapping[str, str]]]


class ProviderError(Exception):
    """A sanitized failure from a REST provider adapter. `category` names the kind."""

    def __init__(self, provider: str, category: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.category = category
        self.status = status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def check_https(provider: str, url: str) -> None:
    if not url.startswith("https://"):
        raise ValueError(f"{provider}: base_url must be https")


def check_key(provider: str, key: str) -> None:
    if not isinstance(key, str) or not key.strip() or any(c in key for c in "\r\n \t"):
        raise ValueError(f"{provider}: an API key without whitespace is needed")


def default_transport(url: str, headers: Mapping[str, str], body: bytes, timeout_s: float) -> Tuple[int, bytes, Mapping[str, str]]:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310 (https checked)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout_s) as response:  # nosec B310
            return response.status, response.read(MAX_RESPONSE_BYTES + 1), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_RESPONSE_BYTES + 1), dict(error.headers)


def post_json(provider: str, transport: Transport, url: str, headers: Mapping[str, str],
              body: Mapping[str, Any], timeout_s: float) -> Any:
    """POST a JSON body and return the parsed JSON object, or raise a sanitized `ProviderError`."""
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    try:
        status, raw, _ = transport(url, {**headers, "content-type": "application/json"}, payload, timeout_s)
    except TimeoutError:
        raise ProviderError(provider, "timeout", "request timed out") from None
    except OSError:
        raise ProviderError(provider, "connection", "could not connect") from None
    if status in (401, 403):
        raise ProviderError(provider, "authentication", "authentication failed", status)
    if status == 429:
        raise ProviderError(provider, "rate_limit", "rate limit reached", status)
    if status >= 500:
        raise ProviderError(provider, "server", "server error", status)
    if status != 200:
        raise ProviderError(provider, "invalid_request", "request rejected", status)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError(provider, "invalid_response", "response too large", status)
    try:
        return json.loads(raw)
    except ValueError:
        raise ProviderError(provider, "invalid_response", "response was not JSON", status) from None

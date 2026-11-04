"""Mocked-client coverage for the Anthropic provider adapter."""

import importlib
from types import SimpleNamespace

import pytest

anthropic = pytest.importorskip(
    "anthropic", reason="install the anthropic extra to run adapter tests"
)
httpx = importlib.import_module("httpx")

_adapter = importlib.import_module("cns_composition.providers.anthropic")
_protocol = importlib.import_module("cns_composition.providers.protocol")

AnthropicAuthenticationError = _adapter.AnthropicAuthenticationError
AnthropicConnectionError = _adapter.AnthropicConnectionError
AnthropicInvalidRequestError = _adapter.AnthropicInvalidRequestError
AnthropicPermissionDeniedError = _adapter.AnthropicPermissionDeniedError
AnthropicProvider = _adapter.AnthropicProvider
AnthropicProviderError = _adapter.AnthropicProviderError
AnthropicRateLimitError = _adapter.AnthropicRateLimitError
AnthropicResponseError = _adapter.AnthropicResponseError
AnthropicServerError = _adapter.AnthropicServerError
AnthropicTimeoutError = _adapter.AnthropicTimeoutError
UnsupportedAnthropicFeatureError = _adapter.UnsupportedAnthropicFeatureError

CompletionStatus = _protocol.CompletionStatus
ModelProvider = _protocol.ModelProvider
ModelRequest = _protocol.ModelRequest
ModelResponse = _protocol.ModelResponse
TokenUsage = _protocol.TokenUsage

def make_request(**changes):
    values = {"model": "claude-example", "system_instruction": "Be brief",
              "user_messages": ("Hi", "Again"), "max_output_tokens": 90,
              "generation_settings": {"temperature": 0.4, "top_p": 0.8, "top_k": 20}}
    values.update(changes)
    return ModelRequest(**values)


def make_response(**changes):
    values = {"content": [SimpleNamespace(type="text", text="Hello"),
                             SimpleNamespace(type="text", text=" there")],
              "model": "claude-returned-model", "stop_reason": "end_turn",
              "usage": SimpleNamespace(input_tokens=7, output_tokens=4),
              "_request_id": "req_abc"}
    values.update(changes)
    return SimpleNamespace(**values)


class FakeMessages:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, result=None, error=None):
        self.messages = FakeMessages(result, error)


def test_request_mapping_and_protocol_compatibility():
    client = FakeClient(make_response())
    provider = AnthropicProvider(client)
    assert isinstance(provider, ModelProvider)
    result = provider.generate(make_request())
    sent = client.messages.calls[0]
    assert sent == {"model": "claude-example", "max_tokens": 90,
                    "messages": [{"role": "user", "content": "Hi"},
                                 {"role": "user", "content": "Again"}],
                    "system": "Be brief", "temperature": 0.4, "top_p": 0.8, "top_k": 20}
    assert isinstance(result, ModelResponse)


def test_response_normalization_native_retention_usage_id_model_and_status():
    native = make_response()
    result = AnthropicProvider(FakeClient(native)).generate(make_request())
    assert result.content == "Hello there"
    assert result.provider == "anthropic" and result.model == "claude-returned-model"
    assert result.completion_status is CompletionStatus.COMPLETE
    assert result.usage == TokenUsage(7, 4) and result.request_id == "req_abc"
    assert result.native_response is native


@pytest.mark.parametrize("reason, expected", [
    ("max_tokens", CompletionStatus.MAX_TOKENS),
    ("stop_sequence", CompletionStatus.STOPPED),
    ("future_reason", CompletionStatus.UNKNOWN),
])
def test_completion_status_mapping(reason, expected):
    result = AnthropicProvider(FakeClient(make_response(stop_reason=reason))).generate(make_request())
    assert result.completion_status is expected


def sdk_status_error(cls, status=401, body=None):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, headers={"request-id": "req_error"})
    return cls("SECRET HEADER MUST NOT ESCAPE", response=response, body=body)


@pytest.mark.parametrize("sdk_error, adapter_error", [
    (sdk_status_error(anthropic.AuthenticationError), AnthropicAuthenticationError),
    (sdk_status_error(anthropic.PermissionDeniedError, 403), AnthropicPermissionDeniedError),
    (sdk_status_error(anthropic.RateLimitError, 429), AnthropicRateLimitError),
    (sdk_status_error(anthropic.BadRequestError, 400), AnthropicInvalidRequestError),
    (sdk_status_error(anthropic.InternalServerError, 500), AnthropicServerError),
])
def test_status_errors_are_structured_and_sanitized(sdk_error, adapter_error):
    provider = AnthropicProvider(FakeClient(error=sdk_error))
    with pytest.raises(adapter_error) as caught:
        provider.generate(make_request())
    assert caught.value.category
    assert "SECRET HEADER" not in str(caught.value)
    assert caught.value.request_id == "req_error"


def test_timeout_connection_and_other_status_error_translation():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    cases = [
        (anthropic.APITimeoutError(request=request), AnthropicTimeoutError),
        (anthropic.APIConnectionError(request=request), AnthropicConnectionError),
        (sdk_status_error(anthropic.APIStatusError, 404), AnthropicProviderError),
    ]
    for error, expected in cases:
        with pytest.raises(expected) as caught:
            AnthropicProvider(FakeClient(error=error)).generate(make_request())
        assert "SECRET HEADER" not in str(caught.value)


def test_unexpected_sdk_error_is_sanitized():
    class HiddenCredentialError(anthropic.APIError):
        pass
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = HiddenCredentialError("token=do-not-leak", request=request, body=None)
    with pytest.raises(AnthropicProviderError) as caught:
        AnthropicProvider(FakeClient(error=error)).generate(make_request())
    assert "do-not-leak" not in str(caught.value)


def test_unsupported_generation_settings_are_not_silently_ignored():
    provider = AnthropicProvider(FakeClient(make_response()))
    with pytest.raises(UnsupportedAnthropicFeatureError, match="stop_sequences"):
        provider.generate(make_request(generation_settings={"stop_sequences": "END"}))
    assert provider._client.messages.calls == []


def test_non_text_response_blocks_are_explicitly_rejected():
    native = make_response(content=[SimpleNamespace(type="tool_use", id="tool-1", name="x", input={})])
    with pytest.raises(UnsupportedAnthropicFeatureError, match="tool_use"):
        AnthropicProvider(FakeClient(native)).generate(make_request())


def test_malformed_response_and_usage_are_rejected():
    with pytest.raises(AnthropicResponseError):
        AnthropicProvider(FakeClient(SimpleNamespace(content=[], model="m"))).generate(make_request())
    malformed_usage = make_response(usage=SimpleNamespace(input_tokens="7", output_tokens=4))
    with pytest.raises(AnthropicResponseError, match="token counts"):
        AnthropicProvider(FakeClient(malformed_usage)).generate(make_request())


def test_empty_system_instruction_is_omitted_and_neutral_module_stays_vendor_free():
    client = FakeClient(make_response())
    AnthropicProvider(client).generate(make_request(system_instruction="", generation_settings={}))
    assert "system" not in client.messages.calls[0]
    neutral = importlib.import_module("cns_composition.providers.protocol")
    assert neutral.ModelProvider is ModelProvider
    assert not any(name == "anthropic" or name.startswith("anthropic.")
                   for name in neutral.__dict__)

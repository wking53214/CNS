import json

import pytest

from cns_composition.providers import CompletionStatus, ModelProvider, ModelRequest
from cns_composition.providers._http import ProviderError
from cns_composition.providers.groq import GroqProvider


def _provider(reply, status=200, seen=None):
    def transport(url, headers, data, timeout):
        if seen is not None:
            seen.update(url=url, headers=headers, body=json.loads(data))
        return status, json.dumps(reply).encode(), {}
    return GroqProvider("gsk_test", transport=transport)


OK = {"id": "req_1", "model": "llama-3.3-70b-versatile",
      "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 3, "completion_tokens": 1}}


def _req(**kw):
    return ModelRequest("llama-3.3-70b-versatile", "be brief", ("hello",), 50, kw)


def test_implements_protocol_and_normalizes():
    seen = {}
    p = _provider(OK, seen=seen)
    assert isinstance(p, ModelProvider)
    r = p.generate(_req(temperature=0.2))
    assert (r.content, r.provider, r.completion_status, r.request_id) == ("hi", "groq", CompletionStatus.COMPLETE, "req_1")
    assert (r.usage.input_tokens, r.usage.output_tokens) == (3, 1)
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["authorization"] == "Bearer gsk_test"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "be brief"}
    assert seen["body"]["temperature"] == 0.2


def test_length_maps_to_max_tokens():
    reply = {**OK, "choices": [{"message": {"content": "hi"}, "finish_reason": "length"}]}
    assert _provider(reply).generate(_req()).completion_status is CompletionStatus.MAX_TOKENS


@pytest.mark.parametrize("bad", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]},
                                 {"choices": [{"message": {"content": "x", "tool_calls": [1]}}]}])
def test_malformed_response_is_refused(bad):
    with pytest.raises(ProviderError) as info:
        _provider(bad).generate(_req())
    assert info.value.category == "invalid_response"


def test_unsupported_setting_and_http_error():
    with pytest.raises(ProviderError) as info:
        _provider(OK).generate(_req(top_k=5))
    assert info.value.category == "unsupported_feature"
    with pytest.raises(ProviderError) as info:
        _provider({}, status=429).generate(_req())
    assert info.value.category == "rate_limit"


def test_key_never_in_error():
    with pytest.raises(ProviderError) as info:
        _provider({}, status=401).generate(_req())
    assert "gsk_test" not in str(info.value)

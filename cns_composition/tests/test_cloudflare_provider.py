import json

import pytest

from cns_composition.providers import CompletionStatus, ModelProvider, ModelRequest
from cns_composition.providers._http import ProviderError
from cns_composition.providers.cloudflare import CloudflareProvider

MODEL = "@cf/meta/llama-3.1-8b-instruct"


def _p(reply, status=200, seen=None):
    def transport(url, headers, data, timeout):
        if seen is not None:
            seen.update(url=url, headers=headers, body=json.loads(data))
        return status, json.dumps(reply).encode(), {}
    return CloudflareProvider("cf-token", "acct123", transport=transport)


def _req():
    return ModelRequest(MODEL, "sys", ("hello",), 30)


def test_legacy_shape_has_unknown_status():
    seen = {}
    p = _p({"success": True, "result": {"response": "hi"}}, seen=seen)
    assert isinstance(p, ModelProvider)
    r = p.generate(_req())
    assert (r.content, r.provider, r.completion_status) == ("hi", "cloudflare", CompletionStatus.UNKNOWN)
    assert seen["url"].endswith("/accounts/acct123/ai/run/" + MODEL)
    assert seen["headers"]["authorization"] == "Bearer cf-token"
    assert seen["body"]["messages"][0]["role"] == "system"


def test_chat_shape_reports_finish_reason():
    reply = {"success": True, "result": {"choices": [{"message": {"content": "hi"}, "finish_reason": "length"}],
                                         "usage": {"prompt_tokens": 2, "completion_tokens": 1}}}
    r = _p(reply).generate(_req())
    assert r.completion_status is CompletionStatus.MAX_TOKENS and r.usage.input_tokens == 2


@pytest.mark.parametrize("bad", [{}, {"success": False, "result": {"response": "x"}}, {"result": {}},
                                 {"result": {"response": 5}}])
def test_malformed_is_refused(bad):
    with pytest.raises(ProviderError) as info:
        _p(bad).generate(_req())
    assert info.value.category == "invalid_response"


def test_inputs_checked():
    with pytest.raises(ValueError):
        CloudflareProvider("t", "bad/id")
    with pytest.raises(ValueError):
        _p({}).generate(ModelRequest("a/../b", "", ("x",), 5))
    with pytest.raises(ProviderError) as info:
        _p({}, status=401).generate(_req())
    assert "cf-token" not in str(info.value)

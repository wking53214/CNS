import json

import pytest

from cns_composition.providers import CompletionStatus, ModelProvider, ModelRequest
from cns_composition.providers._http import ProviderError
from cns_composition.providers.gemini import GeminiProvider

OK = {"candidates": [{"content": {"parts": [{"text": "hi "}, {"text": "there"}]}, "finishReason": "STOP"}],
      "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2}, "responseId": "r1", "modelVersion": "gemini-x"}


def _p(reply, status=200, seen=None):
    def transport(url, headers, data, timeout):
        if seen is not None:
            seen.update(url=url, headers=headers, body=json.loads(data))
        return status, json.dumps(reply).encode(), {}
    return GeminiProvider("AIza-test", transport=transport)


def _req(**kw):
    return ModelRequest("gemini-x", "sys", ("hello",), 40, kw)


def test_request_shape_and_normalization():
    seen = {}
    p = _p(OK, seen=seen)
    assert isinstance(p, ModelProvider)
    r = p.generate(_req(top_p=0.9))
    assert (r.content, r.provider, r.model, r.request_id) == ("hi there", "gemini", "gemini-x", "r1")
    assert r.completion_status is CompletionStatus.COMPLETE and r.usage.output_tokens == 2
    assert seen["url"].endswith("/models/gemini-x:generateContent")
    assert "AIza-test" not in seen["url"] and seen["headers"]["x-goog-api-key"] == "AIza-test"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert seen["body"]["generationConfig"] == {"maxOutputTokens": 40, "topP": 0.9}


def test_max_tokens_and_unknown_reason():
    for reason, status in (("MAX_TOKENS", CompletionStatus.MAX_TOKENS), ("SAFETY", CompletionStatus.UNKNOWN)):
        reply = {**OK, "candidates": [{"content": {"parts": [{"text": "x"}]}, "finishReason": reason}]}
        assert _p(reply).generate(_req()).completion_status is status


@pytest.mark.parametrize("bad", [{}, {"candidates": []}, {"candidates": [{"finishReason": "SAFETY"}]},
                                 {"candidates": [{"content": {"parts": [{"functionCall": {}}]}}]}])
def test_malformed_is_refused(bad):
    with pytest.raises(ProviderError) as info:
        _p(bad).generate(_req())
    assert info.value.category == "invalid_response"


def test_errors_are_sanitized():
    with pytest.raises(ProviderError) as info:
        _p({}, status=429).generate(_req())
    assert info.value.category == "rate_limit" and "AIza" not in str(info.value)
    with pytest.raises(ProviderError):
        _p(OK).generate(_req(frequency_penalty=1))

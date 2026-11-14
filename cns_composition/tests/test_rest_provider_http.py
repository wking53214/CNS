import json

import pytest

from cns_composition.providers._http import ProviderError, check_https, check_key, post_json


def _t(status, body=b"{}", exc=None):
    def transport(url, headers, data, timeout):
        if exc:
            raise exc
        return status, body, {}
    return transport


def test_ok_returns_parsed_json():
    assert post_json("p", _t(200, b'{"a":1}'), "https://x", {}, {}, 1.0) == {"a": 1}


@pytest.mark.parametrize("status,category", [(401, "authentication"), (403, "authentication"), (429, "rate_limit"),
                                              (500, "server"), (400, "invalid_request")])
def test_status_categories(status, category):
    with pytest.raises(ProviderError) as info:
        post_json("p", _t(status, b"secret-body"), "https://x", {"authorization": "Bearer sk-secret"}, {}, 1.0)
    assert info.value.category == category
    assert "secret" not in str(info.value)


def test_timeout_connection_and_bad_json():
    for exc, category in ((TimeoutError(), "timeout"), (OSError("x"), "connection")):
        with pytest.raises(ProviderError) as info:
            post_json("p", _t(200, exc=exc), "https://x", {}, {}, 1.0)
        assert info.value.category == category
    with pytest.raises(ProviderError) as info:
        post_json("p", _t(200, b"not json"), "https://x", {}, {}, 1.0)
    assert info.value.category == "invalid_response"


def test_https_and_key_checks():
    with pytest.raises(ValueError):
        check_https("p", "http://x")
    for bad in ("", "a b", "a\nb"):
        with pytest.raises(ValueError):
            check_key("p", bad)


def test_request_is_json_with_content_type():
    seen = {}

    def transport(url, headers, data, timeout):
        seen.update(headers=headers, data=data)
        return 200, b"{}", {}
    post_json("p", transport, "https://x", {}, {"k": "v"}, 1.0)
    assert seen["headers"]["content-type"] == "application/json"
    assert json.loads(seen["data"]) == {"k": "v"}

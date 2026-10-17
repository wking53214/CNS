"""fallback_parity: a repository's stand-in for subject_digest must digest exactly as CNS does."""

import hashlib
import json

import pytest
from cns.gate import subject_digest

from cns_composition.fallback_parity import COPIES, SAMPLES, digest_parity


def json_sha256(content):
    """The shortcut a stand-in is tempted by: hash the JSON. Correct-looking, and not CNS's digest."""
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def test_a_copy_identical_to_cns_agrees_on_every_sample():
    result = digest_parity("composition-engine", subject_digest)
    assert result.ok and result.checked == len(SAMPLES) and result.differing == ()


def test_a_json_hash_stand_in_disagrees_on_every_sample():
    result = digest_parity("composition-engine", json_sha256)
    assert not result.ok and len(result.differing) == len(SAMPLES)


def test_a_copy_that_gets_one_thing_wrong_is_named_on_exactly_that_sample():
    def bool_is_int(content):
        return subject_digest({k: (int(v) if isinstance(v, bool) else v) for k, v in content.items()})
    result = digest_parity("composition-engine", bool_is_int)
    assert len(result.differing) == 1 and "'v': True" in result.differing[0]


def test_a_copy_that_raises_or_returns_something_else_disagrees():
    def raises(content):
        raise RuntimeError("boom")
    assert all("raised RuntimeError" in d for d in digest_parity("composition-engine", raises).differing)
    assert all("not text" in d for d in digest_parity("composition-engine", lambda c: 7).differing)


def test_only_a_repository_known_to_carry_a_copy_can_be_checked():
    assert "composition-engine" in COPIES
    with pytest.raises(KeyError, match="add it to COPIES first"):
        digest_parity("Nowhere", subject_digest)


def test_the_samples_probe_the_cases_a_shortcut_gets_wrong():
    assert {"ab": "c"} in SAMPLES and {"a": "bc"} in SAMPLES
    assert {"v": True} in SAMPLES and {"v": 1} in SAMPLES
    assert len({subject_digest(s) for s in SAMPLES}) == len(SAMPLES) - 1   # only 0.0 and -0.0 coincide

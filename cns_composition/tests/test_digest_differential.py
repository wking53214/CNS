"""digest_differential: the seeded corpus is deterministic, exact, and covers both sides of every restricted-v1 edge."""

import hashlib
import json
import random
from pathlib import Path

from cns.gate import _canonical, subject_digest

from cns_composition import digest_differential as D
from cns_composition import digest_vectors as V

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "contracts" / "digest-differential.json"


def _cases():
    return json.loads(COMMITTED.read_text(encoding="utf-8"))["cases"]


def test_regenerating_gives_the_committed_file_byte_for_byte():
    assert COMMITTED.read_text(encoding="utf-8") == D.render(D.build())


def test_the_same_seed_gives_the_same_corpus_and_another_seed_does_not():
    rng_a, rng_b, rng_c = random.Random(D.SEED), random.Random(D.SEED), random.Random(D.SEED + 1)
    a = [D.case(rng_a, i) for i in range(20)]
    assert a == [D.case(rng_b, i) for i in range(20)]
    assert a != [D.case(rng_c, i) for i in range(20)]


def test_the_header_names_the_seed_count_and_algorithm():
    data = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert data["schema"] == "cns-digest-differential/1"
    assert data["digest_version"] == V.DIGEST_VERSION
    assert data["seed"] == D.SEED and data["count"] == D.COUNT == 400 == len(data["cases"])
    assert [c["index"] for c in data["cases"]] == list(range(400))


def test_every_case_survives_json_text_and_matches_rendering_digest_and_flag():
    for c in _cases():
        assert set(c) == {"index", "content", "rendering", "digest", "restricted_v1"}
        assert _canonical(c["content"]) == c["rendering"], c["index"]
        assert subject_digest(c["content"]) == c["digest"], c["index"]
        assert hashlib.sha256(c["rendering"].encode("utf-8")).hexdigest() == c["digest"], c["index"]
        assert c["restricted_v1"] is V.restricted_v1(c["content"]), c["index"]


def _walk(value):
    yield value
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def test_the_corpus_reaches_both_sides_of_every_edge():
    cases = _cases()
    restricted = [c for c in cases if c["restricted_v1"]]
    assert 0 < len(restricted) < len(cases)
    depths = {V.container_depth(c["content"]) for c in cases}
    assert {V.RESTRICTED_V1_MAX_DEPTH, V.RESTRICTED_V1_MAX_DEPTH + 1} <= depths
    values = [v for c in cases for v in _walk(c["content"])]
    ints = [v for v in values if isinstance(v, int) and not isinstance(v, bool)]
    assert any(abs(i) == 2 ** 53 - 1 for i in ints) and any(abs(i) > 2 ** 53 - 1 for i in ints)
    assert any(isinstance(v, float) for v in values)
    text = "".join(v for v in values if isinstance(v, str))
    assert "\x00" in text
    assert any(0xE000 <= ord(ch) <= 0xFFFF for ch in text) and any(ord(ch) > 0xFFFF for ch in text)
    assert any(0x300 <= ord(ch) <= 0x36F for ch in text)
    assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def test_no_case_digests_like_its_canonical_json():
    for c in _cases():
        text = json.dumps(c["content"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() != c["digest"], c["index"]

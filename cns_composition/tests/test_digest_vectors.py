"""digest_vectors: the answer key other languages check their reproduction of subject_digest against."""

import hashlib
import json
from pathlib import Path

import pytest
from cns.gate import _canonical, subject_digest

from cns_composition import digest_vectors as V

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "contracts" / "digest-vectors.json"
DIFFERENTIAL = ROOT / "contracts" / "digest-differential.json"


def test_the_committed_file_is_exactly_what_subject_digest_produces_now():
    assert COMMITTED.read_text(encoding="utf-8") == V._render(V.build())


def test_every_vector_survives_a_round_trip_through_json_text():
    """A reader in another language gets the content from JSON text, so the digest must not depend on Python objects."""
    for vector in json.loads(COMMITTED.read_text(encoding="utf-8"))["vectors"]:
        assert subject_digest(vector["content"]) == vector["digest"], vector["name"]


def test_the_vectors_have_unique_names_and_cover_the_cases_a_shortcut_gets_wrong():
    names = [name for name, _ in V.CASES]
    assert len(names) == len(set(names)) >= 20
    for needed in ("bool_is_not_one", "separator_collision_left", "keys_sort_by_code_point",
                   "length_counts_code_points_not_bytes", "negative_zero", "ints_past_64_bits",
                   "float_one_is_not_int_one"):
        assert needed in names


def test_the_pairs_meant_to_coincide_do_and_nothing_else_does():
    digests = {v["name"]: v["digest"] for v in V.build()["vectors"]}
    assert digests["key_order_ba"] == digests["key_order_ab"]
    assert digests["negative_zero"] == digests["positive_zero"]
    assert len(set(digests.values())) == len(digests) - 2


def test_a_json_float_and_a_json_int_stay_different_after_a_round_trip():
    pair = {v["name"]: v for v in json.loads(COMMITTED.read_text(encoding="utf-8"))["vectors"]}["float_one_is_not_int_one"]
    assert isinstance(pair["content"]["i"], int) and isinstance(pair["content"]["f"], float)


# ------------------------------------------------------------ the vendored copies

@pytest.fixture
def stack(tmp_path: Path) -> Path:
    for repo, rel in V.VENDORED.items():
        path = tmp_path / repo / rel
        path.parent.mkdir(parents=True)
        path.write_text(COMMITTED.read_text(encoding="utf-8"), encoding="utf-8")
    for repo, rel in V.VENDORED_DIFFERENTIAL.items():
        path = tmp_path / repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DIFFERENTIAL.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_an_identical_vendored_copy_has_no_drift(stack):
    assert V.drift(stack) == []


def test_a_vendored_copy_that_differs_is_reported_and_says_what_to_do(stack):
    repo, rel = next(iter(V.VENDORED.items()))
    path = stack / repo / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    data["vectors"][0]["digest"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    out = V.drift(stack)
    assert len(out) == 1 and out[0].startswith(repo) and "copy the committed file" in out[0]


def test_a_missing_or_unreadable_or_absent_copy_is_reported(stack):
    repo, rel = next(iter(V.VENDORED.items()))
    path = stack / repo / rel
    path.write_text("{", encoding="utf-8")
    assert "not readable JSON" in V.drift(stack)[0]
    path.unlink()
    assert "no vendored vectors" in V.drift(stack)[0]


def test_a_registered_repo_with_no_checkout_is_reported(tmp_path):
    assert "no checkout" in V.drift(tmp_path)[0]


def test_the_command_passes_on_the_committed_file_and_fails_on_a_stale_one(tmp_path, capsys, monkeypatch):
    assert V.main([]) == 0
    stale = tmp_path / "digest-vectors.json"
    stale.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(V, "_default_path", lambda: stale)
    assert V.main([]) == 1
    assert "run with --write" in capsys.readouterr().err
    assert V.main(["--write"]) == 0 and stale.read_text(encoding="utf-8") == V._render(V.build())


def test_a_symlinked_stack_folder_is_compared_like_any_other(tmp_path):
    """2.0.0: a vendored copy reached through a symlinked stack folder is compared, not reported as missing."""
    real = tmp_path / "elsewhere"
    for repo, rel in V.VENDORED.items():
        path = real / repo / rel
        path.parent.mkdir(parents=True)
        path.write_text(COMMITTED.read_text(encoding="utf-8"), encoding="utf-8")
    for repo, rel in V.VENDORED_DIFFERENTIAL.items():
        path = real / repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DIFFERENTIAL.read_text(encoding="utf-8"), encoding="utf-8")
    stack = tmp_path / "stack"
    stack.mkdir()
    for repo in V.VENDORED:
        (stack / repo).symlink_to(real / repo, target_is_directory=True)
    assert V.drift(stack) == []
    for repo, rel in V.VENDORED.items():
        (real / repo / rel).write_text("{}")
    assert all("differ from CNS" in line for line in V.drift(stack)) and V.drift(stack)


# ------------------------------------------------------------ schema 2 (D-15)

# The 24 digests of schema 1, copied from the file as it was before schema 2. They are frozen: a change to any of
# them is a change to the algorithm, which needs a new digest_version, not a regenerated file.
FROZEN_V1_DIGESTS = {
    "empty": "c348e1722fbda6fbdd0ce8ec7831067eeff989c54b833673b8ebf6890883f012",
    "one_int": "32a98aef7315bc917ac0b650017f846e82bab90385cfe71b6fb53313ddf0006a",
    "null_bool_int": "f1f5dffeacf4d615ddb4871add870412420b31353cdcd47bcc6df60974e86bde",
    "bool_is_not_one": "525e4bb8f6ca1c3131980e369c25797ee4ba7f596b47e68471cad15e3d5d2aee",
    "separator_collision_left": "9c91082e6a9ec1dc9b26d6e16a13cf8e3786769e441760af4ddb93be4818670b",
    "separator_collision_right": "e4be55f20a1f111137a912fb3434b422b392060a6fec2111830f179da02765a1",
    "keys_sort_by_code_point": "bbf67385935d6d25443b1b3752c5ac50ac16d0fd121d60f708f5b1a9f8816bbf",
    "key_order_ba": "acd0be1d57187dae28a701535f4d6ac035f647d79281337902d0c55d60d5738a",
    "key_order_ab": "acd0be1d57187dae28a701535f4d6ac035f647d79281337902d0c55d60d5738a",
    "length_counts_code_points_not_bytes": "b1436e6d2c4c8b8ac453885da0ada4fe58a9ede9640f9f79fab7f6bae699719b",
    "combining_is_not_normalised": "9e01fd509d6ef3e164d9da946f309866c9c2f52d2307c8dc81200a8a035bed5e",
    "empty_string_and_list": "d857a7913538d8d7b81e16c2644d717698c99970a007ac69e047cb92a1ab833e",
    "string_that_looks_like_the_encoding": "61ca0e132aae235dba24b9dc8f7c0e915a8a6209de363235484b39fac646b7f9",
    "nested": "61567fcfc252385f02c87806eb3f58eabb56312e798a099794a7acc012c01937",
    "floats_simple": "8c8f904c2f8e018e3537b98c6ba2cfa512b051b60c9411e4b9faa3e1bcd5feb0",
    "float_one_is_not_int_one": "cd25f1bc921dc98bd2028b2205f7a13a0a3e68110d5027b0890bc4250779febc",
    "negative_zero": "893c683e0df0e4b902f166af65e70080691630f7ebd75b1fcb9c4998548b9b87",
    "positive_zero": "893c683e0df0e4b902f166af65e70080691630f7ebd75b1fcb9c4998548b9b87",
    "float_exponents": "9d83d02a537fc0355339432fca0136c4a05329096d31e2012817831598e46e1d",
    "float_shortest_round_trip": "808450da8cee8799e3e69b35de4525e8f61315d142d92dbd8133b755c49fc8d2",
    "ints_at_the_edges": "49894986fa1b292624bae24b94efd64377ddd00579e73b89e4776bb9d0d46e95",
    "ints_past_64_bits": "6c630763356972faf026213d9a2f4bdc4b2c8400163a252699d2f7bbde8964c0",
    "long_list": "d0f6e218e56137266d133f461395b9c3d54a23b618abe1ce1885e72b18974d80",
    "deep": "37adf00cf0b4bc2eb90324f8c8d63900af03002bfe90de82ca3d52b3c61a63ab",
}


def _committed():
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def test_the_24_schema_1_digests_are_frozen_in_name_order_and_value():
    vectors = _committed()["vectors"]
    assert len(FROZEN_V1_DIGESTS) == 24
    assert [v["name"] for v in vectors[:24]] == list(FROZEN_V1_DIGESTS)
    for v in vectors[:24]:
        assert v["digest"] == FROZEN_V1_DIGESTS[v["name"]], v["name"]
        assert subject_digest(v["content"]) == FROZEN_V1_DIGESTS[v["name"]], v["name"]


def test_schema_2_names_the_algorithm_and_the_domain():
    data = _committed()
    assert data["schema"] == "cns-digest-vectors/2"
    assert data["digest_version"] == V.DIGEST_VERSION == "cns-digest/1"
    domain = data["domain"]
    assert set(domain) >= {"content", "values", "rendering", "digest", "depth", "restricted_v1"}
    restricted = domain["restricted_v1"]
    assert restricted["max_container_depth"] == V.RESTRICTED_V1_MAX_DEPTH == 31
    assert restricted["max_abs_integer"] == 2 ** 53 - 1
    assert "never falls back" in restricted["outside"]


def test_every_vector_carries_the_rendering_it_hashes_and_a_computed_flag():
    for v in _committed()["vectors"]:
        assert set(v) == {"name", "content", "rendering", "digest", "restricted_v1"}, v["name"]
        assert v["rendering"] == _canonical(v["content"]), v["name"]
        assert hashlib.sha256(v["rendering"].encode("utf-8")).hexdigest() == v["digest"], v["name"]
        assert v["restricted_v1"] is V.restricted_v1(v["content"]), v["name"]


def test_restricted_v1_is_exactly_the_documented_rule():
    assert V.restricted_v1({"a": 2 ** 53 - 1, "b": -(2 ** 53 - 1), "t": True, "n": None, "s": "x"})
    assert not V.restricted_v1({"a": 2 ** 53})
    assert not V.restricted_v1({"a": -(2 ** 53)})
    assert not V.restricted_v1({"a": [1.0]})
    assert not V.restricted_v1({"a": 0.0})
    assert V.container_depth({}) == 1 and V.container_depth({"a": 1}) == 1 and V.container_depth({"a": []}) == 2
    assert V.container_depth(V._nested(31)) == 31 and V.restricted_v1(V._nested(31))
    assert V.container_depth(V._nested(32)) == 32 and not V.restricted_v1(V._nested(32))


def test_schema_2_adds_the_cases_the_first_file_lacked():
    data = {v["name"]: v for v in _committed()["vectors"]}
    for needed in ("astral_keys_sort_after_high_bmp_keys", "empty_string_key", "nul_and_control_characters",
                   "mixed_multilingual_text", "int_at_the_safe_limit", "int_one_past_the_safe_limit",
                   "negative_int_one_past_the_safe_limit", "negative_ints", "depth_at_the_restricted_limit",
                   "depth_one_past_the_restricted_limit", "long_string", "many_keys_scrambled_insertion_order",
                   "json_escapes_are_not_cns_escapes", "text_that_looks_like_json"):
        assert needed in data
    assert data["int_at_the_safe_limit"]["restricted_v1"] is True
    assert data["int_one_past_the_safe_limit"]["restricted_v1"] is False
    assert data["negative_int_one_past_the_safe_limit"]["restricted_v1"] is False
    assert data["depth_at_the_restricted_limit"]["restricted_v1"] is True
    assert data["depth_one_past_the_restricted_limit"]["restricted_v1"] is False
    assert len(data["long_string"]["content"]["s"]) == 10000


def test_astral_keys_sort_by_code_point_not_by_utf16():
    v = {x["name"]: x for x in _committed()["vectors"]}["astral_keys_sort_after_high_bmp_keys"]
    keys = list(v["content"])
    by_code_point = sorted(keys)
    by_utf16 = sorted(keys, key=lambda k: k.encode("utf-16-be"))
    assert by_code_point != by_utf16
    positions = [v["rendering"].index(f"s:1:{k}") for k in by_code_point]
    assert positions == sorted(positions)


def test_the_scrambled_keys_are_scrambled_in_the_file_and_digest_like_sorted_ones():
    v = {x["name"]: x for x in _committed()["vectors"]}["many_keys_scrambled_insertion_order"]
    keys = list(v["content"])
    assert len(keys) == 200 and keys != sorted(keys)
    assert subject_digest({k: v["content"][k] for k in sorted(keys)}) == v["digest"]


def test_no_vector_digests_like_its_canonical_json():
    """The algorithm Trident used before CNS: SHA-256 of sorted, compact JSON. A CNS rendering of a map starts with
    `d:` and a JSON object starts with `{`, so the two hash different byte strings for every content."""
    for v in _committed()["vectors"]:
        text = json.dumps(v["content"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() != v["digest"], v["name"]
        assert v["rendering"].startswith("d:") and text.startswith("{")


def test_every_refusal_is_named_and_python_raises_type_error_on_each():
    refusals = _committed()["refusals"]
    names = [r["name"] for r in refusals]
    assert names == ["nan", "positive_infinity", "negative_infinity", "lone_high_surrogate", "lone_low_surrogate",
                     "non_text_key", "bytes"]
    values = V._refusal_values()
    assert set(values) == set(names)
    for r in refusals:
        assert set(r) == {"name", "what", "lenient_json", "why"}
        with pytest.raises(TypeError):
            subject_digest(values[r["name"]])
        if r["lenient_json"] is not None:
            # Python's json is lenient: it accepts NaN, the infinities and lone surrogate escapes. The digest refuses.
            with pytest.raises(TypeError):
                subject_digest(json.loads(r["lenient_json"]))
    assert [r["name"] for r in refusals if r["lenient_json"] is None] == ["non_text_key", "bytes"]


def test_drift_compares_the_whole_file_not_only_the_digests(stack):
    repo, rel = next(iter(V.VENDORED.items()))
    path = stack / repo / rel
    for mutate in (lambda d: d["domain"].update(content="other"),
                   lambda d: d["refusals"].pop(),
                   lambda d: d["vectors"][0].update(rendering="x"),
                   lambda d: d["vectors"][0].update(restricted_v1=False),
                   lambda d: d.update(digest_version="cns-digest/0")):
        data = _committed()
        mutate(data)
        path.write_text(json.dumps(data), encoding="utf-8")
        assert len(V.drift(stack)) == 1
    path.write_text(COMMITTED.read_text(encoding="utf-8"), encoding="utf-8")
    assert V.drift(stack) == []

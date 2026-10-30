"""digest_vectors: the answer key other languages check their reproduction of subject_digest against."""

import json
from pathlib import Path

import pytest
from cns.gate import subject_digest

from cns_composition import digest_vectors as V

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "contracts" / "digest-vectors.json"


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
    stack = tmp_path / "stack"
    stack.mkdir()
    for repo in V.VENDORED:
        (stack / repo).symlink_to(real / repo, target_is_directory=True)
    assert V.drift(stack) == []
    for repo, rel in V.VENDORED.items():
        (real / repo / rel).write_text("{}")
    assert all("differ from CNS" in line for line in V.drift(stack)) and V.drift(stack)

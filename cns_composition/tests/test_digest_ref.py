"""A subject digest that names its encoding (CNS-101): both forms verify against the shared vectors, a digest made
with an encoding CNS does not implement never does, and an unreadable reference is refused."""

import json
import pathlib

import pytest

from cns.gate import DigestRef, subject_digest
from cns_composition.digest_ref import DIGEST_VERSION, matches, parse, ref_of

VECTORS = json.loads((pathlib.Path(__file__).resolve().parents[2] / "contracts" / "digest-vectors.json")
                     .read_text(encoding="utf-8"))


def test_the_named_encoding_is_the_one_the_vectors_file_names():
    assert DIGEST_VERSION == VECTORS["digest_version"]


@pytest.mark.parametrize("row", VECTORS["vectors"], ids=lambda r: r["name"])
def test_every_vector_verifies_bare_and_named(row):
    bare, named = parse(row["digest"]), parse(f"{DIGEST_VERSION}:{row['digest']}")
    assert bare == named == DigestRef(row["digest"])
    assert matches(bare, row["content"]) and matches(named, row["content"])


def test_a_reference_travels_as_version_then_value_and_reads_back():
    ref = ref_of({"a": 1})
    assert ref.text() == f"{DIGEST_VERSION}:{subject_digest({'a': 1})}"
    assert parse(ref.text()) == ref


def test_other_content_does_not_match():
    assert not matches(ref_of({"a": 1}), {"a": 2})


def test_a_digest_under_an_encoding_cns_does_not_implement_never_matches():
    value = subject_digest({"a": 1})
    other = parse(f"cns-digest/2:{value}")
    assert other.version == "cns-digest/2" and not matches(other, {"a": 1})


@pytest.mark.parametrize("text", ["", "abc", "A" * 64, "g" * 64, ":" + "a" * 64, "cns-digest/1:" + "a" * 63,
                                  "no version:" + "a" * 64, "cns-digest:" + "a" * 64, 7, None])
def test_a_reference_that_cannot_be_read_is_refused(text):
    with pytest.raises(ValueError):
        parse(text)


def test_only_a_digest_ref_is_checked():
    assert not matches(subject_digest({"a": 1}), {"a": 1})

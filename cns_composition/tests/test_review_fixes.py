"""Findings of the independent review of the decision-evidence work: each case ran and misbehaved before its fix."""

import dataclasses

import pytest

from cns_composition import consumers
from cns_composition.decision_guard import DecisionGuard
from cns_composition.super_gate import Judged, digest_context
from cns_composition.tests.test_decision_guard import decision


def test_a_hand_built_decision_with_a_non_text_seat_is_not_allowed_and_never_raises():
    issued = decision()
    odd = dataclasses.replace(issued, seats=(None, "DIT:judge"))
    assert odd.allowed is False
    assert odd.reasons()  # does not raise


def test_a_guard_refuses_such_a_decision_with_a_value_error_not_a_type_error():
    odd = dataclasses.replace(decision(), seats=(None, "DIT:judge"))
    with pytest.raises(ValueError):
        DecisionGuard(lambda artifact: Judged(*artifact)).authorize(odd)


@pytest.mark.parametrize("bad", [{"action": "\ud800"}, {"\ud800": "x"}])
def test_a_context_that_cannot_be_digested_is_a_value_error(bad):
    with pytest.raises(ValueError):
        digest_context(bad)


def test_a_mapping_that_answers_differently_from_its_items_is_digested_as_its_items():
    class Lying(dict):
        def keys(self):
            return ["action"]

        def __getitem__(self, key):
            return "something else"

    assert digest_context(Lying({"action": "send"})) == digest_context({"action": "send"})


@pytest.mark.parametrize("bad", [5, {"a": "b"}])
def test_expected_seats_that_are_not_a_collection_of_names_are_a_value_error(bad):
    with pytest.raises(ValueError):
        DecisionGuard(lambda artifact: Judged(*artifact), expected_seats=bad)


def test_drift_refuses_a_single_string_as_the_expected_repositories(tmp_path):
    with pytest.raises(ValueError, match="not one string"):
        consumers.drift(tmp_path, required={}, expect="Link")


def test_a_repository_that_imports_only_cns_interop_is_seen_as_a_consumer(tmp_path):
    repo = tmp_path / "Edge"
    repo.mkdir()
    (repo / "mod.py").write_text("from cns_interop.decision import from_super_gate\n")
    assert "cns_interop.decision" in consumers.scan(repo)
    problems = consumers.drift(tmp_path, required={}, expect=("Edge",))
    assert any("Edge" in p and "not registered" in p for p in problems)

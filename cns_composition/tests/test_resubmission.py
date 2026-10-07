"""The resubmission guard (cns_composition.resubmission)."""

from __future__ import annotations

import pytest

from cns.gate import Gate, GateChain, GateOutcome, GatePosition, resolve, subject_digest
from cns_composition.resubmission import GATE_NAME, Resubmission, ResubmissionGuard

A = Resubmission("item-1", subject_digest({"text": "version A"}))
B = Resubmission("item-1", subject_digest({"text": "version B"}))
C = Resubmission("item-1", subject_digest({"text": "version C"}))


def outcomes(guard, *subs):
    return [guard.check(s).outcome for s in subs]


def test_is_an_alpha_gate_and_sits_in_the_alpha_slot():
    guard = ResubmissionGuard()
    assert isinstance(guard, Gate)
    assert guard.position is GatePosition.ALPHA
    assert GateChain(alpha=(guard,)).misplaced() == ()


def test_first_submission_passes_and_the_verdict_is_bound():
    result = ResubmissionGuard().check(A)
    assert result.outcome is GateOutcome.PASS
    assert result.gate == GATE_NAME
    expected = subject_digest({"subject": A.subject, "content_digest": A.content_digest})
    assert result.binds(A.subject, expected)
    assert not result.binds(B.subject, subject_digest(
        {"subject": B.subject, "content_digest": B.content_digest}))


def test_changed_resubmissions_pass():
    assert outcomes(ResubmissionGuard(), A, B, C) == [GateOutcome.PASS] * 3


def test_unchanged_resubmission_is_allowed_up_to_the_cap_then_refused():
    guard = ResubmissionGuard(max_unchanged=3)
    assert outcomes(guard, A, A, A) == [GateOutcome.PASS] * 3
    refused = guard.check(A)
    assert refused.outcome is GateOutcome.TERMINAL_BREACH
    assert "unchanged" in refused.reason


def test_a_change_resets_the_unchanged_count():
    guard = ResubmissionGuard(max_unchanged=2)
    assert outcomes(guard, A, A, B, B) == [GateOutcome.PASS] * 4
    assert guard.check(B).outcome is GateOutcome.TERMINAL_BREACH


def test_returning_to_an_earlier_version_is_oscillation():
    guard = ResubmissionGuard()
    assert outcomes(guard, A, B) == [GateOutcome.PASS] * 2
    refused = guard.check(A)
    assert refused.outcome is GateOutcome.TERMINAL_BREACH
    assert "oscillation" in refused.reason


def test_a_refused_submission_is_not_remembered_so_it_stays_refused():
    guard = ResubmissionGuard()
    outcomes(guard, A, B)
    assert outcomes(guard, A, A) == [GateOutcome.TERMINAL_BREACH] * 2
    assert guard.attempts("item-1") == 2
    assert guard.check(C).outcome is GateOutcome.PASS


def test_same_content_after_an_upstream_retry_is_allowed():
    # ccc_admission answers RETRY when CCC has not recorded an item yet; the
    # remedy is to ask again with exactly the same text once CCC holds it.
    guard = ResubmissionGuard()
    assert outcomes(guard, A, A) == [GateOutcome.PASS, GateOutcome.PASS]


def test_subjects_are_independent():
    guard = ResubmissionGuard(max_unchanged=1)
    other = Resubmission("item-2", A.content_digest)
    assert outcomes(guard, A, other) == [GateOutcome.PASS] * 2
    assert guard.check(A).outcome is GateOutcome.TERMINAL_BREACH
    assert guard.attempts("item-2") == 1


def test_forget_clears_one_subject():
    guard = ResubmissionGuard()
    outcomes(guard, A, B)
    guard.forget("item-1")
    guard.forget("never-seen")
    assert guard.attempts("item-1") == 0
    assert guard.check(A).outcome is GateOutcome.PASS


def test_history_per_subject_is_bounded():
    guard = ResubmissionGuard(max_history=2)
    outcomes(guard, A, B, C)
    assert guard.attempts("item-1") == 2
    # A has aged out of the window, so returning to it is not detected.
    assert guard.check(A).outcome is GateOutcome.PASS


def test_subject_count_is_bounded_least_recently_judged_first():
    guard = ResubmissionGuard(max_subjects=2)
    one, two, three = (Resubmission(f"s{i}", "d") for i in (1, 2, 3))
    outcomes(guard, one, two)
    guard.check(one)
    guard.check(three)
    assert guard.attempts("s2") == 0
    assert guard.attempts("s1") == 2
    assert guard.attempts("s3") == 1


def test_a_breach_decides_the_whole_set_under_resolve():
    guard = ResubmissionGuard()
    outcomes(guard, A, B)
    assert resolve([guard.check(A)]) is GateOutcome.TERMINAL_BREACH


@pytest.mark.parametrize("subject,digest", [("", "d"), ("s", ""), (None, "d"), ("s", 7)])
def test_resubmission_fields_must_be_non_empty_strings(subject, digest):
    with pytest.raises(ValueError):
        Resubmission(subject, digest)


@pytest.mark.parametrize("kwargs", [
    {"max_unchanged": 0}, {"max_history": -1}, {"max_subjects": True}, {"max_unchanged": 2.5},
])
def test_limits_must_be_positive_integers(kwargs):
    with pytest.raises(ValueError):
        ResubmissionGuard(**kwargs)


def test_only_a_resubmission_is_judged():
    with pytest.raises(TypeError):
        ResubmissionGuard().check("item-1")

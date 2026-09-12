"""The gate contract's own invariants.

`cns.gate` exists because an ordering that lives as a convention inside
four files does not survive a repository written later. These tests are the
part of that claim this package can enforce on its own: that the two ends
are distinguishable, that a misplaced gate is detectable from the row
alone, and that the failure precedence is fail-closed by construction.

What they cannot check is whether a consumer actually runs `alpha` before
doing the work. That is the consumer's test to write, and `GateChain`
exists so that it is one assertion rather than a code review.
"""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from cns.gate import (
    Gate,
    GateChain,
    GateOutcome,
    GatePosition,
    GateResult,
    resolve,
    subject_digest,
    unbound,
)
from cns.rowenum import RowEnum


class _Stub:
    """A conforming gate. Consumers supply the predicate; this supplies none."""

    def __init__(self, name: str, position: GatePosition, outcome: GateOutcome) -> None:
        self.name = name
        self.position = position
        self._outcome = outcome

    def check(self, candidate: object) -> GateResult:
        return GateResult(self.name, self.position, self._outcome)


def _alpha(name: str = "origin", outcome: GateOutcome = GateOutcome.PASS) -> _Stub:
    return _Stub(name, GatePosition.ALPHA, outcome)


def _omega(name: str = "outcome", outcome: GateOutcome = GateOutcome.PASS) -> _Stub:
    return _Stub(name, GatePosition.OMEGA, outcome)


def test_the_protocol_recognises_a_conforming_gate():
    assert isinstance(_alpha(), Gate)


def test_a_gate_without_a_declared_position_is_not_one():
    class NoPosition:
        name = "half"

        def check(self, candidate: object) -> GateResult:  # pragma: no cover
            raise NotImplementedError

    assert not isinstance(NoPosition(), Gate)


def test_results_are_frozen_rows():
    r = GateResult("origin", GatePosition.ALPHA, GateOutcome.PASS)
    with pytest.raises(FrozenInstanceError):
        r.outcome = GateOutcome.RETRY  # type: ignore[misc]


def test_blocking_reads_only_its_own_fields():
    assert not GateResult("g", GatePosition.ALPHA, GateOutcome.PASS).blocking()
    assert GateResult("g", GatePosition.ALPHA, GateOutcome.RETRY).blocking()
    assert GateResult("g", GatePosition.OMEGA, GateOutcome.TERMINAL_BREACH).blocking()


def test_both_enums_are_row_enums():
    """Every enum in a row shape inherits RowEnum. See cns.rowenum."""
    for cls in (GatePosition, GateOutcome):
        assert issubclass(cls, RowEnum)
        for m in cls:
            assert str(m) == m.value
            assert json.dumps(m) == f'"{m.value}"'
            assert m == m.value


def test_a_result_round_trips_through_json():
    import dataclasses

    r = GateResult("origin", GatePosition.ALPHA, GateOutcome.TERMINAL_BREACH, "no")
    assert json.loads(json.dumps(dataclasses.asdict(r))) == {
        "gate": "origin",
        "position": "alpha",
        "outcome": "terminal_breach",
        "reason": "no",
        "subject": "",
        "subject_digest": "",
    }


# --- the ordering invariant, which is the reason the module exists ----------


def test_a_chain_with_one_end_is_not_complete():
    """The measured defect, as a test. Four repositories in the library carry
    a precondition and a token outcome check; one carries a good outcome
    stratum and no precondition. Both are this assertion failing."""
    assert not GateChain(alpha=(_alpha(),)).complete()
    assert not GateChain(omega=(_omega(),)).complete()
    assert not GateChain().complete()
    assert GateChain(alpha=(_alpha(),), omega=(_omega(),)).complete()


def test_a_gate_in_the_wrong_slot_is_named():
    chain = GateChain(alpha=(_alpha("a"), _omega("wrong")), omega=(_omega("b"),))
    assert chain.misplaced() == ("wrong",)


def test_a_correct_chain_has_nothing_misplaced():
    assert GateChain(alpha=(_alpha(),), omega=(_omega(),)).misplaced() == ()


def test_the_two_ends_are_separate_fields_not_one_sequence():
    """A single ordered list records the order someone wrote it in. Separate
    fields record which end each gate is for, which is the thing that has to
    survive being copied into another repository."""
    fields = [f.name for f in __import__("dataclasses").fields(GateChain)]
    assert fields == ["alpha", "omega"]


# --- fail-closed resolution ------------------------------------------------


def test_a_terminal_breach_decides_the_whole_set():
    results = [
        GateResult("a", GatePosition.ALPHA, GateOutcome.PASS),
        GateResult("b", GatePosition.OMEGA, GateOutcome.TERMINAL_BREACH),
        GateResult("c", GatePosition.OMEGA, GateOutcome.RETRY),
    ]
    assert resolve(results) is GateOutcome.TERMINAL_BREACH


def test_a_retry_outranks_a_pass():
    results = [
        GateResult("a", GatePosition.ALPHA, GateOutcome.PASS),
        GateResult("b", GatePosition.OMEGA, GateOutcome.RETRY),
    ]
    assert resolve(results) is GateOutcome.RETRY


def test_all_passing_passes():
    results = [GateResult(n, GatePosition.ALPHA, GateOutcome.PASS) for n in "ab"]
    assert resolve(results) is GateOutcome.PASS


def test_no_results_is_a_pass_and_that_is_deliberate():
    """`resolve` refuses on evidence. With no verdicts it has none, and
    inventing one would hide the real defect, which is a chain that should
    have carried gates. `GateChain.complete` is where that is caught."""
    assert resolve([]) is GateOutcome.PASS


def test_resolve_does_not_require_a_list():
    """Consumers stream verdicts out of generators; a single pass is enough."""
    gen = (GateResult("g", GatePosition.ALPHA, GateOutcome.RETRY) for _ in range(2))
    assert resolve(gen) is GateOutcome.RETRY


def test_terminal_breach_short_circuits():
    """The first terminal breach returns, so a consumer may put its most
    expensive gate last without paying for it on a refusal."""
    seen = []

    def verdicts():
        seen.append("first")
        yield GateResult("a", GatePosition.ALPHA, GateOutcome.TERMINAL_BREACH)
        seen.append("second")  # pragma: no cover
        yield GateResult("b", GatePosition.OMEGA, GateOutcome.PASS)  # pragma: no cover

    assert resolve(verdicts()) is GateOutcome.TERMINAL_BREACH
    assert seen == ["first"]


# --- binding a verdict to what it judged (1.2.0) ---------------------------


def test_a_verdict_can_record_what_it_judged():
    d = subject_digest({"claim_id": "c1", "value": "42"})
    r = GateResult("origin", GatePosition.ALPHA, GateOutcome.PASS, "ok", "c1", d)
    assert r.bound()
    assert r.binds("c1", d)


def test_a_hand_built_verdict_binds_to_nothing():
    """The failure this exists to catch. An unbound result must not satisfy a
    binding check, including one passed empty arguments, or every hand-built
    GateResult passes the check written to find hand-built ones."""
    r = GateResult("loose", GatePosition.ALPHA, GateOutcome.PASS)
    assert not r.bound()
    assert not r.binds("", "")
    assert not r.binds("c1", subject_digest({"any": "thing"}))


def test_a_verdict_does_not_bind_to_different_content():
    """Transplant detection: the verdict was issued for c1's content and does
    not carry over to c2, or to c1 after c1 changed."""
    d1 = subject_digest({"claim_id": "c1", "value": "42"})
    d2 = subject_digest({"claim_id": "c1", "value": "43"})
    r = GateResult("origin", GatePosition.ALPHA, GateOutcome.TERMINAL_BREACH,
                   "no", "c1", d1)
    assert r.binds("c1", d1)
    assert not r.binds("c1", d2)
    assert not r.binds("c2", d1)


def test_the_digest_is_canonical_not_incidental():
    """Two consumers that hash the same content differently cannot check each
    other's verdicts, which is the only reason this function is shared."""
    assert subject_digest({"a": 1, "b": 2}) == subject_digest({"b": 2, "a": 1})
    assert subject_digest({"a": 1}) != subject_digest({"a": "1"})
    assert len(subject_digest({})) == 64


def test_the_digest_refuses_content_it_cannot_describe():
    """A gate binding a verdict to something unrenderable is a defect in the
    gate. Silently coercing it with str() would hide that."""
    with pytest.raises(TypeError):
        subject_digest({"gate": object()})
    with pytest.raises(TypeError):
        subject_digest({"measured": 0.1})


def test_the_encoding_cannot_collide():
    """Length prefixes rather than separators, so a shifted boundary cannot
    produce the same rendering. A separator-based format needs escaping to
    make this true; this one cannot have the collision."""
    assert subject_digest({"ab": "c"}) != subject_digest({"a": "bc"})
    assert subject_digest({"a": "1"}) != subject_digest({"a": 1})
    assert subject_digest({"a": True}) != subject_digest({"a": 1})
    assert subject_digest({"a": None}) != subject_digest({"a": ""})
    assert subject_digest({"a": ["b", "c"]}) != subject_digest({"a": ["bc"]})


def test_unbound_names_the_loose_verdicts():
    d = subject_digest({"x": 1})
    results = [
        GateResult("a", GatePosition.ALPHA, GateOutcome.PASS, "", "s", d),
        GateResult("b", GatePosition.OMEGA, GateOutcome.PASS),
        GateResult("c", GatePosition.OMEGA, GateOutcome.RETRY, "", "s", ""),
    ]
    assert unbound(results) == ("b", "c")


def test_binding_is_a_separate_question_from_resolution():
    """`resolve` decides what verdicts mean; it does not adjudicate whether
    they are well-formed. Keeping those apart means a consumer that does not
    require binding is not forced into it, and one that does asserts it
    explicitly."""
    loose = [GateResult("b", GatePosition.OMEGA, GateOutcome.TERMINAL_BREACH)]
    assert resolve(loose) is GateOutcome.TERMINAL_BREACH
    assert unbound(loose) == ("b",)


def test_reason_kept_its_position():
    """1.1.0 shipped GateResult(gate, position, outcome, reason). The new
    fields are appended so that positional construction still means what it
    did, which is why this is a minor version and not a major one."""
    r = GateResult("g", GatePosition.ALPHA, GateOutcome.RETRY, "because")
    assert r.reason == "because"
    assert r.subject == "" and r.subject_digest == ""

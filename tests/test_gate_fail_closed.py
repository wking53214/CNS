"""resolve and the chain runner fail closed on a verdict that is not one of the three outcomes.

`GateOutcome` is a `(str, Enum)`, so the string "terminal_breach" EQUALS the member. `resolve` compared with `is`, so a
verdict carrying the string (a connector that mapped its own status to text, a hand-built result, a row read back from
JSON) matched neither TERMINAL_BREACH nor RETRY and the set resolved to PASS. A refusal read as a go.
"""

import pytest
from cns.gate import GateOutcome, GatePosition, GateResult, resolve, subject_digest

A, OM = GatePosition.ALPHA, GatePosition.OMEGA


def verdict(outcome, position=A):
    return GateResult(gate="g", position=position, outcome=outcome, reason="r", subject="s",
                      subject_digest=subject_digest({"k": 1}))


@pytest.mark.parametrize("odd", ["terminal_breach", "retry", "pass", "PASS", "", None, 0, 3, object(), b"pass"])
def test_a_verdict_that_is_not_a_gate_outcome_resolves_to_a_breach_never_a_pass(odd):
    assert resolve([verdict(GateOutcome.PASS), verdict(odd)]) is GateOutcome.TERMINAL_BREACH


def test_a_lone_odd_verdict_is_a_breach_too():
    assert resolve([verdict("terminal_breach")]) is GateOutcome.TERMINAL_BREACH


def test_real_outcomes_resolve_as_they_always_did():
    p, r, b = GateOutcome.PASS, GateOutcome.RETRY, GateOutcome.TERMINAL_BREACH
    assert resolve([]) is p and resolve([verdict(p)]) is p
    assert resolve([verdict(p), verdict(r)]) is r
    assert resolve([verdict(r), verdict(b), verdict(p)]) is b

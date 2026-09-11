"""Every row must survive the trip.

This is the test whose absence let 0.2.0 ship a `CallPercept` that could not
be serialised at all. `cns.perception.CallOutcome` was a plain `Enum` while
every `cns.governance` enum was a `(str, Enum)` mixin, so `json.dumps` raised
`TypeError` on any percept, in a package whose `cns.caller` docstring
promised "Serialization is strictly JSON-compatible".

A second defect was hiding behind the first. The bare `(str, Enum)` mixin
renders differently depending on the interpreter:

    python3.10   f"{ExecutionDomain.AI}"  ->  'ai'
    python3.11+  f"{ExecutionDomain.AI}"  ->  'ExecutionDomain.AI'

`pyproject.toml` promises 3.10 and up, so that divergence was live in four
shipped contracts. Any log line, cache key or URL segment built from a row
differed across hosts. `cns.rowenum.RowEnum` pins both, and the CI matrix
is what proves it: these assertions are only meaningful because they run on
3.10, 3.11, 3.12 and 3.13.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum

import pytest

from cns.caller import CallerState, DynamicState
from cns.governance import (ExecutionDomain, IdentityContext, IntentCategory,
                            KernelMetadata, QueueType, RoutingDecision,
                            TrustLevel)
from cns.perception import (CallOutcome, CallPercept, EmotionalState,
                            FrictionEvent)
from cns.rowenum import RowEnum

ALL_ENUMS = [CallOutcome, ExecutionDomain, TrustLevel, IntentCategory, QueueType]


def _percept() -> CallPercept:
    return CallPercept(
        caller_id="c1",
        journey=["root", "billing"],
        friction_events=[FrictionEvent(node="billing", type="repeat", severity=0.4,
                                       timestamp=1.0)],
        emotional_state=EmotionalState(frustration=0.2, patience=0.8, trust=0.5),
        outcome=CallOutcome.RESOLVED,
        abandonment_risk=0.1,
        next_action_distribution={"agent": 1.0},
    )


@pytest.mark.parametrize("enum_cls", ALL_ENUMS, ids=lambda c: c.__name__)
def test_every_enum_is_a_row_enum(enum_cls):
    """A plain Enum in a row shape is the defect this suite exists to stop.
    New enums inherit the guarantee by inheriting the base, and this fails if
    one is added without it."""
    assert issubclass(enum_cls, RowEnum), f"{enum_cls.__name__} must subclass RowEnum"
    assert issubclass(enum_cls, str)


@pytest.mark.parametrize("enum_cls", ALL_ENUMS, ids=lambda c: c.__name__)
def test_enum_text_is_its_value_on_every_python(enum_cls):
    """str, format and json agree with the value, identically on 3.10-3.13."""
    for member in enum_cls:
        assert str(member) == member.value
        assert f"{member}" == member.value
        assert format(member) == member.value
        assert json.dumps(member) == json.dumps(member.value)
        assert member == member.value


def test_the_percept_that_could_not_be_serialised():
    """The 0.2.0 bug, as a test. `json.dumps(asdict(percept))` raised
    TypeError because CallOutcome was a plain Enum."""
    blob = json.dumps(asdict(_percept()))
    assert json.loads(blob)["outcome"] == "resolved"


def test_every_row_round_trips_through_json():
    rows = [
        _percept(),
        FrictionEvent(node="n", type="t", severity=0.1, timestamp=2.0),
        EmotionalState(frustration=0.1, patience=0.2, trust=0.3),
        CallerState(caller_id="c", intent="billing", emotion="calm"),
        DynamicState(),
        KernelMetadata(name="k", version="1", description="d",
                       domain=ExecutionDomain.ROUTING),
        IdentityContext(tenant_id="t", subject_id="s", roles=("agent",),
                        trust_level=TrustLevel.VERIFIED,
                        authentication_method="token", verified=True,
                        signature="sig"),
        RoutingDecision(queue=QueueType.FAST_PATH, reason="low confidence"),
    ]
    for row in rows:
        blob = json.dumps(asdict(row))
        assert json.loads(blob) is not None, type(row).__name__


def test_caller_state_keeps_its_own_promise():
    """`cns.caller` states "Serialization is strictly JSON-compatible".
    That is a claim about this package, so it gets an assertion."""
    state = CallerState(caller_id="c", intent="billing", emotion="calm")
    assert json.loads(json.dumps(state.snapshot()))["next_node"] == "root"


def test_no_row_shape_carries_a_bare_enum():
    """Catches the original defect structurally rather than by enumeration:
    any annotation in a CNS row that resolves to a plain Enum fails here."""
    import cns
    import importlib
    import pkgutil
    for info in pkgutil.walk_packages(cns.__path__, "cns."):
        mod = importlib.import_module(info.name)
        for name in getattr(mod, "__all__", []):
            obj = getattr(mod, name)
            if not isinstance(obj, type) or not issubclass(obj, Enum):
                continue
            assert issubclass(obj, RowEnum), (
                f"{info.name}.{name} is an Enum that is not a RowEnum; it "
                f"cannot be serialised and will not compare equal to its value")

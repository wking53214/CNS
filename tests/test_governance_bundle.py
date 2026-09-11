"""The second bundle: perception, caller, governance. Shapes and the
constructor forms their consumers already use."""
from dataclasses import FrozenInstanceError, fields

import pytest

from cns.caller import CallerState, DynamicState
from cns.governance import (ExecutionDomain, GovernanceError, IdentityContext, IntentCategory,
                            KernelComponent, KernelMetadata, PolicyViolation, QueueType,
                            RoutingDecision, TrustLevel, ValidationError)
from cns.perception import CallOutcome, CallPercept, EmotionalState, FrictionEvent


def test_perception_rows_keep_their_field_order():
    assert [f.name for f in fields(FrictionEvent)] == ["node", "type", "severity", "timestamp"]
    assert [f.name for f in fields(CallPercept)] == ["caller_id", "journey", "friction_events",
                                                     "emotional_state", "outcome", "abandonment_risk",
                                                     "next_action_distribution"]
    assert {o.value for o in CallOutcome} == {"resolved", "abandoned", "escalated", "in_progress"}


def test_emotional_state_deteriorating_is_the_rule_it_was():
    assert EmotionalState(frustration=0.8, patience=0.5, trust=1.0).deteriorating()
    assert EmotionalState(frustration=0.1, patience=0.1, trust=1.0).deteriorating()
    assert not EmotionalState(frustration=0.5, patience=0.5, trust=0.0).deteriorating()


def test_caller_state_defaults_and_snapshot_shape():
    s = CallerState(caller_id="c1", intent="billing", emotion="calm")
    assert s.next_node == "root" and s.latent is None and isinstance(s.dynamic, DynamicState)
    snap = s.snapshot()
    assert set(snap) == {"caller_id", "intent", "emotion", "posterior", "dynamic", "latent", "next_node"}
    assert snap["dynamic"] == {"perceived_wait": 0.0, "frustration": 0.0}
    assert s.to_dict() == snap


def test_governance_enums_are_string_enums():
    assert ExecutionDomain.AI == "ai" and TrustLevel.VERIFIED == "verified"
    assert IntentCategory.HARDSHIP == "hardship" and QueueType.SPECIALIST == "specialist"


def test_governance_rows_are_frozen():
    m = KernelMetadata(name="k", version="1", description="d", domain=ExecutionDomain.ROUTING)
    with pytest.raises(FrozenInstanceError):
        m.name = "x"
    i = IdentityContext(tenant_id="t", subject_id="s", roles=("agent",), trust_level=TrustLevel.LOW,
                        authentication_method="pin", verified=True, signature="sig")
    assert i.roles == ("agent",)
    assert RoutingDecision(queue=QueueType.UNCERTAINTY, reason="low confidence").queue is QueueType.UNCERTAINTY


def test_the_exception_family_has_one_root():
    for exc in (ValidationError, PolicyViolation):
        assert issubclass(exc, GovernanceError)
    with pytest.raises(GovernanceError):
        raise ValidationError("bad")


def test_kernel_component_is_still_a_hollow_seam():
    """Kept as found. Its consumers decide whether it becomes an ABC."""
    with pytest.raises(NotImplementedError):
        KernelComponent().metadata

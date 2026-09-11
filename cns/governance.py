"""CONFIDENTIAL. Trade secret of William King (wking53214). Recorded 2026-09-11.
See README.md. Do not copy, publish, vendor, or disclose.

cns.governance: the governance kernel's contracts.

Extracted 2026-09-11 from GSA_Governance_Operating_Core_Enterprise.py.
GSA-815 and OBSERVE agree on every one of these (OBSERVE carries the
file twice, as GSA.py and under its full name); Ecology's copies had
diverged. The kernel's behaviour (PolicyDecisionPoint,
HumanApprovalWorkflow, OutputGovernanceGate, the fabrics and engines)
stays where it is; these are the enums, exceptions and frozen rows it
speaks in.

KernelComponent is kept as it was found: a hollow seam whose `metadata`
raises NotImplementedError. Turning it into an ABC would change what
can be instantiated, and that is a decision for its consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from cns.rowenum import RowEnum

__all__ = ["ExecutionDomain", "TrustLevel", "GovernanceError", "IntegrityError", "ValidationError", "AuthorizationError", "RoutingError", "PolicyViolation", "KernelMetadata", "KernelComponent", "IdentityContext", "IntentCategory", "QueueType", "RoutingDecision"]

class ExecutionDomain(RowEnum):
    AI = 'ai'
    DATA = 'data'
    ROUTING = 'routing'
    OPERATIONAL = 'operational'


class TrustLevel(RowEnum):
    UNKNOWN = 'unknown'
    LOW = 'low'
    VERIFIED = 'verified'
    PRIVILEGED = 'privileged'


class GovernanceError(Exception):
    pass


class IntegrityError(GovernanceError):
    pass


class ValidationError(GovernanceError):
    pass


class AuthorizationError(GovernanceError):
    pass


class RoutingError(GovernanceError):
    pass


class PolicyViolation(GovernanceError):
    pass


@dataclass(frozen=True, slots=True)
class KernelMetadata:
    name: str
    version: str
    description: str
    domain: ExecutionDomain


class KernelComponent:

    @property
    def metadata(self) -> KernelMetadata:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class IdentityContext:
    tenant_id: str
    subject_id: str
    roles: Tuple[str, ...]
    trust_level: TrustLevel
    authentication_method: str
    verified: bool
    signature: str


class IntentCategory(RowEnum):
    STATUS = 'status'
    PAYMENT = 'payment'
    DOCUMENTS = 'documents'
    ESCALATION = 'escalation'
    HARDSHIP = 'hardship'


class QueueType(RowEnum):
    FAST_PATH = 'fast_path'
    UNCERTAINTY = 'uncertainty'
    SPECIALIST = 'specialist'


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    queue: QueueType
    reason: str

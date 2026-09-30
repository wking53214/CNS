"""CONFIDENTIAL. Trade secret of William King (wking53214). Recorded 2026-09-11.
See README.md. Do not copy, publish, vendor, or disclose.

HERALD as pure translation gate — no logic, only outcome mapping.

Maps between:
- SWIZZLE Verdict enum
- Innovation OS lifecycle decisions
- ghost_tools Status/Severity outcomes
- CNS GateChain/GateOutcome canonical form

Translation is bidirectional and idempotent. No policy decisions,
no filtering, no new logic. HERALD is transparent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

from cns.gate import GateOutcome, GatePosition, GateResult, subject_digest


# ============================================================================
# OUTCOME MODEL MAPPINGS
# ============================================================================

class SwizzleVerdict(str, Enum):
    """From SWIZZLE verdict.py"""
    BANISHED = "banished"      # exact match → PASS
    MISNAMED = "misnamed"      # partial match → RETRY
    ESCAPED = "escaped"        # nothing found → TERMINAL_BREACH
    CONJURED = "conjured"      # false positive → TERMINAL_BREACH
    DISMISSED = "dismissed"    # correct silence → PASS
    UNSUMMONED = "unsummoned"  # test failure → TERMINAL_BREACH


class InnovationOSDecision(str, Enum):
    """From Innovation OS lifecycle"""
    PROPOSED = "proposed"      # AI generated → pending
    EVALUATED = "evaluated"    # system assessed → advisory
    APPROVED = "approved"      # human authorized → PASS
    REJECTED = "rejected"      # failed evaluation → TERMINAL_BREACH
    BRANCHED = "branched"      # alternative path → RETRY


class GhostToolsStatus(str, Enum):
    """From ghost_tools outcome model"""
    PASS = "pass"              # check passed → PASS
    FINDING = "finding"        # defect found → TERMINAL_BREACH
    SKIPPED = "skipped"        # excluded → RETRY
    UNSUMMONED = "unsummoned"  # test failure → TERMINAL_BREACH


# ============================================================================
# TRANSLATION GATE — PURE PASS-THROUGH
# ============================================================================

@dataclass(frozen=True)
class HeraldTranslation:
    """One outcome translated to canonical GateOutcome form.

    Preserves all metadata. Changes only representation.
    Never filters, transforms, or decides.
    """

    source_system: str           # "swizzle" | "innovation_os" | "ghost_tools"
    source_verdict: str          # original verdict/decision/status
    canonical_outcome: GateOutcome
    subject: Optional[Any] = None
    subject_hash: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})


def translate_swizzle_to_canonical(
    verdict: str,
    warp_name: str,
    findings: tuple = (),
    proof_holds: bool = False,
) -> HeraldTranslation:
    """SWIZZLE verdict → GateOutcome with all metadata preserved."""

    mapping = {
        SwizzleVerdict.BANISHED.value: GateOutcome.PASS,
        SwizzleVerdict.MISNAMED.value: GateOutcome.RETRY,
        SwizzleVerdict.ESCAPED.value: GateOutcome.TERMINAL_BREACH,
        SwizzleVerdict.CONJURED.value: GateOutcome.TERMINAL_BREACH,
        SwizzleVerdict.DISMISSED.value: GateOutcome.PASS,
        SwizzleVerdict.UNSUMMONED.value: GateOutcome.TERMINAL_BREACH,
    }

    outcome = mapping.get(verdict, GateOutcome.TERMINAL_BREACH)
    subject_hash = subject_digest({
        "warp": warp_name,
        "findings": findings,
        "proof_holds": proof_holds,
    })

    return HeraldTranslation(
        source_system="swizzle",
        source_verdict=verdict,
        canonical_outcome=outcome,
        subject={"warp": warp_name, "findings": findings},
        subject_hash=subject_hash,
        metadata={
            "proof_holds": proof_holds,
            "finding_count": len(findings),
        },
    )


def translate_innovation_os_to_canonical(
    decision: str,
    problem_id: str,
    idea_id: str,
    evaluation_score: Optional[float] = None,
    authorization_required: bool = False,
) -> HeraldTranslation:
    """Innovation OS lifecycle decision → GateOutcome with all metadata preserved."""

    mapping = {
        InnovationOSDecision.PROPOSED.value: GateOutcome.RETRY,      # pending human eval
        InnovationOSDecision.EVALUATED.value: GateOutcome.RETRY,     # waiting for approval
        InnovationOSDecision.APPROVED.value: GateOutcome.PASS,       # authorized
        InnovationOSDecision.REJECTED.value: GateOutcome.TERMINAL_BREACH,
        InnovationOSDecision.BRANCHED.value: GateOutcome.RETRY,      # alternative path
    }

    outcome = mapping.get(decision, GateOutcome.TERMINAL_BREACH)
    subject_hash = subject_digest({
        "problem": problem_id,
        "idea": idea_id,
        "decision": decision,
        "score": evaluation_score,
    })

    return HeraldTranslation(
        source_system="innovation_os",
        source_verdict=decision,
        canonical_outcome=outcome,
        subject={"problem": problem_id, "idea": idea_id},
        subject_hash=subject_hash,
        metadata={
            "evaluation_score": evaluation_score,
            "authorization_required": authorization_required,
        },
    )


def translate_ghost_tools_to_canonical(
    status: str,
    file_modified: str,
    lines_changed: int,
    severity: Optional[str] = None,
) -> HeraldTranslation:
    """ghost_tools outcome → GateOutcome with all metadata preserved."""

    mapping = {
        GhostToolsStatus.PASS.value: GateOutcome.PASS,
        GhostToolsStatus.FINDING.value: GateOutcome.TERMINAL_BREACH,
        GhostToolsStatus.SKIPPED.value: GateOutcome.RETRY,
        GhostToolsStatus.UNSUMMONED.value: GateOutcome.TERMINAL_BREACH,
    }

    outcome = mapping.get(status, GateOutcome.TERMINAL_BREACH)
    subject_hash = subject_digest({
        "file": file_modified,
        "status": status,
        "lines": lines_changed,
        "severity": severity,
    })

    return HeraldTranslation(
        source_system="ghost_tools",
        source_verdict=status,
        canonical_outcome=outcome,
        subject={"file": file_modified, "lines_changed": lines_changed},
        subject_hash=subject_hash,
        metadata={
            "severity": severity,
            "lines_changed": lines_changed,
        },
    )


def translate_canonical_to_swizzle(
    outcome: GateOutcome,
    subject_hash: str,
) -> str:
    """Canonical GateOutcome → SWIZZLE verdict for re-testing."""

    reverse_mapping = {
        GateOutcome.PASS: SwizzleVerdict.BANISHED.value,
        GateOutcome.RETRY: SwizzleVerdict.MISNAMED.value,
        GateOutcome.TERMINAL_BREACH: SwizzleVerdict.ESCAPED.value,
    }

    return reverse_mapping.get(outcome, SwizzleVerdict.UNSUMMONED.value)


def translate_canonical_to_innovation_os(
    outcome: GateOutcome,
    subject_hash: str,
) -> str:
    """Canonical GateOutcome → Innovation OS decision for next cycle."""

    reverse_mapping = {
        GateOutcome.PASS: InnovationOSDecision.APPROVED.value,
        GateOutcome.RETRY: InnovationOSDecision.BRANCHED.value,
        GateOutcome.TERMINAL_BREACH: InnovationOSDecision.REJECTED.value,
    }

    return reverse_mapping.get(outcome, InnovationOSDecision.REJECTED.value)


def translate_canonical_to_ghost_tools(
    outcome: GateOutcome,
    subject_hash: str,
) -> str:
    """Canonical GateOutcome → ghost_tools status for fixing."""

    reverse_mapping = {
        GateOutcome.PASS: GhostToolsStatus.PASS.value,
        GateOutcome.RETRY: GhostToolsStatus.SKIPPED.value,
        GateOutcome.TERMINAL_BREACH: GhostToolsStatus.FINDING.value,
    }

    return reverse_mapping.get(outcome, GhostToolsStatus.UNSUMMONED.value)


# ============================================================================
# COMPOSITION CONTRACT
# ============================================================================

@dataclass(frozen=True)
class HeraldCompositionResult:
    """One full cycle through the composition.

    Tracks what each system did and the overall verdict.
    """

    cycle: int
    swizzle_verdict: Optional[str]
    innovation_os_decision: Optional[str]
    ghost_tools_status: Optional[str]
    canonical_flow: list[HeraldTranslation]
    overall_outcome: GateOutcome

    def all_pass(self) -> bool:
        """Whether cycle achieved PASS in canonical form."""
        return all(t.canonical_outcome == GateOutcome.PASS for t in self.canonical_flow)

    def any_breach(self) -> bool:
        """Whether cycle hit TERMINAL_BREACH in canonical form."""
        return any(t.canonical_outcome == GateOutcome.TERMINAL_BREACH for t in self.canonical_flow)

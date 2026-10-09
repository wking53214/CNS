"""Composition orchestrator for SWIZZLE, ghost_tools, and WIZZLE.

One unified interface to chain systems without needing HERALD unless a semantic
gap is unavoidable. Translates only at system boundaries where outcome models differ.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from cns.gate import GateOutcome, subject_digest


class SystemName(str, Enum):
    """The three systems in the composition."""
    SWIZZLE = "swizzle"
    GHOST_TOOLS = "ghost_tools"
    WIZZLE = "wizzle"


@dataclass(frozen=True)
class CompositionStep:
    """One system's execution in the composition."""

    system: SystemName
    input_outcome: Optional[str] = None  # outcome from previous step, if any
    output_outcome: Optional[str] = None  # verdict/decision/status produced
    metadata: Dict[str, Any] = None
    subject_hash: Optional[str] = None  # what this step is judging


@dataclass(frozen=True)
class CompositionTrace:
    """Full execution trace of a multi-system composition."""

    steps: List[CompositionStep]
    overall_outcome: GateOutcome  # final canonical outcome
    converged: bool  # did all systems agree?
    cycle: int = 1

    def timeline(self) -> str:
        """Human-readable timeline of the composition."""
        lines = [f"Cycle {self.cycle}:"]
        for i, step in enumerate(self.steps, 1):
            inp = f" ← {step.input_outcome}" if step.input_outcome else ""
            out = f" → {step.output_outcome}" if step.output_outcome else ""
            lines.append(f"  {i}. {step.system.value}{inp}{out}")
        lines.append(f"  Overall: {self.overall_outcome.value}")
        return "\n".join(lines)


class Composer:
    """Orchestrates composition of SWIZZLE, ghost_tools, and WIZZLE.

    Usage:
        composer = Composer()
        trace = composer.run_cycle(
            composition=[SystemName.SWIZZLE, SystemName.GHOST_TOOLS, SystemName.SWIZZLE],
            subject={"repo": "example_repo", "commit": "abc123"}
        )
    """

    def __init__(self):
        self.steps: List[CompositionStep] = []

    def run_cycle(
        self,
        composition: List[SystemName],
        subject: Dict[str, Any],
        cycle: int = 1,
    ) -> CompositionTrace:
        """Execute one full composition cycle.

        Args:
            composition: List of systems to invoke in order
            subject: What we're judging (repo, commit, idea, etc.)
            cycle: Which cycle this is (for tracking)

        Returns:
            Full trace of the composition with all verdicts.
        """
        self.steps = []
        subject_hash = subject_digest(subject)
        previous_outcome = None

        for system in composition:
            step = self._invoke_system(
                system,
                subject=subject,
                subject_hash=subject_hash,
                input_outcome=previous_outcome,
            )
            self.steps.append(step)
            previous_outcome = step.output_outcome

        # Determine overall outcome based on final step
        final_outcome = self._canonicalize_final_outcome(self.steps[-1])
        converged = self._check_convergence(self.steps)

        return CompositionTrace(
            steps=self.steps,
            overall_outcome=final_outcome,
            converged=converged,
            cycle=cycle,
        )

    def _invoke_system(
        self,
        system: SystemName,
        subject: Dict[str, Any],
        subject_hash: str,
        input_outcome: Optional[str],
    ) -> CompositionStep:
        """Invoke one system and return its step in the composition."""

        if system == SystemName.SWIZZLE:
            return self._invoke_swizzle(subject, subject_hash, input_outcome)
        elif system == SystemName.GHOST_TOOLS:
            return self._invoke_ghost_tools(subject, subject_hash, input_outcome)
        elif system == SystemName.WIZZLE:
            return self._invoke_wizzle(subject, subject_hash, input_outcome)
        else:
            raise ValueError(f"Unknown system: {system}")

    def _invoke_swizzle(
        self,
        subject: Dict[str, Any],
        subject_hash: str,
        input_outcome: Optional[str],
    ) -> CompositionStep:
        """SWIZZLE: adversarial test framework.

        If input_outcome exists, SWIZZLE retests after a fix.
        Otherwise, SWIZZLE runs initial test.

        Output: Verdict (BANISHED/ESCAPED/MISNAMED/CONJURED/DISMISSED/UNSUMMONED)
        """
        # In real execution, this would invoke SWIZZLE's run_warp or run_all
        # For now, return a stub that captures the interface
        verdict = "escaped"  # placeholder; would be determined by actual SWIZZLE run

        return CompositionStep(
            system=SystemName.SWIZZLE,
            input_outcome=input_outcome,
            output_outcome=verdict,
            subject_hash=subject_hash,
            metadata={"subject": subject, "retest": input_outcome is not None},
        )

    def _invoke_ghost_tools(
        self,
        subject: Dict[str, Any],
        subject_hash: str,
        input_outcome: Optional[str],
    ) -> CompositionStep:
        """ghost_tools: code scanner and fixer.

        Scans subject and produces findings with Status (CONFIRMED/REASONED/etc.)
        and Severity (CRITICAL/MAJOR/MINOR/INFORMATIONAL).

        Output: Status (or abstracted to common gate language)
        """
        # In real execution, this would invoke ghost_buster.cli
        # For now, return a stub
        status = "confirmed"  # placeholder

        return CompositionStep(
            system=SystemName.GHOST_TOOLS,
            input_outcome=input_outcome,
            output_outcome=status,
            subject_hash=subject_hash,
            metadata={"subject": subject, "scan_type": "mechanical"},
        )

    def _invoke_wizzle(
        self,
        subject: Dict[str, Any],
        subject_hash: str,
        input_outcome: Optional[str],
    ) -> CompositionStep:
        """WIZZLE: forensics edge-case test fixture.

        Tests ghost_tools's forensics layer for semantic correctness.
        Produces forensics classification (REMOVED_FROM_LIBRARY, RELOCATED_TO_TESTS, etc.)

        Output: Forensics verdict
        """
        # In real execution, this would run WIZZLE's forensics tests
        forensics_verdict = "removed_from_library"  # placeholder

        return CompositionStep(
            system=SystemName.WIZZLE,
            input_outcome=input_outcome,
            output_outcome=forensics_verdict,
            subject_hash=subject_hash,
            metadata={"subject": subject, "forensics_layer": True},
        )

    def _canonicalize_final_outcome(self, final_step: CompositionStep) -> GateOutcome:
        """Convert final step's outcome to canonical GateOutcome.

        This is the one place where everything converges to CNS primitives.
        """
        outcome = final_step.output_outcome or "unknown"

        # SWIZZLE verdicts
        if final_step.system == SystemName.SWIZZLE:
            if outcome in ("banished", "dismissed"):
                return GateOutcome.PASS
            elif outcome in ("escaped", "conjured"):
                return GateOutcome.TERMINAL_BREACH
            elif outcome in ("misnamed", "unsummoned"):
                return GateOutcome.RETRY

        # ghost_tools status
        elif final_step.system == SystemName.GHOST_TOOLS:
            if outcome == "confirmed":
                return GateOutcome.PASS
            elif outcome in ("reasoned", "rejected"):
                return GateOutcome.TERMINAL_BREACH
            elif outcome == "suppressed":
                return GateOutcome.RETRY

        # WIZZLE forensics
        elif final_step.system == SystemName.WIZZLE:
            if outcome in ("relocated_to_tests", "intentional_removal"):
                return GateOutcome.PASS
            elif outcome in ("removed_from_library", "regression"):
                return GateOutcome.TERMINAL_BREACH
            elif outcome == "unknown":
                return GateOutcome.RETRY

        # Fallback
        return GateOutcome.TERMINAL_BREACH

    def _check_convergence(self, steps: List[CompositionStep]) -> bool:
        """Did all systems agree on the final outcome?"""
        if not steps or len(steps) < 2:
            return True  # single system always "converges"

        # All steps should have same subject_hash
        if not all(s.subject_hash == steps[0].subject_hash for s in steps):
            return False

        # Heuristic: convergence means final outcome matches pattern
        final_outcome = self._canonicalize_final_outcome(steps[-1])
        return final_outcome != GateOutcome.RETRY  # RETRY means we're still exploring

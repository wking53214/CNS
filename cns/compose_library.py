"""Generic composition orchestrator for entire library.

Discovers systems across 67 repos, builds composition graphs,
and routes outcomes through compatible chains without universal translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from abc import ABC, abstractmethod

from .gate import GateOutcome, subject_digest


class SystemModel(str, Enum):
    """Outcome model signatures across library."""
    SWIZZLE_VERDICT = "swizzle_verdict"  # BANISHED/ESCAPED/MISNAMED/CONJURED/DISMISSED/UNSUMMONED
    GHOST_TOOLS_STATUS = "ghost_tools_status"  # CONFIRMED/REASONED/CONFIRMED_BY_REVIEW/REJECTED/SUPPRESSED
    GHOST_TOOLS_SEVERITY = "ghost_tools_severity"  # CRITICAL/MAJOR/MINOR/INFORMATIONAL
    WIZZLE_FORENSICS = "wizzle_forensics"  # REMOVED_FROM_LIBRARY/RELOCATED_TO_TESTS/REGRESSION/UNKNOWN
    INNOVATION_OS_DECISION = "innovation_os_decision"  # PROPOSED/EVALUATED/APPROVED/REJECTED/BRANCHED
    CNS_GATE_OUTCOME = "cns_gate_outcome"  # PASS/RETRY/TERMINAL_BREACH (canonical)


@dataclass
class SystemAdapter(ABC):
    """Base adapter for any system in the library.

    Each repo that wants to participate in composition provides an adapter
    that declares its input/output models and execution interface.
    """

    system_name: str
    input_models: Set[SystemModel]  # what this system accepts
    output_model: SystemModel  # what this system produces

    @abstractmethod
    def invoke(
        self,
        subject: Dict[str, Any],
        input_outcome: Optional[str] = None,
    ) -> str:
        """Execute this system and return outcome as string.

        Args:
            subject: What we're judging
            input_outcome: Previous system's outcome (if this is not first in chain)

        Returns:
            Outcome string in this system's native format
        """
        pass


@dataclass
class CompositionLink:
    """One edge in composition graph: system A outputs to system B."""

    from_system: str
    to_system: str
    translation_rule: Optional[Callable[[str], str]] = None  # None = direct passthrough


@dataclass(frozen=True)
class CompositionStep:
    """One system's execution in the composition."""

    system_name: str
    input_outcome: Optional[str] = None
    output_outcome: Optional[str] = None
    output_model: SystemModel = SystemModel.CNS_GATE_OUTCOME
    metadata: Dict[str, Any] = field(default_factory=dict)
    subject_hash: Optional[str] = None


@dataclass(frozen=True)
class CompositionTrace:
    """Full execution trace through library systems."""

    steps: List[CompositionStep]
    overall_outcome: GateOutcome
    composition_path: List[str]  # system names in order
    cycle: int = 1
    converged: bool = False

    def timeline(self) -> str:
        """Human-readable timeline."""
        lines = [f"Cycle {self.cycle}: {' → '.join(self.composition_path)}"]
        for i, step in enumerate(self.steps, 1):
            inp = f" ← {step.input_outcome}" if step.input_outcome else ""
            out = f" → {step.output_outcome}" if step.output_outcome else ""
            lines.append(f"  {i}. {step.system_name}{inp}{out}")
        lines.append(f"  Final: {self.overall_outcome.value}")
        return "\n".join(lines)


class LibraryComposer:
    """Orchestrates composition across entire library.

    - Discovers systems and their outcome models
    - Builds compatibility graphs
    - Routes outcomes through compatible chains
    - Translates only where models differ
    """

    def __init__(self):
        self.adapters: Dict[str, SystemAdapter] = {}
        self.translation_rules: Dict[Tuple[SystemModel, SystemModel], Callable[[str], str]] = {}
        self._build_compatibility_graph()

    def register_adapter(self, adapter: SystemAdapter) -> None:
        """Register a system adapter from the library."""
        self.adapters[adapter.system_name] = adapter
        self._build_compatibility_graph()  # Rebuild graph after each registration

    def register_translation(
        self,
        from_model: SystemModel,
        to_model: SystemModel,
        rule: Callable[[str], str],
    ) -> None:
        """Register translation rule between two outcome models."""
        self.translation_rules[(from_model, to_model)] = rule

    def _build_compatibility_graph(self) -> None:
        """Build graph of which systems can feed into which."""
        self.graph: Dict[str, Set[str]] = {
            name: set() for name in self.adapters.keys()
        }

        for from_name, from_adapter in self.adapters.items():
            for to_name, to_adapter in self.adapters.items():
                if from_name == to_name:
                    continue
                # Can from_adapter → to_adapter?
                if from_adapter.output_model in to_adapter.input_models:
                    self.graph[from_name].add(to_name)

    def find_composition_path(
        self,
        start_system: str,
        end_system: str,
        max_depth: int = 5,
    ) -> Optional[List[str]]:
        """Find shortest composition path from start to end system.

        Returns list of system names in order, or None if no path exists.
        """
        if start_system not in self.adapters or end_system not in self.adapters:
            return None

        visited = {start_system}
        queue = [(start_system, [start_system])]

        while queue:
            current, path = queue.pop(0)
            if current == end_system:
                return path
            if len(path) >= max_depth:
                continue

            for neighbor in self.graph.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def compose(
        self,
        composition_path: List[str],
        subject: Dict[str, Any],
        cycle: int = 1,
    ) -> CompositionTrace:
        """Execute composition along specified path.

        Args:
            composition_path: List of system names to chain
            subject: What we're judging
            cycle: Which cycle this is

        Returns:
            Full trace of execution
        """
        if not composition_path:
            raise ValueError("Empty composition path")

        for system_name in composition_path:
            if system_name not in self.adapters:
                raise ValueError(f"Unknown system: {system_name}")

        steps: List[CompositionStep] = []
        subject_hash = subject_digest(subject)
        previous_outcome = None

        for system_name in composition_path:
            adapter = self.adapters[system_name]

            # Invoke system
            outcome = adapter.invoke(subject, input_outcome=previous_outcome)

            # Translate if needed
            if previous_outcome and steps:
                from_model = steps[-1].output_model
                to_model = adapter.input_models.pop()  # first compatible model
                if from_model != to_model:
                    outcome = self._translate(outcome, from_model, to_model)

            step = CompositionStep(
                system_name=system_name,
                input_outcome=previous_outcome,
                output_outcome=outcome,
                output_model=adapter.output_model,
                subject_hash=subject_hash,
            )
            steps.append(step)
            previous_outcome = outcome

        # Canonicalize final outcome
        final_outcome = self._canonicalize(steps[-1])
        converged = self._check_convergence(steps)

        return CompositionTrace(
            steps=steps,
            overall_outcome=final_outcome,
            composition_path=composition_path,
            cycle=cycle,
            converged=converged,
        )

    def _translate(
        self,
        outcome: str,
        from_model: SystemModel,
        to_model: SystemModel,
    ) -> str:
        """Translate outcome between models using registered rules."""
        rule = self.translation_rules.get((from_model, to_model))
        if rule:
            return rule(outcome)
        # Fallback: no translation registered
        return outcome

    def _canonicalize(self, final_step: CompositionStep) -> GateOutcome:
        """Convert final outcome to canonical GateOutcome."""
        outcome = final_step.output_outcome or "unknown"
        model = final_step.output_model

        # Already canonical
        if model == SystemModel.CNS_GATE_OUTCOME:
            if outcome == "pass":
                return GateOutcome.PASS
            elif outcome == "terminal_breach":
                return GateOutcome.TERMINAL_BREACH
            elif outcome == "retry":
                return GateOutcome.RETRY

        # SWIZZLE verdicts
        elif model == SystemModel.SWIZZLE_VERDICT:
            if outcome in ("banished", "dismissed"):
                return GateOutcome.PASS
            elif outcome in ("escaped", "conjured"):
                return GateOutcome.TERMINAL_BREACH
            else:
                return GateOutcome.RETRY

        # ghost_tools status
        elif model == SystemModel.GHOST_TOOLS_STATUS:
            if outcome == "confirmed":
                return GateOutcome.PASS
            elif outcome in ("reasoned", "rejected"):
                return GateOutcome.TERMINAL_BREACH
            else:
                return GateOutcome.RETRY

        # ghost_tools severity (meta)
        elif model == SystemModel.GHOST_TOOLS_SEVERITY:
            if outcome == "critical":
                return GateOutcome.TERMINAL_BREACH
            elif outcome == "major":
                return GateOutcome.TERMINAL_BREACH
            elif outcome in ("minor", "informational"):
                return GateOutcome.PASS
            else:
                return GateOutcome.RETRY

        # WIZZLE forensics
        elif model == SystemModel.WIZZLE_FORENSICS:
            if outcome in ("relocated_to_tests", "intentional_removal"):
                return GateOutcome.PASS
            elif outcome in ("removed_from_library", "regression"):
                return GateOutcome.TERMINAL_BREACH
            else:
                return GateOutcome.RETRY

        # Innovation OS decisions
        elif model == SystemModel.INNOVATION_OS_DECISION:
            if outcome == "approved":
                return GateOutcome.PASS
            elif outcome == "rejected":
                return GateOutcome.TERMINAL_BREACH
            else:
                return GateOutcome.RETRY

        # Fallback
        return GateOutcome.TERMINAL_BREACH

    def _check_convergence(self, steps: List[CompositionStep]) -> bool:
        """Did composition converge to a decision?"""
        if len(steps) < 2:
            return True
        # Convergence: final outcome is PASS or TERMINAL_BREACH (not RETRY)
        final = self._canonicalize(steps[-1])
        return final != GateOutcome.RETRY


class CompositionBuilder:
    """Fluent API for building complex compositions."""

    def __init__(self, composer: LibraryComposer):
        self.composer = composer
        self.path: List[str] = []

    def add_system(self, system_name: str) -> CompositionBuilder:
        """Add system to composition path."""
        if system_name in self.composer.adapters:
            self.path.append(system_name)
        else:
            raise ValueError(f"System not registered: {system_name}")
        return self

    def build(self) -> List[str]:
        """Return the composition path."""
        return self.path

    def execute(
        self,
        subject: Dict[str, Any],
        cycle: int = 1,
    ) -> CompositionTrace:
        """Execute the composition."""
        return self.composer.compose(self.path, subject, cycle)

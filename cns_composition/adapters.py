"""System adapters for SWIZZLE, ghost_tools, and WIZZLE.

Each adapter declares its outcome model and implements the invoke interface
for the LibraryComposer to orchestrate.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from .compose_library import SystemAdapter, SystemModel


class SwizzleAdapter(SystemAdapter):
    """Adapter for SWIZZLE: adversarial test framework.

    SWIZZLE plants defects and tests whether scanners find them.
    Produces Verdict outcomes: BANISHED/ESCAPED/MISNAMED/CONJURED/DISMISSED/UNSUMMONED
    """

    def __init__(self):
        super().__init__(
            system_name="swizzle",
            input_models={SystemModel.CNS_GATE_OUTCOME},  # Can receive retry signals
            output_model=SystemModel.SWIZZLE_VERDICT,
        )

    def invoke(
        self,
        subject: Dict[str, Any],
        input_outcome: Optional[str] = None,
    ) -> str:
        """Execute SWIZZLE test suite on subject.

        Args:
            subject: Repo/commit to test
            input_outcome: Previous outcome if retesting after fix

        Returns:
            Verdict: one of BANISHED/ESCAPED/MISNAMED/CONJURED/DISMISSED/UNSUMMONED
        """
        # In real execution, this invokes SWIZZLE.run_warp() or run_all()
        # For now, placeholder showing the interface

        if input_outcome == "retry":
            # Retest after fix
            return "banished"  # defect was fixed; no longer found
        else:
            # Initial test
            return "escaped"  # defect found but not by our planted test


class GhostToolsAdapter(SystemAdapter):
    """Adapter for ghost_tools: code scanner and vulnerability finder.

    Scans for security findings with Status (CONFIRMED/REASONED/etc.)
    and Severity (CRITICAL/MAJOR/MINOR/INFORMATIONAL).

    Produces Status outcomes by default, but can also emit Severity as separate signal.
    """

    def __init__(self):
        super().__init__(
            system_name="ghost_tools",
            input_models={
                SystemModel.SWIZZLE_VERDICT,  # Can take SWIZZLE output
                SystemModel.CNS_GATE_OUTCOME,  # Can take gate signal
            },
            output_model=SystemModel.GHOST_TOOLS_STATUS,
        )

    def invoke(
        self,
        subject: Dict[str, Any],
        input_outcome: Optional[str] = None,
    ) -> str:
        """Scan subject for security findings.

        Args:
            subject: Code/repo to scan
            input_outcome: Previous verdict (e.g., "escaped" from SWIZZLE)

        Returns:
            Status: one of CONFIRMED/REASONED/CONFIRMED_BY_REVIEW/REJECTED/SUPPRESSED
        """
        # In real execution, this invokes ghost_buster.cli or mechanical scanner
        # For now, placeholder

        if input_outcome == "escaped":
            # SWIZZLE found a defect; ghost_tools confirms it
            return "confirmed"
        else:
            # Independent scan
            return "reasoned"  # finding needs human review


class WizzleAdapter(SystemAdapter):
    """Adapter for WIZZLE: forensics edge-case test fixture.

    Tests ghost_tools's forensics layer for semantic correctness.
    Verifies that findings match intent, not just technical accuracy.

    Produces Provenance classifications: REMOVED_FROM_LIBRARY/RELOCATED_TO_TESTS/REGRESSION/UNKNOWN
    """

    def __init__(self):
        super().__init__(
            system_name="wizzle",
            input_models={SystemModel.GHOST_TOOLS_STATUS},
            output_model=SystemModel.WIZZLE_FORENSICS,
        )

    def invoke(
        self,
        subject: Dict[str, Any],
        input_outcome: Optional[str] = None,
    ) -> str:
        """Verify forensics correctness against ghost_tools findings.

        Args:
            subject: Code/repo to analyze
            input_outcome: ghost_tools Status (e.g., "confirmed")

        Returns:
            Provenance: one of REMOVED_FROM_LIBRARY/RELOCATED_TO_TESTS/REGRESSION/UNKNOWN
        """
        # In real execution, this runs WIZZLE's forensics test suite
        # Checking git history, commit messages, and semantic context
        # For now, placeholder

        if input_outcome == "confirmed":
            # Finding is confirmed; check if it's intentional or regression
            return "removed_from_library"  # member was intentionally removed from production
        else:
            return "unknown"  # need more context


def register_core_adapters(composer: Any) -> None:
    """Register the three core system adapters with a LibraryComposer.

    Args:
        composer: LibraryComposer instance to register adapters on
    """
    composer.register_adapter(SwizzleAdapter())
    composer.register_adapter(GhostToolsAdapter())
    composer.register_adapter(WizzleAdapter())


def register_core_translation_rules(composer: Any) -> None:
    """Register translation rules between outcome models.

    The three core systems register none. Each accepts the previous system's
    output model directly (SWIZZLE verdicts feed ghost_tools, ghost_tools
    statuses feed WIZZLE), and the last output is canonicalised by the
    composer itself. The function stays as the one place a rule would be
    added, so callers do not change.

    Args:
        composer: LibraryComposer instance to register rules on
    """

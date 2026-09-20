"""Tests for library-wide composition orchestrator.

Validates that SystemAdapter implementations work with LibraryComposer,
composition paths can be found and executed, and subject binding/convergence
work correctly across all systems.
"""

import pytest

from cns.compose_library import LibraryComposer, SystemModel
from cns.adapters import (
    register_core_adapters,
    register_core_translation_rules,
    SwizzleAdapter,
    GhostToolsAdapter,
    WizzleAdapter,
    InnovationOSAdapter,
)


class TestAdapterRegistration:
    """Verify adapters register correctly with LibraryComposer."""

    def test_swizzle_adapter_input_output_models(self):
        """SWIZZLE accepts gate outcome, produces verdict."""
        adapter = SwizzleAdapter()
        assert adapter.system_name == "swizzle"
        assert SystemModel.CNS_GATE_OUTCOME in adapter.input_models
        assert adapter.output_model == SystemModel.SWIZZLE_VERDICT

    def test_ghost_tools_adapter_input_output_models(self):
        """ghost_tools accepts verdict or gate, produces status."""
        adapter = GhostToolsAdapter()
        assert adapter.system_name == "ghost_tools"
        assert SystemModel.SWIZZLE_VERDICT in adapter.input_models
        assert SystemModel.CNS_GATE_OUTCOME in adapter.input_models
        assert adapter.output_model == SystemModel.GHOST_TOOLS_STATUS

    def test_wizzle_adapter_input_output_models(self):
        """WIZZLE accepts ghost_tools status, produces forensics."""
        adapter = WizzleAdapter()
        assert adapter.system_name == "wizzle"
        assert SystemModel.GHOST_TOOLS_STATUS in adapter.input_models
        assert adapter.output_model == SystemModel.WIZZLE_FORENSICS

    def test_innovation_os_adapter_input_output_models(self):
        """Innovation OS accepts multiple input models, produces decision."""
        adapter = InnovationOSAdapter()
        assert adapter.system_name == "innovation_os"
        assert SystemModel.SWIZZLE_VERDICT in adapter.input_models
        assert SystemModel.GHOST_TOOLS_STATUS in adapter.input_models
        assert SystemModel.WIZZLE_FORENSICS in adapter.input_models
        assert adapter.output_model == SystemModel.INNOVATION_OS_DECISION


class TestLibraryComposerIntegration:
    """Verify LibraryComposer works with core adapters."""

    @pytest.fixture
    def composer(self):
        """Set up composer with core adapters and translation rules."""
        c = LibraryComposer()
        register_core_adapters(c)
        register_core_translation_rules(c)
        return c

    def test_adapters_registered(self, composer):
        """All four core adapters are registered."""
        assert "swizzle" in composer.adapters
        assert "ghost_tools" in composer.adapters
        assert "wizzle" in composer.adapters
        assert "innovation_os" in composer.adapters

    def test_compatibility_graph_built(self, composer):
        """Compatibility graph reflects actual outcome model connections."""
        # SWIZZLE → ghost_tools (SWIZZLE_VERDICT in ghost_tools.input_models)
        assert "ghost_tools" in composer.graph.get("swizzle", set())

        # ghost_tools → WIZZLE (GHOST_TOOLS_STATUS in wizzle.input_models)
        assert "wizzle" in composer.graph.get("ghost_tools", set())

        # ghost_tools → Innovation OS (GHOST_TOOLS_STATUS in innovation_os.input_models)
        assert "innovation_os" in composer.graph.get("ghost_tools", set())

        # WIZZLE → Innovation OS (WIZZLE_FORENSICS in innovation_os.input_models)
        assert "innovation_os" in composer.graph.get("wizzle", set())

    def test_find_path_swizzle_to_innovation_os(self, composer):
        """Find path from SWIZZLE to Innovation OS."""
        path = composer.find_composition_path("swizzle", "innovation_os")
        assert path is not None
        assert path[0] == "swizzle"
        assert path[-1] == "innovation_os"
        # Should route through at least ghost_tools or directly if possible
        assert len(path) >= 2

    def test_find_path_ghost_tools_to_innovation_os(self, composer):
        """Find path from ghost_tools to Innovation OS."""
        path = composer.find_composition_path("ghost_tools", "innovation_os")
        assert path is not None
        assert "ghost_tools" in path
        assert "innovation_os" in path

    def test_find_path_circular(self, composer):
        """No circular paths from SWIZZLE back to SWIZZLE."""
        path = composer.find_composition_path("swizzle", "swizzle")
        # BFS will not find a cycle (no edge loops back)
        assert path is None or path == ["swizzle"]


class TestCompositionExecution:
    """Verify compositions execute correctly with adapters."""

    @pytest.fixture
    def composer(self):
        c = LibraryComposer()
        register_core_adapters(c)
        register_core_translation_rules(c)
        return c

    def test_single_system_composition(self, composer):
        """Execute single system composition (SWIZZLE only)."""
        subject = {"repo": "test_repo", "commit": "abc123"}
        trace = composer.compose(["swizzle"], subject, cycle=1)

        assert len(trace.steps) == 1
        assert trace.steps[0].system_name == "swizzle"
        assert trace.steps[0].output_outcome is not None
        assert trace.composition_path == ["swizzle"]

    def test_two_system_composition(self, composer):
        """Execute two-system composition (SWIZZLE → ghost_tools)."""
        subject = {"repo": "test_repo", "commit": "abc123"}
        path = composer.find_composition_path("swizzle", "ghost_tools")

        if path:
            trace = composer.compose(path, subject, cycle=1)
            assert len(trace.steps) >= 2
            assert trace.steps[0].system_name == "swizzle"
            assert trace.steps[-1].system_name == "ghost_tools"

            # Verify subject hash is consistent across steps
            subject_hash = trace.steps[0].subject_hash
            for step in trace.steps:
                assert step.subject_hash == subject_hash

    def test_full_circle_composition(self, composer):
        """Execute full circle (SWIZZLE → ghost_tools → WIZZLE → Innovation OS)."""
        subject = {"repo": "test_repo", "commit": "abc123"}
        composition = ["swizzle", "ghost_tools", "wizzle", "innovation_os"]

        trace = composer.compose(composition, subject, cycle=1)

        assert len(trace.steps) == 4
        assert trace.steps[0].system_name == "swizzle"
        assert trace.steps[1].system_name == "ghost_tools"
        assert trace.steps[2].system_name == "wizzle"
        assert trace.steps[3].system_name == "innovation_os"

        # Final outcome should be canonical (PASS/RETRY/TERMINAL_BREACH)
        assert trace.overall_outcome.value in ("pass", "retry", "terminal_breach")

    def test_subject_binding_across_cycle(self, composer):
        """Subject hash remains consistent across composition steps."""
        subject1 = {"repo": "repo_a", "commit": "aaa"}
        subject2 = {"repo": "repo_b", "commit": "bbb"}

        composition = ["swizzle", "ghost_tools"]
        trace1 = composer.compose(composition, subject1, cycle=1)
        trace2 = composer.compose(composition, subject2, cycle=1)

        # Same subject → same hash
        assert trace1.steps[0].subject_hash == trace1.steps[1].subject_hash

        # Different subject → different hash
        assert trace1.steps[0].subject_hash != trace2.steps[0].subject_hash

    def test_convergence_check(self, composer):
        """Convergence detection identifies whether composition settled."""
        subject = {"repo": "test_repo", "commit": "abc123"}
        composition = ["swizzle", "ghost_tools", "wizzle", "innovation_os"]
        trace = composer.compose(composition, subject, cycle=1)

        # Final outcome is PASS or TERMINAL_BREACH → converged
        # Final outcome is RETRY → not converged (still exploring)
        if trace.overall_outcome.value == "retry":
            assert not trace.converged
        else:
            assert trace.converged

    def test_cycle_tracking(self, composer):
        """Composition trace tracks cycle number correctly."""
        subject = {"repo": "test_repo", "commit": "abc123"}
        composition = ["swizzle"]

        trace_cycle1 = composer.compose(composition, subject, cycle=1)
        trace_cycle2 = composer.compose(composition, subject, cycle=2)

        assert trace_cycle1.cycle == 1
        assert trace_cycle2.cycle == 2


class TestTranslationRules:
    """Verify translation rules work at system boundaries."""

    @pytest.fixture
    def composer(self):
        c = LibraryComposer()
        register_core_adapters(c)
        register_core_translation_rules(c)
        return c

    def test_verdict_to_decision_translation(self, composer):
        """SWIZZLE verdict translates to Innovation OS decision."""
        rule = composer.translation_rules.get(
            (SystemModel.SWIZZLE_VERDICT, SystemModel.INNOVATION_OS_DECISION)
        )
        assert rule is not None

        # Test translation mappings
        assert rule("banished") == "approved"
        assert rule("dismissed") == "approved"
        assert rule("escaped") == "rejected"
        assert rule("conjured") == "rejected"
        assert rule("unsummoned") == "branched"

    def test_status_to_decision_translation(self, composer):
        """ghost_tools status translates to Innovation OS decision."""
        rule = composer.translation_rules.get(
            (SystemModel.GHOST_TOOLS_STATUS, SystemModel.INNOVATION_OS_DECISION)
        )
        assert rule is not None

        assert rule("confirmed") == "approved"
        assert rule("reasoned") == "branched"
        assert rule("rejected") == "rejected"

    def test_decision_to_gate_translation(self, composer):
        """Innovation OS decision translates to CNS gate outcome."""
        rule = composer.translation_rules.get(
            (SystemModel.INNOVATION_OS_DECISION, SystemModel.CNS_GATE_OUTCOME)
        )
        assert rule is not None

        assert rule("approved") == "pass"
        assert rule("rejected") == "terminal_breach"
        assert rule("branched") == "retry"


class TestCompositionBuilder:
    """Verify fluent API for building compositions."""

    @pytest.fixture
    def composer(self):
        c = LibraryComposer()
        register_core_adapters(c)
        register_core_translation_rules(c)
        return c

    def test_builder_add_systems(self, composer):
        """Build composition fluently."""
        from cns.compose_library import CompositionBuilder

        builder = CompositionBuilder(composer)
        path = (
            builder.add_system("swizzle")
            .add_system("ghost_tools")
            .add_system("wizzle")
            .add_system("innovation_os")
            .build()
        )

        assert path == ["swizzle", "ghost_tools", "wizzle", "innovation_os"]

    def test_builder_execute(self, composer):
        """Builder can execute composition directly."""
        from cns.compose_library import CompositionBuilder

        builder = CompositionBuilder(composer)
        subject = {"repo": "test_repo", "commit": "abc123"}

        trace = (
            builder.add_system("swizzle")
            .add_system("ghost_tools")
            .execute(subject, cycle=1)
        )

        assert len(trace.steps) == 2
        assert trace.overall_outcome.value in ("pass", "retry", "terminal_breach")

    def test_builder_unknown_system_raises(self, composer):
        """Adding unknown system raises ValueError."""
        from cns.compose_library import CompositionBuilder

        builder = CompositionBuilder(composer)
        with pytest.raises(ValueError, match="System not registered"):
            builder.add_system("nonexistent_system")

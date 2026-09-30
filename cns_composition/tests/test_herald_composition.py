"""Integration tests: SWIZZLE → HERALD → Innovation OS → ghost_tools → repeat.

These tests will FAIL and expose what's missing from direct composition.
Each failure is a requirement for the 5-cycle loop to work.
"""

import pytest
from cns.gate import GateOutcome
from cns_composition.herald_passthrough import (
    HeraldCompositionResult,
    SwizzleVerdict,
    InnovationOSDecision,
    GhostToolsStatus,
    translate_swizzle_to_canonical,
    translate_innovation_os_to_canonical,
    translate_ghost_tools_to_canonical,
    translate_canonical_to_swizzle,
    translate_canonical_to_innovation_os,
    translate_canonical_to_ghost_tools,
)


class TestHeraldTranslationBoundary:
    """Can HERALD translate between three outcome models without loss?"""

    def test_swizzle_banished_translates_to_pass(self):
        """SWIZZLE's highest verdict should map to PASS."""
        t = translate_swizzle_to_canonical(
            SwizzleVerdict.BANISHED.value,
            warp_name="test_warp",
            findings=(("detector", "file.py", 42),),
            proof_holds=True,
        )
        assert t.canonical_outcome == GateOutcome.PASS
        assert t.subject_hash is not None

    def test_swizzle_escaped_translates_to_breach(self):
        """SWIZZLE's blind spot should map to TERMINAL_BREACH."""
        t = translate_swizzle_to_canonical(
            SwizzleVerdict.ESCAPED.value,
            warp_name="missed_defect",
            findings=(),
            proof_holds=True,
        )
        assert t.canonical_outcome == GateOutcome.TERMINAL_BREACH

    def test_innovation_os_approved_translates_to_pass(self):
        """Innovation OS approved decision should be PASS."""
        t = translate_innovation_os_to_canonical(
            InnovationOSDecision.APPROVED.value,
            problem_id="prob_1",
            idea_id="idea_42",
            evaluation_score=0.95,
            authorization_required=True,
        )
        assert t.canonical_outcome == GateOutcome.PASS
        assert t.metadata["evaluation_score"] == 0.95

    def test_innovation_os_proposed_not_yet_pass(self):
        """Innovation OS proposed (AI generated) should be RETRY, not PASS."""
        t = translate_innovation_os_to_canonical(
            InnovationOSDecision.PROPOSED.value,
            problem_id="prob_1",
            idea_id="idea_1",
            evaluation_score=None,
        )
        # Proposed is pending human approval, so it's not PASS yet
        assert t.canonical_outcome == GateOutcome.RETRY

    def test_ghost_tools_confirmed_translates_to_pass(self):
        """ghost_tools CONFIRMED should map to PASS."""
        t = translate_ghost_tools_to_canonical(
            GhostToolsStatus.CONFIRMED.value,
            file_modified="innovation_os/engine.py",
            lines_changed=5,
            severity="MINOR",
        )
        assert t.canonical_outcome == GateOutcome.PASS
        assert t.metadata["lines_changed"] == 5

    def test_ghost_tools_rejected_translates_to_breach(self):
        """ghost_tools REJECTED (a human said no) should map to TERMINAL_BREACH."""
        t = translate_ghost_tools_to_canonical(
            GhostToolsStatus.REJECTED.value,
            file_modified="innovation_os/engine.py",
            lines_changed=0,
            severity="CRITICAL",
        )
        assert t.canonical_outcome == GateOutcome.TERMINAL_BREACH


class TestHeraldRoundTrip:
    """Can we round-trip: system → canonical → system without loss?"""

    def test_swizzle_roundtrip_banished(self):
        """BANISHED → canonical → back to SWIZZLE should yield same verdict."""
        original = SwizzleVerdict.BANISHED.value
        t = translate_swizzle_to_canonical(original, "test", (), True)
        recovered = translate_canonical_to_swizzle(t.canonical_outcome, t.subject_hash)
        # Should map to BANISHED (which is PASS)
        assert recovered == original

    def test_innovation_os_roundtrip_approved(self):
        """APPROVED → canonical → back should yield APPROVED."""
        original = InnovationOSDecision.APPROVED.value
        t = translate_innovation_os_to_canonical(original, "p1", "i1")
        recovered = translate_canonical_to_innovation_os(t.canonical_outcome, t.subject_hash)
        assert recovered == original

    def test_ghost_tools_roundtrip_confirmed(self):
        """CONFIRMED → canonical → back should yield CONFIRMED."""
        original = GhostToolsStatus.CONFIRMED.value
        t = translate_ghost_tools_to_canonical(original, "file.py", 5)
        recovered = translate_canonical_to_ghost_tools(t.canonical_outcome, t.subject_hash)
        assert recovered == original


class TestCompositionCycle:
    """Simulate one full cycle: SWIZZLE → Innovation OS → ghost_tools → re-test."""

    def test_cycle_1_swizzle_finds_issue(self):
        """Cycle 1: SWIZZLE tests Innovation OS, finds issue."""
        # SWIZZLE verdict: proposal became approved silently (ESCAPED = bad)
        verdict = translate_swizzle_to_canonical(
            SwizzleVerdict.ESCAPED.value,
            warp_name="ai_proposal_became_approved",
            findings=(),
            proof_holds=True,
        )
        assert verdict.canonical_outcome == GateOutcome.TERMINAL_BREACH
        assert verdict.source_system == "swizzle"

    def test_cycle_2_innovation_os_receives_breach(self):
        """Cycle 2: Innovation OS interprets SWIZZLE's TERMINAL_BREACH as rejection."""
        # Convert SWIZZLE's TERMINAL_BREACH into Innovation OS decision
        recovered_decision = translate_canonical_to_innovation_os(
            GateOutcome.TERMINAL_BREACH,
            "hash_x"
        )
        # Should map to REJECTED
        assert recovered_decision == InnovationOSDecision.REJECTED.value

    def test_cycle_3_ghost_tools_attempts_fix(self):
        """Cycle 3: ghost_tools receives rejection, attempts fix."""
        # Innovation OS says REJECTED
        # ghost_tools tries to fix Innovation OS code to prevent silent approval
        fix_status = translate_ghost_tools_to_canonical(
            GhostToolsStatus.CONFIRMED.value,
            file_modified="innovation_os/lifecycle.py",
            lines_changed=12,
            severity="MAJOR",
        )
        assert fix_status.canonical_outcome == GateOutcome.PASS
        assert fix_status.metadata["lines_changed"] == 12

    def test_cycle_4_swizzle_retests_after_fix(self):
        """Cycle 4: SWIZZLE re-tests Innovation OS after ghost_tools fix."""
        # After the fix, SWIZZLE re-runs the same test case
        # Best case: now BANISHED (found the issue)
        retest = translate_swizzle_to_canonical(
            SwizzleVerdict.BANISHED.value,
            warp_name="ai_proposal_became_approved",
            findings=(("lifecycle_check", "lifecycle.py", 42),),
            proof_holds=True,
        )
        assert retest.canonical_outcome == GateOutcome.PASS


class TestCompositionGaps:
    """What is MISSING for the loop to actually work, recorded the way the
    root conftest demands: as assertions of the gap, not skips. Each one
    fails the day its gap closes and makes someone write the real test.
    The questions from the original skips are kept in the docstrings."""

    def test_gap_swizzle_needs_innovation_os_interface(self):
        """SWIZZLE has no native way to invoke Innovation OS as a target.

        SWIZZLE currently tests ghost_tools (code modification system).
        Innovation OS is a decision system, not code modification.
        What does "test Innovation OS" mean? What are the test cases?

        The gap, asserted: the SWIZZLE adapter is a placeholder that never
        reads its subject. When a real adapter lands, this fails.
        """
        from cns_composition.adapters import SwizzleAdapter
        adapter = SwizzleAdapter()
        assert adapter.invoke({"repo": "a"}, None) == adapter.invoke({"repo": "b", "commit": "c"}, None) == "escaped"
        assert adapter.invoke({}, "retry") == "banished"

    def test_gap_innovation_os_needs_to_expose_decision_interface(self):
        """Innovation OS makes decisions, but how does HERALD get them out?

        Innovation OS has a lifecycle, but no canonical "decision" export format.
        HERALD needs to hook into: Problem → Idea → Decision point.

        The gap, asserted: the Innovation OS adapter decides from the input
        outcome alone and never consults the subject.
        """
        from cns_composition.adapters import InnovationOSAdapter
        adapter = InnovationOSAdapter()
        assert adapter.invoke({"problem": "p1"}, None) == adapter.invoke({"problem": "p2"}, None) == "proposed"
        assert adapter.invoke({"problem": "p1"}, "banished") == "approved"

    def test_gap_ghost_tools_needs_innovation_os_file_interface(self):
        """ghost_tools modifies code, but what IS "Innovation OS code to fix"?

        ghost_tools works on Python files. Innovation OS is a framework.
        Does ghost_tools patch innovation_os/*.py files?
        Does it understand the semantic meaning of lifecycle decisions?

        The gap, asserted: the ghost_tools adapter never opens or reads the
        file its subject names.
        """
        from cns_composition.adapters import GhostToolsAdapter
        adapter = GhostToolsAdapter()
        assert adapter.invoke({"file": "a.py"}, "escaped") == adapter.invoke({"file": "b.py"}, "escaped") == "confirmed"
        assert adapter.invoke({"file": "a.py"}, None) == "reasoned"

    def test_gap_no_cycle_termination_condition(self):
        """How many cycles until success? What is "success"?

        The loop spec says 5 cycles, but:
        - Does "all PASS" mean we're done?
        - Can we hit cycles 2-4 without progress?
        - Is there a regression detection (cycle 3 makes it worse)?

        The gap, asserted: a trace carries a cycle number and a convergence
        flag read off the final outcome, and nothing else. A termination
        criterion would be a new field here.
        """
        from dataclasses import fields
        from cns_composition.compose_library import CompositionTrace
        assert [f.name for f in fields(CompositionTrace)] == [
            "steps", "overall_outcome", "composition_path", "cycle", "converged"]

    def test_gap_no_failure_recovery(self):
        """What happens if ghost_tools breaks something else?

        If cycle 3 (ghost_tools fix) introduces a NEW bug detected in cycle 4:
        - Does ghost_tools know to revert?
        - Does HERALD have a rollback path?
        - Is there a "worse than before" detection?

        The gap, asserted: neither composer exposes any recovery operation.
        """
        from cns_composition.compose_library import CompositionBuilder, LibraryComposer
        public = {n for cls in (LibraryComposer, CompositionBuilder)
                  for n in dir(cls) if not n.startswith("_")}
        assert not {"rollback", "revert", "recover", "undo"} & public


class TestGhostToolsVocabularyPin:
    """Step 1.4: one ghost_tools vocabulary, pinned to its source of truth.

    Source: wking53214/ghost_tools, ghost_buster/schema.py, class Status,
    read at commit 93143f5 (the file last changed in d1fd094). The members
    and their order are copied from that file, not inferred. If ghost_tools
    changes its Status, this list changes in the same commit that moves
    the passthrough, and the diff is the review.
    """

    GHOST_TOOLS_STATUS_SOURCE = [
        ("CONFIRMED", "confirmed"),
        ("REASONED", "reasoned"),
        ("CONFIRMED_BY_REVIEW", "confirmed_by_review"),
        ("REJECTED", "rejected"),
        ("SUPPRESSED", "suppressed"),
    ]

    def test_enum_matches_ghost_buster_schema_status(self):
        assert [(m.name, m.value) for m in GhostToolsStatus] == \
            self.GHOST_TOOLS_STATUS_SOURCE

    def test_every_member_translates_and_every_outcome_maps_back(self):
        """No member falls through to the unknown-status fallback, and the
        reverse direction only ever produces a real member."""
        for member in GhostToolsStatus:
            t = translate_ghost_tools_to_canonical(member.value, "f.py", 0)
            assert t.source_verdict == member.value
            assert isinstance(t.canonical_outcome, GateOutcome)
        members = {m.value for m in GhostToolsStatus}
        for outcome in GateOutcome:
            assert translate_canonical_to_ghost_tools(outcome, "h") in members

    def test_the_invented_vocabulary_is_gone(self):
        for stale in ("pass", "finding", "skipped", "unsummoned"):
            assert stale not in {m.value for m in GhostToolsStatus}


class TestSubjectBinding:
    """Do translated outcomes stay bound to what they judged?"""

    def test_swizzle_outcome_binds_to_warp(self):
        """SWIZZLE outcome should refuse to be applied to different warp."""
        t1 = translate_swizzle_to_canonical(
            SwizzleVerdict.BANISHED.value,
            warp_name="warp_A",
            findings=(("det", "f.py", 1),),
        )
        t2 = translate_swizzle_to_canonical(
            SwizzleVerdict.BANISHED.value,
            warp_name="warp_B",
            findings=(("det", "f.py", 1),),
        )
        # Same verdict, different subject → different hash
        assert t1.subject_hash != t2.subject_hash

    def test_innovation_os_outcome_binds_to_idea(self):
        """Innovation OS outcome should not transplant to different idea."""
        t1 = translate_innovation_os_to_canonical(
            InnovationOSDecision.APPROVED.value,
            problem_id="prob_1",
            idea_id="idea_A",
        )
        t2 = translate_innovation_os_to_canonical(
            InnovationOSDecision.APPROVED.value,
            problem_id="prob_1",
            idea_id="idea_B",
        )
        assert t1.subject_hash != t2.subject_hash

    def test_ghost_tools_outcome_binds_to_file_state(self):
        """ghost_tools outcome should bind to file hash, not just filename."""
        # Same file, different lines changed
        t1 = translate_ghost_tools_to_canonical(
            GhostToolsStatus.CONFIRMED.value,
            file_modified="engine.py",
            lines_changed=5,
        )
        t2 = translate_ghost_tools_to_canonical(
            GhostToolsStatus.CONFIRMED.value,
            file_modified="engine.py",
            lines_changed=10,
        )
        # Different state → different hash
        assert t1.subject_hash != t2.subject_hash

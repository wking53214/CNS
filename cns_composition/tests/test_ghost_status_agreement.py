"""Every place CNS maps a ghost_tools Status to a gate outcome gives the same answer, and it is ghost_tools' answer.

ghost_tools' own table (ghost_buster/cns_adapter.py, _STATUS_TO_OUTCOME) is the source, because the vocabulary is
ghost_tools': its Status says how sure Ghost is that a finding is real. By that meaning:

  confirmed, confirmed_by_review  PASS   Ghost is sure, or a human verified it
  suppressed                      PASS   known and accepted into the baseline: not a live defect
  reasoned                        RETRY  an unverified claim. Verifying it is the repair, so it is not a breach
  rejected                        BREACH a human said no

CNS carried a different table in three places (reasoned as a breach; suppressed as RETRY; confirmed_by_review as RETRY in
one of them). CNS cannot import ghost_tools, so the table is written out here and cited above.
"""

import pytest
from cns.gate import GateOutcome

from cns_composition.compose import Composer, SystemName
from cns_composition.compose import CompositionStep as SingleStep
from cns_composition.compose_library import CompositionStep, LibraryComposer, SystemModel
from cns_composition.herald_passthrough import (
    GhostToolsStatus,
    translate_canonical_to_ghost_tools,
    translate_ghost_tools_to_canonical,
)

GHOST_TOOLS_OWN_TABLE = {
    "confirmed": GateOutcome.PASS,
    "confirmed_by_review": GateOutcome.PASS,
    "suppressed": GateOutcome.PASS,
    "reasoned": GateOutcome.RETRY,
    "rejected": GateOutcome.TERMINAL_BREACH,
}


def test_the_table_covers_exactly_ghost_toolss_statuses():
    assert set(GHOST_TOOLS_OWN_TABLE) == {m.value for m in GhostToolsStatus}


@pytest.mark.parametrize("status,expected", sorted(GHOST_TOOLS_OWN_TABLE.items()))
def test_the_herald_table_agrees_with_ghost_tools(status, expected):
    assert translate_ghost_tools_to_canonical(status, "f.py", 0).canonical_outcome is expected


@pytest.mark.parametrize("status,expected", sorted(GHOST_TOOLS_OWN_TABLE.items()))
def test_the_library_composer_agrees_with_ghost_tools(status, expected):
    step = CompositionStep(system_name="ghost_tools", output_outcome=status,
                           output_model=SystemModel.GHOST_TOOLS_STATUS)
    assert LibraryComposer()._canonicalize(step) is expected


@pytest.mark.parametrize("status,expected", sorted(GHOST_TOOLS_OWN_TABLE.items()))
def test_the_single_composer_agrees_with_ghost_tools(status, expected):
    step = SingleStep(system=SystemName.GHOST_TOOLS, output_outcome=status)
    assert Composer()._canonicalize_final_outcome(step) is expected


def test_an_unverified_claim_is_never_a_breach_in_any_table():
    assert translate_ghost_tools_to_canonical("reasoned", "f.py", 0).canonical_outcome is GateOutcome.RETRY


@pytest.mark.parametrize("outcome", list(GateOutcome))
def test_going_back_to_a_status_and_forward_again_keeps_the_outcome(outcome):
    """The reverse table only ever produces a status that maps forward to the same outcome."""
    status = translate_canonical_to_ghost_tools(outcome, "hash")
    assert translate_ghost_tools_to_canonical(status, "f.py", 0).canonical_outcome is outcome


def test_the_retry_status_sent_back_for_fixing_is_the_unverified_one():
    assert translate_canonical_to_ghost_tools(GateOutcome.RETRY, "hash") == "reasoned"

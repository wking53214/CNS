"""Every place CNS maps a SWIZZLE verdict to a gate outcome gives the same answer.

SWIZZLE's own table (swizzle/cns_adapter.py, _VERDICT_TO_OUTCOME) is the source. Three tables in
this package carry the same six verdicts, and one of them mapped UNSUMMONED to TERMINAL_BREACH
while the other two and SWIZZLE mapped it to RETRY. UNSUMMONED is SWIZZLE failing at its own job
(the build failed, the scan could not run, or the proof did not hold). It says nothing about the
scanner, so it cannot be a breach; it asks for the run to be repeated.

CNS cannot import SWIZZLE, so the expected table is written out here and cited above.
"""

import pytest
from cns.gate import GateOutcome

from cns_composition.compose import Composer, SystemName
from cns_composition.compose import CompositionStep as SingleStep
from cns_composition.compose_library import CompositionStep, LibraryComposer, SystemModel
from cns_composition.herald_passthrough import translate_swizzle_to_canonical

SWIZZLES_OWN_TABLE = {
    "banished": GateOutcome.PASS,
    "dismissed": GateOutcome.PASS,
    "misnamed": GateOutcome.RETRY,
    "unsummoned": GateOutcome.RETRY,
    "escaped": GateOutcome.TERMINAL_BREACH,
    "conjured": GateOutcome.TERMINAL_BREACH,
}


@pytest.mark.parametrize("verdict,expected", sorted(SWIZZLES_OWN_TABLE.items()))
def test_the_herald_table_agrees_with_swizzle(verdict, expected):
    assert translate_swizzle_to_canonical(verdict, "warp").canonical_outcome is expected


@pytest.mark.parametrize("verdict,expected", sorted(SWIZZLES_OWN_TABLE.items()))
def test_the_library_composer_agrees_with_swizzle(verdict, expected):
    step = CompositionStep(system_name="swizzle", output_outcome=verdict,
                           output_model=SystemModel.SWIZZLE_VERDICT)
    assert LibraryComposer()._canonicalize(step) is expected


@pytest.mark.parametrize("verdict,expected", sorted(SWIZZLES_OWN_TABLE.items()))
def test_the_single_composer_agrees_with_swizzle(verdict, expected):
    step = SingleStep(system=SystemName.SWIZZLE, output_outcome=verdict)
    assert Composer()._canonicalize_final_outcome(step) is expected


def test_unsummoned_is_never_a_breach_in_any_table():
    assert translate_swizzle_to_canonical("unsummoned", "w").canonical_outcome is GateOutcome.RETRY

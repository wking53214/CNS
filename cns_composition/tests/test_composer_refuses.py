"""compose.Composer refuses to invent an outcome.

Its three steps used to return fixed placeholders: SWIZZLE "escaped" (a breach), ghost_tools
"confirmed" (a PASS) and WIZZLE "removed_from_library" (a breach), none of them read from the
subject. A ghost_tools cycle therefore passed without scanning anything. The adapters in
adapters.py were made to refuse for this reason; these tests hold the same line here.
"""

import pytest

from cns_composition.compose import Composer, SystemName


@pytest.mark.parametrize("system", list(SystemName))
def test_a_single_step_without_a_real_run_refuses(system):
    with pytest.raises(NotImplementedError):
        Composer().run_cycle([system], {"repo": "r", "commit": "c"})


def test_a_ghost_tools_cycle_no_longer_passes_without_scanning():
    composer = Composer()
    with pytest.raises(NotImplementedError):
        composer.run_cycle([SystemName.GHOST_TOOLS], {"repo": "r"})
    assert composer.steps == []


def test_a_refusal_midway_leaves_no_placeholder_step_behind():
    composer = Composer()
    with pytest.raises(NotImplementedError):
        composer.run_cycle([SystemName.SWIZZLE, SystemName.GHOST_TOOLS], {"repo": "r"})
    assert composer.steps == []

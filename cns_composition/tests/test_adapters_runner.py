"""The SWIZZLE and ghost_tools adapters take a real run from the caller, and refuse to invent one.

CNS imports no repository, so the run is a function the caller supplies. Without one the adapters
refuse exactly as before. What the function returns must be an outcome of that system's own
vocabulary; anything else is an error, not a pass, a retry or a breach.
"""

import pytest
from cns.gate import GateOutcome

from cns_composition.adapters import GhostToolsAdapter, SwizzleAdapter, WizzleAdapter
from cns_composition.compose_library import LibraryComposer
from cns_composition.herald_passthrough import GhostToolsStatus, SwizzleVerdict

SUBJECT = {"repo": "r", "commit": "c"}


def test_without_a_runner_both_adapters_still_refuse():
    for adapter in (SwizzleAdapter(), GhostToolsAdapter(), WizzleAdapter()):
        with pytest.raises(NotImplementedError):
            adapter.invoke(SUBJECT, None)


def test_a_runner_is_handed_the_subject_and_the_previous_outcome():
    seen = []

    def run(subject, previous):
        seen.append((subject, previous))
        return "banished"

    assert SwizzleAdapter(run).invoke(SUBJECT, "retry") == "banished"
    assert seen == [(SUBJECT, "retry")]


@pytest.mark.parametrize("verdict", [v.value for v in SwizzleVerdict])
def test_every_swizzle_verdict_passes_through_unchanged(verdict):
    assert SwizzleAdapter(lambda s, p: verdict).invoke(SUBJECT) == verdict


@pytest.mark.parametrize("status", [v.value for v in GhostToolsStatus])
def test_every_ghost_tools_status_passes_through_unchanged(status):
    assert GhostToolsAdapter(lambda s, p: status).invoke(SUBJECT) == status


def test_an_enum_member_is_accepted_as_its_value():
    assert SwizzleAdapter(lambda s, p: SwizzleVerdict.ESCAPED).invoke(SUBJECT) == "escaped"
    assert GhostToolsAdapter(lambda s, p: GhostToolsStatus.REJECTED).invoke(SUBJECT) == "rejected"


@pytest.mark.parametrize("bad", ["", "maybe", "BANISHED", " banished", "pass", "retry", None, 1, ["banished"], b"banished"])
def test_an_answer_outside_the_vocabulary_is_refused_not_mapped(bad):
    with pytest.raises(ValueError, match="refusing to invent an outcome"):
        SwizzleAdapter(lambda s, p: bad).invoke(SUBJECT)
    with pytest.raises(ValueError, match="refusing to invent an outcome"):
        GhostToolsAdapter(lambda s, p: bad).invoke(SUBJECT)


def test_one_systems_word_is_not_the_others():
    with pytest.raises(ValueError):
        SwizzleAdapter(lambda s, p: "confirmed").invoke(SUBJECT)
    with pytest.raises(ValueError):
        GhostToolsAdapter(lambda s, p: "banished").invoke(SUBJECT)


def test_an_exception_from_the_run_is_not_turned_into_an_outcome():
    def boom(subject, previous):
        raise RuntimeError("scan failed")

    with pytest.raises(RuntimeError):
        GhostToolsAdapter(boom).invoke(SUBJECT)


def test_the_composer_runs_a_wired_path_and_canonicalizes_the_last_outcome():
    composer = LibraryComposer()
    composer.register_adapter(SwizzleAdapter(lambda s, p: "banished"))
    seen = []
    composer.register_adapter(GhostToolsAdapter(lambda s, p: seen.append(p) or "confirmed"))
    trace = composer.compose(["swizzle", "ghost_tools"], SUBJECT)
    assert seen == ["banished"]
    assert [s.output_outcome for s in trace.steps] == ["banished", "confirmed"]
    assert trace.overall_outcome is GateOutcome.PASS and trace.converged


def test_an_unwired_adapter_in_a_path_still_stops_the_composition():
    composer = LibraryComposer()
    composer.register_adapter(SwizzleAdapter(lambda s, p: "banished"))
    composer.register_adapter(GhostToolsAdapter())
    with pytest.raises(NotImplementedError):
        composer.compose(["swizzle", "ghost_tools"], SUBJECT)

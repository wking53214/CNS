"""LibraryComposer is retired: SuperGate over run_chain is the composition path (CNS-011).

It stays importable for reference, says so loudly when built, and no repository that depends on CNS may start
depending on it.
"""

import pathlib
import warnings

import pytest

from cns_composition.compose_library import LibraryComposer
from cns_composition.consumers import REQUIRED

ROOT = pathlib.Path(__file__).resolve().parents[2]
RETIRED = ("cns_composition.compose_library", "cns_composition.adapters")


def test_building_one_warns_and_names_what_replaced_it():
    with pytest.warns(DeprecationWarning, match="SuperGate"):
        LibraryComposer()


def test_the_warning_points_at_the_caller_not_at_this_module():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        LibraryComposer()
    assert caught and caught[0].filename == __file__


@pytest.mark.parametrize("repo", sorted(REQUIRED))
def test_no_consumer_imports_a_retired_module(repo):
    assert not set(REQUIRED[repo]) & set(RETIRED), f"{repo} imports a retired module"


def test_the_guide_lives_in_history_and_not_at_the_root():
    assert (ROOT / "docs" / "history" / "LIBRARY_COMPOSITION_GUIDE.md").is_file()
    assert not (ROOT / "LIBRARY_COMPOSITION_GUIDE.md").exists()

"""Step 15: every action in every workflow is pinned to a full commit, and ruff and mypy run in CI.

A tag such as `actions/checkout@v4` moves; a workflow that names it runs whatever the tag points at on the day, and
repin.yml's `propose` job does that with a write token. The commits below are the ones the sibling repositories already
use for checkout and setup-python; upload-artifact and download-artifact have no sibling user, so their commits were
read from `git ls-remote` of the action repositories (the commit the tag names), not guessed.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

PINS = {
    "actions/checkout": ("11bd71901bbe5b1630ceea73d27597364c9af683", "v4.2.2"),
    "actions/setup-python": ("a26af69be951a213d495a4c3e4e4022e16d87065", "v5.6.0"),
    "actions/upload-artifact": ("ea165f8d65b6e75b540449e92b4886f43607fa02", "v4.6.2"),
    "actions/download-artifact": ("d3f86a106a0bac45b974a628896c90dbdf5c8093", "v4.3.0"),
}
USES = re.compile(r"(?m)^\s*(?:- )?uses: (?P<action>[^@\s]+)@(?P<ref>\S+)(?P<rest>[^\n]*)$")


def test_there_are_workflows_and_each_uses_something():
    assert [p.name for p in WORKFLOWS] == ["chains.yml", "ci.yml", "links.yml", "repin.yml", "stack.yml"]
    assert all(USES.search(p.read_text(encoding="utf-8")) for p in WORKFLOWS)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_a_full_commit_with_its_version_in_a_comment(path):
    found = list(USES.finditer(path.read_text(encoding="utf-8")))
    assert found
    for m in found:
        assert re.fullmatch(r"[0-9a-f]{40}", m["ref"]), f"{path.name}: {m['action']}@{m['ref']} is not a full commit"
        assert re.fullmatch(r"\s+# v\d+\.\d+\.\d+", m["rest"]), f"{path.name}: {m['action']} has no version comment"
        want = PINS.get(m["action"])
        assert want is not None, f"{path.name}: {m['action']} has no recorded pin in this test"
        assert (m["ref"], m["rest"].strip()) == (want[0], f"# {want[1]}"), f"{path.name}: {m['action']} is not the recorded pin"


def test_the_write_token_job_says_why_it_is_kept():
    text = (ROOT / ".github" / "workflows" / "repin.yml").read_text(encoding="utf-8")
    job = text.split("\n  propose:\n", 1)[1]
    head = job.split("    steps:", 1)[0]
    assert "contents: write" in head and "pull-requests: write" in head
    assert "write token" in head and "runs\n    # no code from the other repositories" in head


def test_ci_runs_ruff_and_mypy_on_the_composition_package():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "run: python -m ruff check .\n" in text
    assert "run: python -m mypy cns_composition\n" in text
    assert "python -m mypy --strict cns/" in text  # the existing gate stays
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"ruff==\d+\.\d+\.\d+"', pyproject), "ruff is pinned in the dev extra"
    assert 'select = ["E4", "E7", "E9", "F"]' in pyproject

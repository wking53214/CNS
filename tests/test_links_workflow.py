"""The links workflow checks the ledger against every repository without trusting any of them."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "links.yml").read_text(encoding="utf-8")


def test_it_runs_on_a_schedule_by_hand_and_for_changes_to_the_ledger_only():
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in triggers and "workflow_dispatch:" in triggers
    assert "contracts/cns-links.json" in triggers and "cns_composition/link_ledger.py" in triggers
    assert "push:" not in triggers and "pull_request_target" not in triggers


def test_nothing_is_granted_by_default_and_the_one_job_can_only_read():
    assert re.search(r"(?m)^permissions: \{\}$", WORKFLOW)
    assert re.search(r"(?m)^    permissions:\n      contents: read$", WORKFLOW)
    assert "contents: write" not in WORKFLOW and "pull-requests: write" not in WORKFLOW


def test_the_repository_list_comes_from_the_ledger_not_from_this_file():
    assert "hub/contracts/cns-links.json" in WORKFLOW
    for name in ("ghost_tools", "SWIZZLE", "WARDEN", "sentinel_os"):
        assert name not in WORKFLOW.split("\nname: links\n", 1)[1]


def test_nothing_from_the_event_or_from_other_repositories_is_run_or_spliced_into_a_shell():
    body = WORKFLOW.split("\njobs:\n", 1)[1]
    assert "${{ github.event" not in body and "${{ github.head_ref" not in body
    assert "pip install" not in body and "stack/" not in body.split("link_ledger", 1)[1]
    assert "--stack ../stack" in body and "persist-credentials: false" in body


def test_a_repository_it_cannot_read_is_skipped_with_a_warning_and_the_token_is_masked():
    assert "::warning::" in WORKFLOW and "::add-mask::" in WORKFLOW

"""The links workflow checks the ledger against every repository without trusting any of them."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "links.yml").read_text(encoding="utf-8")


def test_it_runs_on_a_schedule_by_hand_and_for_changes_to_the_ledger_only():
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in triggers and "workflow_dispatch:" in triggers
    assert "contracts/cns-links.json" in triggers and "cns_composition/link_ledger.py" in triggers
    assert triggers.count("push:") == 1 and "push:\n    branches:\n      - main\n    paths:\n" in triggers
    assert "pull_request_target" not in triggers


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


def test_it_also_runs_the_consumers_check_against_the_same_checkouts():
    assert "python -m cns_composition.consumers --stack ../stack" in WORKFLOW
    assert "cns_composition/consumers.py" in WORKFLOW.split("\npermissions:", 1)[0]


def test_it_also_checks_the_vendored_digest_vectors_against_the_same_checkouts():
    assert "python -m cns_composition.digest_vectors --stack ../stack" in WORKFLOW
    assert "contracts/digest-vectors.json" in WORKFLOW.split("\npermissions:", 1)[0]


def test_it_also_holds_every_repositorys_cns_pin_to_the_release_floor():
    assert "python -m cns_composition.cns_versions --stack ../stack" in WORKFLOW
    triggers = WORKFLOW.split("\npermissions:", 1)[0]
    assert "contracts/cns-releases.json" in triggers and "cns_composition/cns_versions.py" in triggers



# ------------------------------------------------------------ kernel-digest (D-13)
# Read as text, like the tests above: PyYAML is not a dependency of this repository.

KERNEL = WORKFLOW.split("\n  kernel-digest:\n", 1)[1]


def _paths(block: str):
    return re.findall(r"(?m)^      - (\S+)$", block.split("paths:\n", 1)[1].split("\n  push:", 1)[0].split("\npermissions:", 1)[0])


def test_a_change_to_the_digest_or_its_contracts_triggers_the_workflow_on_pull_request_and_on_push_to_main():
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    pull, push = triggers.split("\n  pull_request:\n", 1)[1].split("\n  push:\n", 1)
    assert push.startswith("    branches:\n      - main\n    paths:\n")
    assert _paths(pull) == _paths(push)
    for path in ("cns/gate.py", "contracts/digest-vectors.json", "contracts/digest-differential.json",
                 "cns_composition/digest_vectors.py", "cns_composition/digest_differential.py"):
        assert path in _paths(pull)


def test_the_kernel_job_is_separate_read_only_and_holds_no_secret():
    assert KERNEL.startswith("    name: kernel-digest\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n")
    assert "needs:" not in WORKFLOW
    assert "secrets." not in KERNEL and "${{ github.event" not in KERNEL and "persist-credentials: false" in KERNEL
    assert "::add-mask::" in KERNEL and "exit 1" in KERNEL  # a checkout that fails is a failure, not a skip


def test_the_kernel_job_copies_cns_files_over_exactly_the_registered_vendored_paths_and_runs_both_rust_suites():
    from cns_composition import digest_vectors
    assert f"cp hub/contracts/digest-vectors.json kernel/{digest_vectors.VENDORED['STACK-Kernel']}\n" in KERNEL
    assert ("cp hub/contracts/digest-differential.json "
            f"kernel/{digest_vectors.VENDORED_DIFFERENTIAL['STACK-Kernel']}\n") in KERNEL
    assert "cargo +stable test -p stack-sentinel --test cns_vectors --locked\n" in KERNEL
    assert "cargo +stable test -p stack-trident --test cns_digest --locked\n" in KERNEL
    assert KERNEL.index("cp hub/contracts") < KERNEL.index("cargo +stable test")

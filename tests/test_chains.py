"""The chains workflow runs real repositories read-only, and the chain scripts are held to what CNS declares.

The scripts import other repositories, so they cannot run in this suite; the workflow runs them. What can be
held here: the workflow's permissions and checkouts, and that the scripts name only repositories CNS knows.
"""

import ast
import re
from pathlib import Path

from cns_composition.repo_gates import ENDS
from cns_composition.spine_trace import SPINE

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "chains.yml").read_text(encoding="utf-8")
FULL = ROOT / "chains" / "full_chain.py"
SPINE_RUN = ROOT / "chains" / "spine_run.py"


def test_the_workflow_can_only_read_and_runs_on_a_schedule_by_hand_and_for_its_own_paths():
    assert re.search(r"(?m)^permissions: \{\}$", WORKFLOW)
    assert re.search(r"(?m)^    permissions:\n      contents: read$", WORKFLOW)
    assert "contents: write" not in WORKFLOW and "pull-requests: write" not in WORKFLOW
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in triggers and "workflow_dispatch:" in triggers and "chains/**" in triggers
    assert "push:" not in triggers and "pull_request_target" not in triggers


def test_nothing_from_the_event_is_spliced_into_a_shell():
    body = WORKFLOW.split("\njobs:\n", 1)[1]
    assert "${{ github.event" not in body and "${{ github.head_ref" not in body
    assert body.count("persist-credentials: false") == body.count("uses: actions/checkout@v4")


def test_every_repository_the_chains_use_is_checked_out():
    declared = set(re.findall(r"repository: \$\{\{ github\.repository_owner \}\}/(\S+)", WORKFLOW))
    assert declared == {"Governance_Gateway", "DGK", "DIT", "URE", *SPINE}


def test_the_full_chain_names_only_repositories_whose_gate_ends_cns_declares():
    tree = ast.parse(FULL.read_text(encoding="utf-8"))
    named = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and n.value in {"Governance_Gateway", "DGK", "DIT", "URE"}}
    assert named == {"Governance_Gateway", "DGK", "DIT", "URE"} and named <= set(ENDS)


def test_both_scripts_state_what_each_scenario_must_produce_and_exit_nonzero_when_it_does_not():
    for path in (FULL, SPINE_RUN):
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        assert "SCENARIOS" in text and "return 1 if" in text and "raise SystemExit(main())" in text


def test_the_spine_script_exercises_every_repository_of_the_spine():
    text = SPINE_RUN.read_text(encoding="utf-8")
    for package in SPINE.values():
        assert f"{package}.cns_connector" in text or f"from {package} import" in text

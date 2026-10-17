"""The repin workflow keeps the manifest true without trusting the code it runs.

The workflow cannot run until it is on the default branch, so what can be held now is held here: who gets
which permission, that it names every repository the manifest names, that nothing from the event is spliced
into a shell, and that the check the proposing job runs on the canary's manifest refuses what it should.
That check is extracted from the workflow text and executed, not re-implemented.
"""

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "repin.yml").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "contracts" / "warden-stack.json").read_text(encoding="utf-8"))


def job(name):
    """The text of one job: from `  name:` to the next job or the end of the file."""
    after = WORKFLOW.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  (\w+):\n", after)
    jobs = dict(zip(parts[1::2], parts[2::2]))
    return jobs[name]


def test_the_workflow_runs_on_a_schedule_and_by_hand_and_on_nothing_else():
    triggers = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in triggers and "workflow_dispatch:" in triggers
    assert "push:" not in triggers and "pull_request" not in triggers


def test_nothing_is_granted_by_default():
    assert re.search(r"(?m)^permissions: \{\}$", WORKFLOW)


def test_the_job_that_runs_other_repositories_code_can_only_read():
    block = job("canary")
    assert re.search(r"(?m)^    permissions:\n      contents: read$", block)
    assert "write" not in block


def test_the_job_that_can_write_runs_none_of_their_code():
    block = job("propose")
    assert "contents: write" in block and "pull-requests: write" in block
    assert "stack/" not in block
    assert "circuit_canary" not in block and "cns_composition.repin" not in block
    assert "repository:" not in block


def test_proposing_only_happens_after_a_change_and_only_from_the_default_branch():
    block = job("propose")
    assert "needs: canary" in block
    assert "needs.canary.outputs.changed == 'true'" in block
    assert "github.ref_name == github.event.repository.default_branch" in block


def test_the_canary_runs_the_circuit_every_time_not_only_when_a_pin_moved():
    block = job("canary")
    step = block.split("Run the whole circuit on that combination", 1)[1].split("\n      - ", 1)[0]
    assert "circuit_canary" in step and "if:" not in step


def test_the_canary_installs_pytest_and_cns_before_it_runs_the_circuit():
    """The first run on GitHub ended SUITE_RED on a clean Python: the throwaway repository's tests need pytest, and
    the instruments do not inherit PYTHONPATH, so cns has to be installed, not just reachable."""
    block = job("canary")
    install = block.index("python -m pip install pytest ./hub")
    assert install < block.index("cns_composition.repin")
    assert install < block.index("cns_composition.circuit_canary")


@pytest.mark.parametrize("name", sorted(MANIFEST["repos"]))
def test_every_repository_the_manifest_pins_is_checked_out_into_the_stack(name):
    block = job("canary")
    assert f"repository: ${{{{ github.repository_owner }}}}/{name}\n" in block
    assert f"path: stack/{name}\n" in block


def test_the_workflow_checks_out_no_repository_the_manifest_does_not_pin():
    block = job("canary")
    named = set(re.findall(r"repository: \$\{\{ github.repository_owner \}\}/(\w+)", block))
    assert named == set(MANIFEST["repos"])


def test_no_checkout_keeps_a_credential_it_does_not_need():
    block = job("canary")
    assert block.count("persist-credentials: false") == block.count("actions/checkout@")


def test_no_expression_is_spliced_into_a_shell_block():
    """Values reach a script through env, never by expansion into the script text."""
    for body in re.findall(r"(?m)^        run: \|\n((?:          .*\n|\n)+)", WORKFLOW):
        assert "${{" not in body, body


def test_every_action_is_pinned_to_a_release_tag():
    uses = re.findall(r"(?m)^\s+- uses: (\S+)$", WORKFLOW)
    assert uses and all(re.search(r"@v\d+$", u) for u in uses)


def test_a_failed_pull_request_still_leaves_the_branch_and_a_link():
    block = job("propose")
    assert "git push --force origin auto/repin" in block
    assert "GITHUB_STEP_SUMMARY" in block and "compare/auto/repin" in block


# ---------------------------------------------------------------------------
# The re-check the proposing job runs on the manifest the canary produced.
# ---------------------------------------------------------------------------

def recheck_source():
    block = job("propose")
    heredoc = re.search(r"python - <<'PY'\n(.*?)\n\s*PY\n", block, re.S)
    assert heredoc, "the re-check is no longer a python heredoc"
    return textwrap.dedent(heredoc.group(1))


def recheck(tmp_path, old, new):
    (tmp_path / "contracts").mkdir(exist_ok=True)
    (tmp_path / "proposed").mkdir(exist_ok=True)
    (tmp_path / "contracts" / "warden-stack.json").write_text(json.dumps(old), encoding="utf-8")
    (tmp_path / "proposed" / "warden-stack.json").write_text(json.dumps(new), encoding="utf-8")
    return subprocess.run([sys.executable, "-c", recheck_source()], cwd=tmp_path, capture_output=True, text=True)


def moved(manifest):
    return {**manifest, "repos": {n: "f" * 40 for n in manifest["repos"]}}


def test_the_recheck_accepts_a_manifest_that_only_moved_commits(tmp_path):
    assert recheck(tmp_path, MANIFEST, moved(MANIFEST)).returncode == 0


def test_the_recheck_accepts_an_unchanged_manifest(tmp_path):
    assert recheck(tmp_path, MANIFEST, MANIFEST).returncode == 0


@pytest.mark.parametrize("edit,why", [
    (lambda m: {**m, "schema": "warden-stack/2"}, "schema"),
    (lambda m: {**m, "contract": "2"}, "contract"),
    (lambda m: {**m, "repos": {**m["repos"], "EXTRA": "f" * 40}}, "set of repositories"),
    (lambda m: {**m, "repos": dict(list(m["repos"].items())[1:])}, "set of repositories"),
    (lambda m: {**m, "repos": dict(reversed(list(m["repos"].items())))}, "set of repositories"),
    (lambda m: {**m, "repos": {**m["repos"], "WARDEN": "abc1234"}}, "full commit"),
    (lambda m: {**m, "repos": {**m["repos"], "WARDEN": "F" * 40}}, "full commit"),
    (lambda m: {**m, "repos": {**m["repos"], "WARDEN": "main"}}, "full commit"),
    (lambda m: {**m, "note": "smuggled"}, "top-level field"),
])
def test_the_recheck_refuses_anything_but_a_commit_move(tmp_path, edit, why):
    done = recheck(tmp_path, MANIFEST, edit(moved(MANIFEST)))
    assert done.returncode != 0 and why in done.stderr

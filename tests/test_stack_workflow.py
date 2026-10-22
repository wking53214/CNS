"""The stack workflow holds the installed circuit to the manifest, and what can be run without GitHub is run here.

`.github/workflows/stack.yml` installs the whole circuit the way the README says, checks out the repositories the
manifest names at the commits it names, and runs the four checks that need all of them. The workflow itself can only
run on GitHub, so this file holds what can be held: when it runs, what it may do, which actions it uses, the order
of its steps, that it installs what `contracts/install-stack.txt` says, and that it takes its repositories from the
manifest and not from a list of its own. The checkout step and the one-`cns` assertion are extracted from the
workflow text and executed against local fixtures, not re-implemented.
"""

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "stack.yml").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "contracts" / "warden-stack.json").read_text(encoding="utf-8"))
INSTALL = (ROOT / "contracts" / "install-stack.txt").read_text(encoding="utf-8")

CHECKOUT = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2"
SETUP_PYTHON = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0"
HORSEMEN = "claude/horsemen-production-status-5wsndb"


def steps():
    """The job's steps, each as its own text block."""
    body = WORKFLOW.split("\n    steps:\n", 1)[1]
    return [chunk for chunk in re.split(r"(?m)^      - ", body) if chunk.strip()]


def step(fragment):
    found = [s for s in steps() if fragment in s]
    assert len(found) == 1, f"{len(found)} steps contain {fragment!r}"
    return found[0]


def position(fragment):
    return next(i for i, s in enumerate(steps()) if fragment in s)


def triggers():
    return WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]


def heredoc(block):
    found = re.search(r"python - <<'PY'\n(.*?)\n\s*PY\n?", block, re.S)
    assert found, "the step is no longer a python heredoc"
    return textwrap.dedent(found.group(1)) + "\n"


# ---------------------------------------------------------------------------------------- when it runs, what it may do

def test_it_runs_on_pushes_and_pull_requests_to_main_and_the_horsemen_branch_and_weekly():
    for event in ("push", "pull_request"):
        block = re.split(r"(?m)^  \w+:", triggers().split(f"  {event}:\n", 1)[1], maxsplit=1)[0]
        assert re.search(r"(?m)^      - main$", block) and f"      - {HORSEMEN}" in block, event
    assert re.search(r'(?m)^    - cron: "\d+ \d+ \* \* \d"$', triggers()), "a weekly schedule"
    assert "schedule:" in triggers()


def test_the_schedule_is_weekly_not_more_often():
    cron = re.search(r'cron: "(\S+) (\S+) (\S+) (\S+) (\S+)"', WORKFLOW).groups()
    minute, hour, day_of_month, month, day_of_week = cron
    assert minute.isdigit() and hour.isdigit() and day_of_month == "*" and month == "*" and day_of_week.isdigit()


def test_the_token_can_only_read_and_nothing_writes():
    assert re.search(r"(?m)^permissions:\n  contents: read$", WORKFLOW)
    assert not re.search(r"(?m)^\s*[\w-]+: write$", WORKFLOW)
    assert WORKFLOW.count("permissions:") == 2  # the workflow and the one job


def test_there_is_one_job():
    assert re.findall(r"(?m)^  (\w+):$", WORKFLOW.split("\njobs:\n", 1)[1]) == ["stack"]


def test_every_action_is_pinned_by_full_commit_and_names_the_release_it_is():
    uses = re.findall(r"(?m)^\s+- uses: (.+)$", WORKFLOW)
    assert uses == [CHECKOUT, SETUP_PYTHON]


def test_no_checkout_keeps_a_credential():
    checkouts = [s for s in steps() if s.startswith("uses: actions/checkout@")]
    assert len(checkouts) == 1 and "persist-credentials: false" in checkouts[0]
    assert "path: hub" in checkouts[0]


def test_python_is_3_12():
    assert re.search(r'python-version: "3\.12"', step("actions/setup-python"))


def test_no_expression_is_spliced_into_a_shell_block():
    """Values reach a script through env, never by expansion into the script text."""
    for body in re.findall(r"(?m)^        run: (?:\|\n((?:          .*\n|\n)+)|(.*)\n)", WORKFLOW):
        assert "${{" not in "".join(body), body


# ------------------------------------------------------------------------------------------- what it installs

def test_it_installs_the_stack_file_plus_what_the_circuit_needs():
    block = step("Install the whole circuit")
    assert "working-directory: hub" in block
    assert 'python -m pip install -r contracts/install-stack.txt "pytest>=8" numpy==2.5.4 matplotlib==3.11.2' in block
    assert (ROOT / "contracts" / "install-stack.txt").is_file()


def test_the_extra_pins_are_the_ones_install_stack_gives_for_python_3_12():
    """If install-stack.txt moves numpy or matplotlib, this job must move with it or it tests another environment."""
    assert "numpy==2.5.4; python_version >= '3.12'" in INSTALL
    assert "matplotlib==3.11.2" in INSTALL and "'pytest>=8'" in INSTALL


def test_the_workflow_names_no_repository_of_its_own():
    """It reads the manifest, so adding a repository there needs no edit here."""
    checkout = step("Check out the seven repositories")
    assert 'warden-stack.json' in checkout
    for name in MANIFEST["repos"]:
        assert name not in checkout, name


def test_the_install_file_and_the_manifest_name_the_same_repositories():
    installed = set(re.findall(r"(?m)^[\w.-]+ @ git\+https://github\.com/wking53214/([\w.-]+?)(?:\.git)?@", INSTALL))
    installed = {n.casefold() for n in installed} - {"cns", "watcher_mcu"}
    assert installed == {n.casefold() for n in MANIFEST["repos"]}


# -------------------------------------------------------------------------------------------- the order, and the checks

def test_the_steps_run_in_the_order_that_makes_each_one_meaningful():
    order = ["Install the whole circuit", "pip is satisfied", "Exactly one cns", "Check out the seven",
             "cns_composition.seat_pins", "cns_composition.cns_versions", "cns_composition.repin",
             "cns_composition.circuit_canary"]
    assert [position(f) for f in order] == sorted(position(f) for f in order)
    assert position("actions/checkout") < position("actions/setup-python") < position(order[0])


@pytest.mark.parametrize("command", [
    "python -m pip check",
    "python -m cns_composition.seat_pins --stack ../stack",
    "python -m cns_composition.cns_versions --stack ../stack",
    "python -m cns_composition.repin --stack ../stack --check",
    "python -m cns_composition.circuit_canary --stack ../stack --cns .",
])
def test_each_check_runs_as_its_own_step_with_nothing_that_could_hide_a_failure(command):
    block = step(command)
    assert f"run: {command}\n" in block + "\n"
    for hiding in ("continue-on-error", "|| true", "if:", "set +e"):
        assert hiding not in block


@pytest.mark.parametrize("module", ["seat_pins", "cns_versions", "repin", "circuit_canary"])
def test_the_checks_run_this_checkouts_code_from_the_hub_directory(module):
    block = step(f"cns_composition.{module}")
    assert "working-directory: hub" in block
    assert "PYTHONPATH: ${{ github.workspace }}/hub" in block


def test_the_pip_check_and_the_install_are_not_skippable():
    assert "continue-on-error" not in WORKFLOW and "|| true" not in WORKFLOW


# ------------------------------------------------------------- the checkout step, run against local repositories

def git(folder, *args):
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                           "-C", str(folder), *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def make_remote(base, name):
    """base/<name>.git with two commits; returns (first, second)."""
    folder = base / f"{name}.git"
    folder.mkdir(parents=True)
    git(folder, "init", "-q")
    shas = []
    for i in range(2):
        (folder / "f.txt").write_text(f"{name} {i}\n")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", f"c{i}")
        shas.append(git(folder, "rev-parse", "HEAD"))
    return shas


def run_checkout(tmp_path, repos, base):
    (tmp_path / "hub" / "contracts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "hub" / "contracts" / "warden-stack.json").write_text(
        json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": repos}), encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path), "BASE_URL": str(base) + "/",
           "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run([sys.executable, "-c", heredoc(step("Check out the seven"))], cwd=tmp_path, env=env,
                          capture_output=True, text=True)


def test_the_checkout_step_puts_every_manifest_repository_at_the_commit_the_manifest_names(tmp_path):
    base = tmp_path / "remote"
    repos = {}
    for name in MANIFEST["repos"]:
        first, second = make_remote(base, name)
        assert first != second
        repos[name] = first  # not the head: the named commit is what must be checked out
    done = run_checkout(tmp_path, repos, base)
    assert done.returncode == 0, done.stderr
    assert sorted(p.name for p in (tmp_path / "stack").iterdir()) == sorted(MANIFEST["repos"])
    for name, sha in repos.items():
        assert git(tmp_path / "stack" / name, "rev-parse", "HEAD") == sha
        assert (tmp_path / "stack" / name / "f.txt").read_text() == f"{name} 0\n"
        assert f"{name} {sha}" in done.stdout


@pytest.mark.parametrize("bad,why", [
    ("abc1234", "full commit"),
    ("A" * 40, "full commit"),
    ("main", "full commit"),
    ("0" * 40, ""),  # a full commit the remote does not have: git fails the step
])
def test_the_checkout_step_refuses_a_pin_that_is_not_a_commit_the_remote_has(tmp_path, bad, why):
    base = tmp_path / "remote"
    first, _ = make_remote(base, "one")
    make_remote(base, "two")
    done = run_checkout(tmp_path, {"one": first, "two": bad}, base)
    assert done.returncode != 0
    assert why in done.stderr


def test_the_checkout_step_refuses_a_repository_the_remote_does_not_have(tmp_path):
    base = tmp_path / "remote"
    base.mkdir()
    done = run_checkout(tmp_path, {"missing": "a" * 40}, base)
    assert done.returncode != 0


@pytest.mark.parametrize("name", ["../escape", ".hidden", "a/b", "a b"])
def test_the_checkout_step_refuses_a_name_that_is_not_a_repository_name(tmp_path, name):
    base = tmp_path / "remote"
    base.mkdir()
    done = run_checkout(tmp_path, {name: "a" * 40}, base)
    assert done.returncode != 0 and "not a repository name" in done.stderr
    assert not (tmp_path / "escape").exists()


def test_the_checkout_step_refuses_an_empty_manifest(tmp_path):
    base = tmp_path / "remote"
    base.mkdir()
    done = run_checkout(tmp_path, {}, base)
    assert done.returncode != 0 and "names no repository" in done.stderr


# ----------------------------------------------------------- the one-cns assertion, run against fake distributions

def dist(root, name, version="1.9.0"):
    folder = root / f"{name.lower()}-{version}.dist-info"
    folder.mkdir(parents=True)
    (folder / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8")


def one_cns(path_entries):
    # Only the fixtures and the standard library are searched: no installed cns of this interpreter can be found.
    prelude = ("import re, sys, importlib.metadata\n"
               "sys.path[:] = %r + [p for p in sys.path if 'site-packages' not in p and 'dist-packages' not in p]\n"
               % [str(p) for p in path_entries])
    code = prelude + heredoc(step("Exactly one cns"))
    return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)


def test_one_cns_distribution_passes(tmp_path):
    site = tmp_path / "site"
    dist(site, "cns")
    dist(site, "warden", "0.13.7")
    done = one_cns([site])
    assert done.returncode == 0, done.stderr
    assert "cns 1.9.0" in done.stdout


def test_no_cns_distribution_fails(tmp_path):
    site = tmp_path / "site"
    dist(site, "warden", "0.13.7")
    done = one_cns([site])
    assert done.returncode != 0 and "found 0" in done.stderr


def test_two_cns_distributions_fail_whatever_the_spelling_of_the_name(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    dist(first, "cns")
    dist(second, "CNS", "1.8.0")
    done = one_cns([first, second])
    assert done.returncode != 0 and "found 2" in done.stderr


def test_a_look_alike_name_is_not_a_cns_distribution(tmp_path):
    site = tmp_path / "site"
    dist(site, "cns")
    dist(site, "cns-tools", "0.1.0")
    dist(site, "ccns", "0.1.0")
    assert one_cns([site]).returncode == 0


def test_the_checkout_step_refuses_the_id_of_an_annotated_tag_which_is_not_the_commit_it_points_at(tmp_path):
    base = tmp_path / "remote"
    first, _ = make_remote(base, "one")
    git(base / "one.git", "tag", "-a", "-m", "release", "v1", first)
    tag_object = git(base / "one.git", "rev-parse", "v1")
    assert tag_object != first
    done = run_checkout(tmp_path, {"one": tag_object}, base)
    assert done.returncode != 0 and f"not {tag_object}" in done.stderr

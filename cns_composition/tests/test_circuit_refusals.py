"""circuit_refusals: each case builds the stack it claims to, and a circuit that does not refuse it fails the case.

Warden is replaced by a small stand-in that refuses for the real reasons (a pin that is not a full commit, a used
folder the manifest does not name, a checkout not at its pin, uncommitted work asked the strict way, a red suite)
and answers ACCEPT otherwise. A second stand-in accepts everything, which must fail every case: that is the proof
each case really changes something. The real circuit is run by the stack workflow.
"""

import json
import subprocess

import pytest

from cns_composition import circuit_refusals as cr

IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]

#: A Warden that refuses what Warden 0.13.8 refuses, written as plainly as possible.
STRICT_CLI = r'''
import json, os, re, subprocess, sys
from pathlib import Path

def out(decision, code, reason):
    print(json.dumps({"schema": "cns.run/1", "contract": "1", "decision": decision, "reason": reason,
                      "converged": decision == "ACCEPT", "finished": False, "put_back": False}))
    raise SystemExit(code)

args = sys.argv[1:]
target = Path(args[1])
stack = Path(args[args.index("--stack") + 1])
cns = Path(args[args.index("--cns") + 1])
manifest = json.loads((cns / "contracts" / "warden-stack.json").read_text())["repos"]
folders = {p.name.lower(): p for p in stack.iterdir() if p.is_dir()}
for name, pinned in manifest.items():
    if not re.fullmatch(r"[0-9a-f]{40}", pinned):
        out("USAGE_ERROR", 2, f"the stack manifest pins {name!r} to {pinned[:12]!r}, which is not a full 40-character commit")
    folder = folders.get(name.lower())
    if folder is None:
        out("USAGE_ERROR", 2, f"the stack manifest names {name!r}, which is not in the --stack folder")
    head = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != pinned:
        out("USAGE_ERROR", 2, f"the stack manifest pins {name!r} to {pinned[:12]}, but the checkout is at {head[:12]}")
if "drafter" not in folders and "--claim-commit" not in args:
    out("USAGE_ERROR", 2, "this stack has no drafter and nothing to propose; give --claim-commit, --claim-diff or --drafter")
for used in ("drafter", "judge", "burnish"):
    if used in folders and used not in {n.lower() for n in manifest}:
        out("USAGE_ERROR", 2, f"the stack manifest does not name {used!r}, yet this run uses it as a seat")
env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
empty = Path(os.environ["TMPDIR"]) / "emptyconfig" if "TMPDIR" in os.environ else cns / "emptyconfig"
empty.mkdir(exist_ok=True)
(empty / "gitconfig").write_text("")
env.update({"HOME": str(empty), "XDG_CONFIG_HOME": str(empty), "GIT_CONFIG_GLOBAL": str(empty / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1"})
for name, folder in folders.items():
    if folder.resolve() == target.resolve():
        continue
    status = subprocess.run(["git", "-c", "core.excludesFile=", "-C", str(folder), "status", "--porcelain",
                             "--untracked-files=all"], capture_output=True, text=True, env=env).stdout
    flags = subprocess.run(["git", "-C", str(folder), "ls-files", "-v"], capture_output=True, text=True, env=env).stdout
    hidden = [l for l in flags.splitlines() if l and (l[0].islower() or l[0] == "S")]
    if status.strip() or hidden:
        out("USAGE_ERROR", 2, f"the stack folder {name!r} has uncommitted changes")
if "assert circle(1) == 0" in (target / "tests" / "test_area.py").read_text():
    out("INCONCLUSIVE", 6, "Cycle 1: the suite is not green; nothing was written")
out("ACCEPT", 0, "")
'''

LENIENT_CLI = '''
import json
print(json.dumps({"schema": "cns.run/1", "contract": "1", "decision": "ACCEPT", "reason": "", "converged": True,
                  "finished": False, "put_back": False}))
'''


def git(folder, *args):
    return subprocess.run(["git", *IDENT, "-C", str(folder), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def make_repo(stack, name, files):
    folder = stack / name
    folder.mkdir(parents=True)
    git(folder, "init", "-q")
    files = {".gitignore": "__pycache__/\n", **files}  # as the real repositories do: a cache is not uncommitted work
    for rel, text in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "pinned")
    return git(folder, "rev-parse", "HEAD")


@pytest.fixture
def circuit(tmp_path, monkeypatch):
    """A stack of the circuit (Warden, the Judge and an instrument) plus a hub whose manifest pins them, with the strict
    stand-in as Warden. DRAFTER and BURNISH are released from the circuit: neither is in the stack or the manifest."""
    monkeypatch.setattr(cr.canary, "_missing_modules", lambda python, modules=cr.canary._NEEDED: [])
    stack = tmp_path / "stack"
    heads = {}
    heads["WARDEN"] = make_repo(stack, "WARDEN", {"warden/__init__.py": "", "warden/cli.py": STRICT_CLI})
    heads["JUDGE"] = make_repo(stack, "JUDGE", {"judge/__init__.py": "", "judge/seat.py": "class Judge: pass\n"})
    heads["SWIZZLE"] = make_repo(stack, "SWIZZLE", {"swizzle/__init__.py": ""})
    make_repo(stack, "WATCHER_MCU", {"watcher/cli.py": "x = 1\n"})  # in the stack, not in the manifest, not used
    cns = tmp_path / "cns"
    (cns / "contracts").mkdir(parents=True)
    (cns / "contracts" / "warden-stack.json").write_text(json.dumps(
        {"schema": "warden-stack/1", "contract": "1", "repos": heads}, indent=2) + "\n")
    monkeypatch.setenv("TMPDIR", str(tmp_path / "t"))
    (tmp_path / "t").mkdir()
    return stack, cns


def lenient(stack):
    (stack / "WARDEN" / "warden" / "cli.py").write_text(LENIENT_CLI)
    git(stack / "WARDEN", "commit", "-q", "-am", "lenient")
    return git(stack / "WARDEN", "rev-parse", "HEAD")


@pytest.mark.parametrize("case", [c.name for c in cr.CASES])
def test_a_strict_circuit_refuses_every_case(circuit, case):
    stack, cns = circuit
    outcome = cr.run_case(next(c for c in cr.CASES if c.name == case), stack, cns)
    assert outcome.ok, (outcome.decision, outcome.exit_code, outcome.reason)
    assert (outcome.decision, outcome.exit_code) in {("USAGE_ERROR", 2), ("INCONCLUSIVE", 6)}


@pytest.mark.parametrize("case", [c.name for c in cr.CASES])
def test_a_circuit_that_accepts_everything_fails_every_case(circuit, case):
    """The proof that each case changes something: a Warden that refuses nothing must fail all of them."""
    stack, cns = circuit
    head = lenient(stack)
    data = json.loads((cns / "contracts" / "warden-stack.json").read_text())
    data["repos"]["WARDEN"] = head
    (cns / "contracts" / "warden-stack.json").write_text(json.dumps(data, indent=2) + "\n")
    outcome = cr.run_case(next(c for c in cr.CASES if c.name == case), stack, cns)
    assert not outcome.ok and outcome.decision == "ACCEPT" and outcome.exit_code == 0


@pytest.mark.parametrize("case", [c.name for c in cr.CASES])
def test_no_case_is_refused_for_want_of_a_proposer(circuit, case):
    """The stack has no Drafter, so a run with no claim is refused for that and every case would pass for the wrong
    reason. Each case hands Warden a claimed commit, so the refusal it reads is the one the case is about."""
    stack, cns = circuit
    outcome = cr.run_case(next(c for c in cr.CASES if c.name == case), stack, cns)
    assert "nothing to propose" not in outcome.reason


def test_the_ten_cases_the_decision_record_promises_and_the_three_roster_cases_are_all_here():
    assert [c.name for c in cr.CASES] == [
        "dirty_tracked", "dirty_untracked", "omitted_seat", "short_pin", "uppercase_pin", "wrong_commit",
        "assume_unchanged", "skip_worktree", "global_excludes", "red_suite", "missing_seat", "unnamed_burnish",
        "unnamed_drafter"]
    assert all(c.expected == cr._REFUSED for c in cr.CASES[:9] + cr.CASES[10:])
    assert cr.CASES[9].expected == frozenset({("INCONCLUSIVE", 6), ("FINISH_REJECTED", 1), ("JUDGE_REJECTED", 1)})


def test_the_real_stack_is_never_written_and_the_scratch_is_removed(circuit, tmp_path):
    stack, cns = circuit
    before = {p: p.read_text() for p in stack.rglob("*") if p.is_file() and ".git" not in p.parts}
    status_before = {name: git(stack / name, "status", "--porcelain") for name in ("JUDGE", "WARDEN")}
    for case in cr.CASES:
        cr.run_case(case, stack, cns)
    after = {p: p.read_text() for p in stack.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert after == before
    assert {name: git(stack / name, "status", "--porcelain") for name in ("JUDGE", "WARDEN")} == status_before
    assert not [p for p in (tmp_path / "t").iterdir() if p.name.startswith("circuit-refusal-")]


def test_a_case_that_cannot_be_built_is_a_failure_that_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(cr.canary, "_missing_modules", lambda python, modules=cr.canary._NEEDED: [])
    stack = tmp_path / "stack"
    (stack / "JUDGE").mkdir(parents=True)  # not a git checkout, nothing else
    cns = tmp_path / "cns"
    (cns / "contracts").mkdir(parents=True)
    (cns / "contracts" / "warden-stack.json").write_text(json.dumps(
        {"schema": "warden-stack/1", "contract": "1", "repos": {"JUDGE": "a" * 40}}))
    outcome = cr.run_case(cr.CASES[0], stack, cns)
    assert not outcome.ok and outcome.decision == "REFUSAL_ERROR" and "could not be built" in outcome.reason


def test_the_command_exits_zero_only_when_every_case_is_refused(circuit, capsys):
    stack, cns = circuit
    assert cr.main(["--stack", str(stack), "--cns", str(cns), "--case", "short_pin", "--case", "wrong_commit"]) == 0
    out = capsys.readouterr().out
    assert "short_pin: USAGE_ERROR exit 2: refused as it must be" in out and "every case was refused (2 of 2)" in out
    lenient(stack)
    data = json.loads((cns / "contracts" / "warden-stack.json").read_text())
    data["repos"]["WARDEN"] = git(stack / "WARDEN", "rev-parse", "HEAD")
    (cns / "contracts" / "warden-stack.json").write_text(json.dumps(data, indent=2) + "\n")
    assert cr.main(["--stack", str(stack), "--cns", str(cns), "--case", "omitted_seat"]) == 1
    err = capsys.readouterr().err
    assert "omitted_seat: FAILED: got ACCEPT exit 0, expected USAGE_ERROR exit 2" in err
    assert "1 of 1 cases were not refused" in err


def test_the_command_refuses_a_missing_stack_hub_or_seat(tmp_path, capsys):
    assert cr.main(["--stack", str(tmp_path / "none"), "--cns", str(tmp_path)]) == 2
    (tmp_path / "stack").mkdir()
    assert cr.main(["--stack", str(tmp_path / "stack"), "--cns", str(tmp_path)]) == 2
    assert "no contracts/warden-stack.json" in capsys.readouterr().err
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "warden-stack.json").write_text("{}")
    assert cr.main(["--stack", str(tmp_path / "stack"), "--cns", str(tmp_path)]) == 2
    assert "no WARDEN checkout" in capsys.readouterr().err


def test_an_interpreter_that_cannot_import_what_the_circuit_needs_is_named(circuit, monkeypatch, capsys):
    stack, cns = circuit
    monkeypatch.setattr(cr.canary, "_missing_modules", lambda python, modules=cr.canary._NEEDED: ["numpy"])
    assert cr.main(["--stack", str(stack), "--cns", str(cns)]) == 2
    assert "cannot import numpy" in capsys.readouterr().err

"""circuit_canary: ACCEPT is the only pass, and every other answer is a failure that says why.

Warden is replaced by a small stand-in package that prints a canned run record, so each outcome Warden can
give is checked without running the whole circuit. The real circuit is run by the repin workflow.
"""

import json
import os
from pathlib import Path

import pytest

from cns_composition import circuit_canary as cc

FAKE_CLI = '''\
import json, os, sys
print(os.environ["FAKE_RUN"] if os.environ.get("FAKE_RUN") else "")
sys.stderr.write(os.environ.get("FAKE_ERR", ""))
raise SystemExit(int(os.environ.get("FAKE_RC", "0")))
'''

RECORD = {"schema": "cns.run/1", "decision": "ACCEPT", "reason": "", "converged": True, "put_back": False}


@pytest.fixture
def stack(tmp_path, monkeypatch):
    s = tmp_path / "stack"
    for name in ("WARDEN", "JUDGE", "DRAFTER", "BURNISH"):
        (s / name).mkdir(parents=True)
    pkg = s / "WARDEN" / "warden"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "cli.py").write_text(FAKE_CLI)
    monkeypatch.setenv("FAKE_RUN", json.dumps(RECORD))
    monkeypatch.setenv("FAKE_RC", "0")
    return s


def run(stack, tmp_path):
    return cc.run_canary(stack, tmp_path / "cns")


def test_accept_converged_and_nothing_put_back_is_a_pass(stack, tmp_path):
    result = run(stack, tmp_path)
    assert result.ok and result.decision == "ACCEPT"


@pytest.mark.parametrize("change,rc", [
    ({"decision": "REJECT", "reason": "the suite is red"}, 1),
    ({"decision": "USAGE_ERROR", "reason": "the stack manifest pins 'x' to 1, but the checkout is at 2"}, 2),
    ({"decision": "ACCEPT_UNVERIFIED", "reason": "held"}, 0),
    ({"converged": False}, 0),
    ({"put_back": True}, 0),
    ({"decision": "ACCEPT"}, 1),            # exit code disagrees with the record
])
def test_anything_but_a_clean_accept_is_a_failure(stack, tmp_path, monkeypatch, change, rc):
    monkeypatch.setenv("FAKE_RUN", json.dumps({**RECORD, **change}))
    monkeypatch.setenv("FAKE_RC", str(rc))
    assert not run(stack, tmp_path).ok


def test_the_failure_carries_warden_own_reason(stack, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_RUN", json.dumps({**RECORD, "decision": "USAGE_ERROR", "reason": "pins 'x' to 1"}))
    monkeypatch.setenv("FAKE_RC", "2")
    result = run(stack, tmp_path)
    assert (result.decision, result.reason) == ("USAGE_ERROR", "pins 'x' to 1")


def test_output_that_is_not_a_run_record_is_a_failure_with_the_last_line(stack, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_RUN", "")
    monkeypatch.setenv("FAKE_ERR", "boom: no such seat\n")
    monkeypatch.setenv("FAKE_RC", "2")
    result = run(stack, tmp_path)
    assert not result.ok and result.decision == "CANARY_ERROR" and "boom: no such seat" in result.reason


def test_a_record_that_is_not_an_object_is_a_failure(stack, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_RUN", "[1, 2]")
    assert not run(stack, tmp_path).ok


def test_a_missing_seat_checkout_is_named(stack, tmp_path):
    import shutil
    shutil.rmtree(stack / "JUDGE")
    result = run(stack, tmp_path)
    assert not result.ok and "no JUDGE checkout" in result.reason


def test_a_missing_stack_folder_is_a_failure(tmp_path):
    assert "does not exist" in cc.run_canary(tmp_path / "nope", tmp_path).reason


def test_a_circuit_that_does_not_finish_is_a_timeout(stack, tmp_path):
    (stack / "WARDEN" / "warden" / "cli.py").write_text("import time\ntime.sleep(30)\n")
    result = cc.run_canary(stack, tmp_path / "cns", timeout=1)
    assert not result.ok and result.decision == "CANARY_TIMEOUT"


def test_warden_is_handed_the_stack_the_hub_and_a_documentation_grant(stack, tmp_path):
    (stack / "WARDEN" / "warden" / "cli.py").write_text(
        "import json, sys\nprint(json.dumps({'decision': 'ACCEPT', 'reason': ' '.join(sys.argv[1:]), "
        "'converged': True, 'put_back': False}))\n")
    result = run(stack, tmp_path)
    assert result.ok
    assert "tagteam" in result.reason
    assert f"--stack {stack}" in result.reason and f"--cns {tmp_path / 'cns'}" in result.reason
    assert "--scope documentation" in result.reason


def test_the_seats_are_importable_from_the_stack_and_the_hub(stack, tmp_path):
    (stack / "WARDEN" / "warden" / "cli.py").write_text(
        "import json, os\nprint(json.dumps({'decision': 'ACCEPT', 'reason': os.environ['PYTHONPATH'], "
        "'converged': True, 'put_back': False}))\n")
    got = run(stack, tmp_path).reason.split(os.pathsep)
    assert got == [str(stack / n) for n in ("WARDEN", "JUDGE", "DRAFTER", "BURNISH")] + [str(tmp_path / "cns")]


def test_the_canary_leaves_the_stack_as_it_found_it_and_removes_its_scratch(stack, tmp_path):
    before = sorted(p.relative_to(stack).as_posix() for p in stack.rglob("*") if "__pycache__" not in p.parts)
    (stack / "WARDEN" / "warden" / "cli.py").write_text(
        "import json, sys\nprint(json.dumps({'decision': 'ACCEPT', 'reason': sys.argv[2], "
        "'converged': True, 'put_back': False}))\n")
    result = run(stack, tmp_path)
    after = sorted(p.relative_to(stack).as_posix() for p in stack.rglob("*") if "__pycache__" not in p.parts)
    assert after == before
    assert not Path(result.reason).exists()          # the throwaway target is gone


def test_the_throwaway_target_is_a_clean_git_repository(stack, tmp_path):
    (stack / "WARDEN" / "warden" / "cli.py").write_text(
        "import json, subprocess, sys\n"
        "out = subprocess.run(['git', '-C', sys.argv[2], 'status', '--porcelain'], capture_output=True, text=True)\n"
        "print(json.dumps({'decision': 'ACCEPT', 'reason': 'dirty:' + out.stdout, 'converged': True, "
        "'put_back': False}))\n")
    assert run(stack, tmp_path).reason == "dirty:"


def test_the_cli_exit_codes(stack, tmp_path, capsys, monkeypatch):
    assert cc.main(["--stack", str(stack), "--cns", str(tmp_path / "cns")]) == 0
    assert "ACCEPT" in capsys.readouterr().out
    monkeypatch.setenv("FAKE_RUN", json.dumps({**RECORD, "decision": "REJECT", "reason": "red"}))
    monkeypatch.setenv("FAKE_RC", "1")
    assert cc.main(["--stack", str(stack), "--cns", str(tmp_path / "cns")]) == 1
    assert "REJECT: red" in capsys.readouterr().err

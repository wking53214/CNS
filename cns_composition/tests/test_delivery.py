"""delivery: an undelivered report is never exit 0, and a file is written whole, over a regular file or nothing.

The cases that need a real file descriptor run a command in a subprocess with descriptor 1 closed, or with the
reader of its pipe already gone. No device node is opened or written; the special files are a FIFO and a folder
the test creates, and a full device is a stand-in stream whose flush raises ENOSPC.
"""

import ast
import errno
import io
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from cns_composition import delivery

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ("seat_pins", "cns_versions", "repin", "circuit_canary", "consumers", "digest_vectors", "link_ledger",
            "install_stack", "circuit_refusals")


# ---------------------------------------------------------------------------------------------- deliver, in process

def test_a_delivered_report_keeps_its_exit_code(capsys):
    print("the report")
    assert delivery.deliver(0, "x") == 0 and delivery.deliver(1, "x") == 1
    assert capsys.readouterr().err == ""


def test_a_closed_stdout_turns_success_into_two_and_says_so(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdout", None)
    assert delivery.deliver(0, "seat_pins") == 2
    assert "seat_pins: stdout is closed, so the report was not delivered" in capsys.readouterr().err


def test_a_failure_that_was_already_reported_keeps_its_code_and_still_says_the_report_was_lost(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdout", None)
    assert delivery.deliver(1, "x") == 1
    assert "not delivered" in capsys.readouterr().err


class _Failing(io.StringIO):
    def __init__(self, err: OSError):
        super().__init__()
        self.err = err

    def flush(self):
        raise self.err


@pytest.mark.parametrize("err", [BrokenPipeError(errno.EPIPE, "Broken pipe"), OSError(errno.ENOSPC, "No space left"),
                                 OSError(errno.EIO, "Input/output error")])
def test_a_flush_that_fails_is_two_and_stdout_is_detached_so_shutdown_cannot_fail_again(monkeypatch, capsys, err):
    monkeypatch.setattr(sys, "stdout", _Failing(err))
    monkeypatch.setattr(sys, "__stdout__", sys.stdout)
    assert delivery.deliver(0, "repin") == 2
    assert sys.stdout is None and sys.__stdout__ is None
    assert f"repin: the report could not be delivered ({type(err).__name__})" in capsys.readouterr().err


def test_a_closed_stderr_does_not_raise(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert delivery.deliver(0, "x") == 2


# ------------------------------------------------------------------------------------------ the commands, in a process

def _run(module, *args, **kw):
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-m", f"cns_composition.{module}", *args], env=env, cwd=ROOT,
                          text=True, timeout=120, **kw)


@pytest.mark.parametrize("module", ["consumers", "digest_vectors", "link_ledger"])
def test_a_command_with_stdout_closed_exits_two_and_names_it(module):
    done = _run(module, stderr=subprocess.PIPE, preexec_fn=lambda: os.close(1))
    assert done.returncode == 2, done.stderr
    assert f"{module}: stdout is closed" in done.stderr
    assert "Traceback" not in done.stderr


@pytest.mark.parametrize("module", ["consumers", "digest_vectors", "link_ledger"])
def test_a_command_whose_reader_has_gone_exits_two_with_no_traceback(module):
    reader, writer = os.pipe()
    os.close(reader)
    try:
        done = _run(module, stdout=writer, stderr=subprocess.PIPE)
    finally:
        os.close(writer)
    assert done.returncode == 2, done.stderr
    assert "could not be delivered (BrokenPipeError)" in done.stderr
    assert "Traceback" not in done.stderr and "Exception ignored" not in done.stderr


def test_every_command_in_the_package_ends_with_deliver():
    """A new command that prints a report and returns without `deliver` is the defect this module exists for."""
    for module in sorted(p.stem for p in (ROOT / "cns_composition").glob("*.py")):
        source = (ROOT / "cns_composition" / f"{module}.py").read_text(encoding="utf-8")
        if '__name__ == "__main__"' not in source:
            continue
        assert module in COMMANDS, f"{module} is a command this test does not know"
        tree = ast.parse(source)
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        last = main.body[-1]
        assert isinstance(last, ast.Return) and isinstance(last.value, ast.Call), module
        func = last.value.func
        assert isinstance(func, ast.Attribute) and func.attr == "deliver" and \
            isinstance(func.value, ast.Name) and func.value.id == "delivery", f"{module}.main does not end with delivery.deliver"
        assert last.value.args[1].value == module, f"{module}.main names another program"  # type: ignore[attr-defined]


# ------------------------------------------------------------------------------------------------------- write_file

def test_write_file_writes_whole_and_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "out.json"
    delivery.write_file(target, "{}\n")
    assert target.read_text() == "{}\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_write_file_replaces_a_regular_file_and_keeps_its_permission_bits(tmp_path):
    target = tmp_path / "out.json"
    target.write_text("old")
    os.chmod(target, 0o640)
    delivery.write_file(target, "new")
    assert target.read_text() == "new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_write_file_refuses_a_symbolic_link_and_leaves_its_target_alone(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("real")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(delivery.DeliveryError, match="is a symbolic link; a file is only ever written over a regular file"):
        delivery.write_file(link, "x")
    assert real.read_text() == "real" and link.is_symlink()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["link.json", "real.json"]


def test_write_file_refuses_a_named_pipe_without_blocking(tmp_path):
    fifo = tmp_path / "out.json"
    os.mkfifo(fifo)
    with pytest.raises(delivery.DeliveryError, match="is a named pipe"):
        delivery.write_file(fifo, "x")
    assert stat.S_ISFIFO(os.lstat(fifo).st_mode)


def test_write_file_refuses_a_folder(tmp_path):
    with pytest.raises(delivery.DeliveryError, match="is a folder"):
        delivery.write_file(tmp_path, "x")


def test_write_file_refuses_a_link_that_appears_between_the_check_and_the_rename(tmp_path, monkeypatch):
    target = tmp_path / "out.json"
    target.write_text("old")
    calls = []
    original_kind = delivery._kind

    def kind(path):
        calls.append(path)
        if len(calls) == 2:  # the second look, just before the rename: a link has appeared
            Path(path).unlink()
            Path(path).symlink_to(tmp_path / "elsewhere")
        return original_kind(path)

    monkeypatch.setattr(delivery, "_kind", kind)
    with pytest.raises(delivery.DeliveryError, match="is a symbolic link"):
        delivery.write_file(target, "new")
    assert target.is_symlink() and not (tmp_path / "elsewhere").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_a_failed_write_leaves_the_old_file_whole_and_no_temporary_file(tmp_path, monkeypatch):
    target = tmp_path / "out.json"
    target.write_text("old")

    def fail(*a, **k):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(delivery.DeliveryError, match="could not be written: OSError"):
        delivery.write_file(target, "new")
    assert target.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


# ----------------------------------------------------------------------- the two commands that write, through it

def test_read_text_refuses_a_named_pipe_and_a_folder_instead_of_blocking(tmp_path):
    fifo = tmp_path / "in.json"
    os.mkfifo(fifo)
    with pytest.raises(delivery.DeliveryError, match="is a named pipe, not a regular file, so it was not read"):
        delivery.read_text(fifo)
    with pytest.raises(delivery.DeliveryError, match="is a folder"):
        delivery.read_text(tmp_path)
    with pytest.raises(FileNotFoundError):  # the caller's own "cannot be read" message is kept for this case
        delivery.read_text(tmp_path / "missing")
    (tmp_path / "ok").write_text("text")
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "ok")
    assert delivery.read_text(link) == "text"  # a link to a regular file is read; only what it points at matters


def test_the_files_a_person_names_are_refused_when_they_are_pipes(tmp_path, capsys):
    """`repin --manifest`, `seat_pins --manifest`, `cns_versions --table` and `link_ledger --ledger` each read a
    file the command line names. A pipe there blocked the command forever; now it is exit 2 by name."""
    from cns_composition import cns_versions, link_ledger, repin, seat_pins
    fifo = tmp_path / "named.json"
    os.mkfifo(fifo)
    stack = tmp_path / "stack"
    stack.mkdir()
    assert repin.main(["--stack", str(stack), "--manifest", str(fifo)]) == 2
    assert "is a named pipe" in capsys.readouterr().err
    assert seat_pins.main(["--stack", str(stack), "--manifest", str(fifo)]) == 2
    assert "is a named pipe" in capsys.readouterr().err
    assert cns_versions.main(["--stack", str(stack), "--table", str(fifo)]) == 2
    assert "is a named pipe" in capsys.readouterr().err
    assert link_ledger.main(["--ledger", str(fifo)]) == 2
    assert "is a named pipe" in capsys.readouterr().err


def test_digest_vectors_write_refuses_a_symbolic_link_at_the_vectors_file(tmp_path, monkeypatch, capsys):
    from cns_composition import digest_vectors
    link = tmp_path / "digest-vectors.json"
    link.symlink_to(tmp_path / "elsewhere.json")
    monkeypatch.setattr(digest_vectors, "_default_path", lambda: link)
    assert digest_vectors.main(["--write"]) == 2
    assert "is a symbolic link" in capsys.readouterr().err
    assert not (tmp_path / "elsewhere.json").exists()
